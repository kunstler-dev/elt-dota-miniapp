"""Souls shop: arcanas and expensive immortal Dota 2 items from the Steam Community Market.

Price in souls = market price x the "souls per 1 USD" rate (set by an admin). Only players
who passed the Steam check can buy (option A). Souls are charged immediately; an admin gifts the item in Steam and marks
the order as delivered, or cancels it and the souls are refunded."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..models import ShopItem, ShopOrder, SteamAccount, User
from ..services import market, souls
from ..services.users import get_for_update, now_ms
from .deps import AdminTg, CurrentTg, Session
from .routes import require_access, state_out

router = APIRouter(prefix="/api")

MAX_PENDING = 3


def _item(i: ShopItem) -> dict:
    return {"id": i.id, "title": i.title, "kind": i.kind, "about": i.about, "price": i.price, "stock": i.stock,
            "need_note": i.need_note, "image": i.image, "active": i.active, "sort": i.sort,
            "usd_cents": i.usd_cents, "listings": i.listings, "usd_ms": i.usd_ms}


def _order(o: ShopOrder) -> dict:
    return {"id": o.id, "item_id": o.item_id, "title": o.title, "price": o.price, "note": o.note, "status": o.status,
            "admin_note": o.admin_note, "created_ms": o.created_ms, "updated_ms": o.updated_ms}


@router.get("/shop")
async def shop(tg: CurrentTg, s: Session) -> dict:
    await market.sync_catalog(s)
    items = (await s.execute(select(ShopItem).where(ShopItem.active.is_(True))
                             .order_by(ShopItem.sort, ShopItem.price.desc()))).scalars().all()
    orders = (await s.execute(select(ShopOrder).where(ShopOrder.user_id == tg.id)
                              .order_by(ShopOrder.created_ms.desc()).limit(50))).scalars().all()
    per_usd = await market.rate(s)
    await s.commit()
    return {"items": [_item(i) for i in items], "orders": [_order(o) for o in orders], "max_pending": MAX_PENDING,
            "souls_per_usd": per_usd}


class BuyIn(BaseModel):
    note: str = Field(default="", max_length=280)


@router.post("/shop/{item_id}/buy")
async def buy(item_id: str, body: BuyIn, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    acc = await s.get(SteamAccount, tg.id)
    if acc is None or not acc.passed:
        raise HTTPException(403, "steam_not_verified")
    u = await get_for_update(s, tg.id)
    item = await s.get(ShopItem, item_id, with_for_update=True)
    if item is None or not item.active:
        await s.rollback()
        raise HTTPException(404, "item_not_found")
    note = body.note.strip()
    if item.need_note and len(note) < 3:
        await s.rollback()
        raise HTTPException(400, "note_required")
    if (item.stock is not None and item.stock <= 0) or item.listings == 0:
        await s.rollback()
        raise HTTPException(409, "out_of_stock")
    pending = (await s.execute(select(func.count()).select_from(ShopOrder).where(
        ShopOrder.user_id == u.id, ShopOrder.status == "pending"))).scalar_one()
    if pending >= MAX_PENDING:
        await s.rollback()
        raise HTTPException(429, "too_many_pending")
    if u.souls < item.price:
        await s.rollback()
        raise HTTPException(400, "not_enough_souls")
    now = now_ms()
    o = ShopOrder(user_id=u.id, item_id=item.id, title=item.title, price=item.price, note=note, status="pending",
                  created_ms=now, updated_ms=now)
    s.add(o)
    await s.flush()
    souls.change(s, u, -item.price, "shop", f"order:{o.id}", now)
    if item.stock is not None:
        item.stock -= 1
    await s.commit()
    return {"order": _order(o), "state": state_out(u, now)}


# ---------------- admin ----------------
@router.get("/admin/shop")
async def admin_shop(request: Request, _: AdminTg, s: Session) -> dict:
    await market.sync_catalog(s)
    items = (await s.execute(select(ShopItem).order_by(ShopItem.sort, ShopItem.id))).scalars().all()
    rows = (await s.execute(select(ShopOrder, User, SteamAccount)
                            .join(User, User.id == ShopOrder.user_id)
                            .join(SteamAccount, SteamAccount.user_id == ShopOrder.user_id, isouter=True)
                            .order_by((ShopOrder.status != "pending"), ShopOrder.created_ms.desc()).limit(300))).all()
    per_usd = await market.rate(s)
    await s.commit()
    return {"souls_per_usd": per_usd, "refreshing": bool(getattr(request.app.state, "market_refreshing", False)),
            "items": [_item(i) for i in items],
            "orders": [{**_order(o), "user_id": u.id, "user": f"@{u.username}" if u.username else (u.first_name or str(u.id)),
                        "steam_id": acc.steam_id if acc else None, "persona": acc.persona if acc else None}
                       for o, u, acc in rows]}


class RateIn(BaseModel):
    souls_per_usd: int = Field(ge=1, le=1_000_000)


@router.post("/admin/shop/rate")
async def admin_rate(body: RateIn, _: AdminTg, s: Session) -> dict:
    await market.set_rate(s, body.souls_per_usd)
    await s.commit()
    return {"souls_per_usd": body.souls_per_usd}


@router.post("/admin/shop/refresh")
async def admin_refresh(request: Request, _: AdminTg) -> dict:
    """Refresh prices from the market now (in the background: ~3-4 s per item so the market doesn't rate-limit us)."""
    st = request.app.state
    if getattr(st, "market_refreshing", False):
        return {"started": False}
    st.market_refreshing = True

    async def run() -> None:
        try:
            await market.refresh_prices(st.db, now_ms(), force=True)
        finally:
            st.market_refreshing = False

    st.market_task = asyncio.create_task(run())
    return {"started": True}


class ItemPatch(BaseModel):
    stock: int | None = Field(default=None, ge=0)
    unlimited: bool = False
    active: bool | None = None


@router.patch("/admin/shop/items/{item_id}")
async def admin_item(item_id: str, body: ItemPatch, _: AdminTg, s: Session) -> dict:
    item = await s.get(ShopItem, item_id)
    if item is None:
        raise HTTPException(404, "item_not_found")
    if body.unlimited:
        item.stock = None
    elif body.stock is not None:
        item.stock = body.stock
    if body.active is not None:
        item.active = body.active
    await s.commit()
    return {"item": _item(item)}


class OrderIn(BaseModel):
    status: str = Field(pattern="^(sent|cancelled)$")
    admin_note: str | None = Field(default=None, max_length=280)


@router.post("/admin/shop/orders/{order_id}")
async def admin_order(order_id: int, body: OrderIn, _: AdminTg, s: Session) -> dict:
    o = await s.get(ShopOrder, order_id, with_for_update=True)
    if o is None:
        raise HTTPException(404, "order_not_found")
    if o.status != "pending":
        raise HTTPException(409, "order_closed")
    now = now_ms()
    if body.status == "cancelled":
        u = await get_for_update(s, o.user_id)
        souls.change(s, u, o.price, "shop_refund", f"order:{o.id}", now)
        item = await s.get(ShopItem, o.item_id)
        if item is not None and item.stock is not None:
            item.stock += 1
    o.status, o.admin_note, o.updated_ms = body.status, body.admin_note, now
    await s.commit()
    return {"order": _order(o)}
