from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from ..game import balance as B
from ..models import ShopItem, Ledger, SteamAccount, User
from ..services.users import get_or_create
from .deps import CurrentTg, Session

router = APIRouter(prefix="/api")

FRIENDS_LIMIT = 100
TOP_LIMIT = 50


def _name(u: User) -> str:
    return u.username or u.first_name or f"id{u.id}"


@router.get("/friends")
async def friends(request: Request, tg: CurrentTg, s: Session) -> dict:
    me = await get_or_create(s, tg)
    await s.commit()
    rows = (await s.execute(
        select(User, SteamAccount.passed)
        .outerjoin(SteamAccount, SteamAccount.user_id == User.id)
        .where(User.referrer_id == me.id)
        .order_by(User.ref_confirmed_ms.is_(None), User.created_ms.desc())
        .limit(FRIENDS_LIMIT)
    )).all()
    # souls each friend brought: bonus + share (ref in the ledger is the friend's id)
    brought = {ref: total for ref, total in (await s.execute(
        select(Ledger.ref, func.sum(Ledger.amount))
        .where(Ledger.user_id == me.id, Ledger.reason.in_(("ref_bonus", "ref_share")))
        .group_by(Ledger.ref)
    )).all()} if rows else {}
    total = (await s.execute(select(func.count()).where(User.referrer_id == me.id))).scalar_one()

    def status(u: User, passed: bool | None) -> str:
        if u.ref_confirmed_ms:
            return "confirmed"
        return "no_steam" if passed is None else "not_verified"

    bot = getattr(request.app.state, "bot_username", None)
    return {
        "invite_link": f"https://t.me/{bot}?start=ref_{me.id}" if bot else None,
        "rules": {"bonus": B.REF_BONUS, "bonus_premium": B.REF_BONUS_PREMIUM, "welcome": B.REF_WELCOME,
                  "share_l1": B.REF_SHARE_L1, "share_l2": B.REF_SHARE_L2,
                  # the cheapest arcana in the shop, for the "arcana = N friends" estimate
                  "arcana_souls": (await s.execute(select(func.min(ShopItem.price)).where(
                      ShopItem.kind == "arcana", ShopItem.active.is_(True)))).scalar()},
        "confirmed": me.ref_count,
        "invited": total,
        "souls_earned": me.ref_souls,
        "friends": [{"name": _name(u), "photo_url": u.photo_url, "is_premium": u.is_premium,
                     "status": status(u, passed), "souls": int(brought.get(str(u.id), 0))} for u, passed in rows],
    }


@router.get("/top/referrals")
async def top_referrals(tg: CurrentTg, s: Session) -> dict:
    me = await get_or_create(s, tg)
    await s.commit()
    top = (await s.execute(
        select(User).where(User.ref_count > 0).order_by(User.ref_count.desc(), User.id).limit(TOP_LIMIT)
    )).scalars().all()
    rank = None
    if me.ref_count > 0:
        rank = 1 + (await s.execute(select(func.count()).where(
            (User.ref_count > me.ref_count) | ((User.ref_count == me.ref_count) & (User.id < me.id))))).scalar_one()
    return {
        "top": [{"rank": i + 1, "id": u.id, "name": _name(u), "photo_url": u.photo_url, "value": u.ref_count, "me": u.id == me.id}
                for i, u in enumerate(top)],
        "me": {"rank": rank, "value": me.ref_count},
    }
