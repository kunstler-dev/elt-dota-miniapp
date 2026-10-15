"""Player profile: your own (Profile tab) and someone else's (opened from the leaderboards). Others don't see the balance or Steam ID."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from ..game import arsenal as A
from ..game import clicker
from ..models import GameDay, SteamAccount, User, UserHero, UserItem
from ..services import activity
from ..services.users import get_or_create, now_ms
from .deps import CurrentTg, Session

router = APIRouter(prefix="/api/profile")


def look_of(u: User, hero: str) -> dict:
    """Hero look for 3D: the body (arcana-aware) and the models of equipped items."""
    h = A.HERO_BY_ID[hero]
    eq = A.equipped(u, hero)
    models = {slot: A.ITEMS[i].model for slot, i in eq.items() if i}
    body = models.pop("body", h.dir + h.body)
    return {"hero": hero, "body": body, "gear": list(models.values()), "extras": [h.dir + e for e in h.extras]}


async def _profile(request: Request, s: Session, u: User, me: bool) -> dict:
    tz = request.app.state.settings.timezone
    now = now_ms()
    owned = {A.DEFAULT_HERO} | set((await s.execute(
        select(UserHero.hero_id).where(UserHero.user_id == u.id))).scalars())
    items = (await s.execute(select(func.count()).where(UserItem.user_id == u.id))).scalar_one()
    games = {g: (await s.execute(select(func.max(GameDay.best)).where(
        GameDay.user_id == u.id, GameDay.game == g))).scalar() or 0 for g in ("hook", "guess")}
    week = activity.week_key(now, tz)
    month = activity.month_key(now, tz)
    wrank, wpts, wleague = await activity.my_place(s, u.id, week, 0)
    mrank, mpts, _ = await activity.my_place(s, u.id, month, None)
    acc = await s.get(SteamAccount, u.id)
    hero = A.active_hero(u)
    out = {
        "id": u.id,
        "name": u.username or u.first_name or f"id{u.id}",
        "photo_url": u.photo_url,
        "is_premium": u.is_premium,
        "since_ms": u.created_ms,
        "league": clicker.league(u),
        "earned_total": u.earned_total,
        "tap_power": A.tap_power(u),
        "profit_per_hour": u.profit_per_hour,
        "hero": {"id": hero, "name": A.HERO_BY_ID[hero].name},
        "look": look_of(u, hero),
        "heroes": [{"id": h.id, "name": h.name, "owned": h.id in owned, "tap_power": A.hero_power(u, h.id)}
                   for h in A.HEROES],
        "items_owned": items,
        "friends": u.ref_count,
        "games": games,
        "week": {"rank": wrank, "points": wpts, "league": wleague},
        "month": {"rank": mrank, "points": mpts},
        "steam": {"persona": acc.persona if acc else None, "verified": bool(acc and acc.passed)},
    }
    if me:
        out["coins"], out["souls"] = u.coins, u.souls
    return out


@router.get("")
async def my_profile(request: Request, tg: CurrentTg, s: Session) -> dict:
    u = await get_or_create(s, tg)
    out = await _profile(request, s, u, True)
    await s.commit()
    return out


@router.get("/{user_id}")
async def other_profile(user_id: int, request: Request, tg: CurrentTg, s: Session) -> dict:
    await get_or_create(s, tg)
    u = await s.get(User, user_id)
    if u is None:
        raise HTTPException(404, "unknown player")
    out = await _profile(request, s, u, user_id == tg.id)
    await s.commit()
    return out
