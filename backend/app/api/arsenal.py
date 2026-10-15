"""Heroes (buy / pick for tapping) and their Arsenal (buy / equip items)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..game import arsenal as A
from ..game import clicker
from ..models import User, UserHero, UserItem
from ..services.users import get_or_create, now_ms
from .deps import CurrentTg, Session
from .routes import require_access, state_out

router = APIRouter(prefix="/api")


async def _owned_items(s: Session, user_id: int) -> set[str]:
    rows = await s.execute(select(UserItem.item_id).where(UserItem.user_id == user_id))
    return set(rows.scalars()) | {i.id for i in A.ITEMS.values() if i.set.tier == 0}


async def _owned_heroes(s: Session, user_id: int) -> set[str]:
    rows = await s.execute(select(UserHero.hero_id).where(UserHero.user_id == user_id))
    return set(rows.scalars()) | {A.DEFAULT_HERO}


def _out(u: User, hero: str, heroes: set[str], items: set[str]) -> dict:
    eq = A.equipped(u, hero)
    worn = {i for i in eq.values() if i}
    full = A.full_set(hero, eq)
    h = A.HERO_BY_ID[hero]
    active = A.active_hero(u)
    return {
        "heroes": [{"id": x.id, "name": x.name, "price": x.price, "power": x.power, "income": x.income,
                    "owned": x.id in heroes, "active": x.id == active, "tap_power": A.hero_power(u, x.id)}
                   for x in A.HEROES],
        "hero": hero,
        "model": {"dir": h.dir, "body": h.body, "extras": [h.dir + e for e in h.extras]},
        "slots": [{"id": s, "name": A.SLOT_NAMES.get(s, s)} for s in A.HERO_SLOTS[hero]],
        "sets": [{"id": g.id, "name": g.name, "tier": g.tier, "bonus": round(A.set_mult(g), 2)}
                 for g in A.SETS if g.hero == hero],
        "items": [{"id": i.id, "set": i.set.id, "slot": i.slot, "model": i.model, "power": i.power, "price": i.price,
                   "owned": i.id in items, "equipped": i.id in worn} for i in A.ITEMS.values() if i.hero == hero],
        "equipped": eq,
        "full_set": full.id if full else None,
        "tap_power": A.hero_power(u, hero),
    }


def _hero_or_404(hero: str | None, u: User) -> str:
    hero = hero or A.active_hero(u)
    if hero not in A.HERO_BY_ID:
        raise HTTPException(404, "unknown hero")
    return hero


@router.get("/arsenal")
async def get_arsenal(tg: CurrentTg, s: Session, hero: str | None = None) -> dict:
    u = await get_or_create(s, tg)
    out = _out(u, _hero_or_404(hero, u), await _owned_heroes(s, u.id), await _owned_items(s, u.id))
    await s.commit()
    return out


@router.post("/heroes/{hero_id}/buy")
async def buy_hero(hero_id: str, tg: CurrentTg, s: Session) -> dict:
    h = A.HERO_BY_ID.get(hero_id)
    if h is None:
        raise HTTPException(404, "unknown hero")
    await require_access(s, tg.id)
    u = await get_or_create(s, tg)
    heroes = await _owned_heroes(s, u.id)
    if hero_id in heroes:
        await s.rollback()
        raise HTTPException(409, "already_owned")
    now = now_ms()
    clicker.sync(u, now)  # income at the old rate, before the change
    if u.coins < h.price:
        await s.rollback()
        raise HTTPException(400, "not_enough_coins")
    u.coins -= h.price
    u.profit_per_hour += h.income
    u.active_hero = hero_id  # start tapping with the purchased hero right away
    s.add(UserHero(user_id=u.id, hero_id=hero_id, bought_ms=now))
    try:
        await s.commit()
    except IntegrityError:
        await s.rollback()
        raise HTTPException(409, "already_owned") from None
    return {"arsenal": _out(u, hero_id, heroes | {hero_id}, await _owned_items(s, u.id)), "state": state_out(u, now)}


@router.post("/heroes/{hero_id}/select")
async def select_hero(hero_id: str, tg: CurrentTg, s: Session) -> dict:
    u = await get_or_create(s, tg)
    heroes = await _owned_heroes(s, u.id)
    if hero_id not in heroes:
        await s.rollback()
        raise HTTPException(403, "not_owned")
    now = now_ms()
    clicker.sync(u, now)
    u.active_hero = hero_id
    await s.commit()
    return {"arsenal": _out(u, hero_id, heroes, await _owned_items(s, u.id)), "state": state_out(u, now)}


@router.post("/arsenal/{item_id}/buy")
async def buy_item(item_id: str, tg: CurrentTg, s: Session) -> dict:
    item = A.ITEMS.get(item_id)
    if item is None:
        raise HTTPException(404, "unknown item")
    await require_access(s, tg.id)
    u = await get_or_create(s, tg)
    heroes = await _owned_heroes(s, u.id)
    if item.hero not in heroes:
        await s.rollback()
        raise HTTPException(403, "hero_not_owned")
    items = await _owned_items(s, u.id)
    if item_id in items:
        await s.rollback()
        raise HTTPException(409, "already_owned")
    now = now_ms()
    clicker.sync(u, now)
    if u.coins < item.price:
        await s.rollback()
        raise HTTPException(400, "not_enough_coins")
    u.coins -= item.price
    s.add(UserItem(user_id=u.id, item_id=item_id, bought_ms=now))
    A.equip(u, item_id)  # equip the purchased item right away
    try:
        await s.commit()
    except IntegrityError:
        await s.rollback()
        raise HTTPException(409, "already_owned") from None
    return {"arsenal": _out(u, item.hero, heroes, items | {item_id}), "state": state_out(u, now)}


@router.post("/arsenal/{item_id}/equip")
async def equip_item(item_id: str, tg: CurrentTg, s: Session) -> dict:
    item = A.ITEMS.get(item_id)
    if item is None:
        raise HTTPException(404, "unknown item")
    u = await get_or_create(s, tg)
    items = await _owned_items(s, u.id)
    if item_id not in items:
        await s.rollback()
        raise HTTPException(403, "not_owned")
    now = now_ms()
    clicker.sync(u, now)
    A.equip(u, item_id)
    await s.commit()
    return {"arsenal": _out(u, item.hero, await _owned_heroes(s, u.id), items), "state": state_out(u, now)}
