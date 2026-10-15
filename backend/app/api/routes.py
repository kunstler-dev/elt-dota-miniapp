from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from ..game import arsenal as A
from ..game import balance as B
from ..game import clicker
from ..models import SteamAccount, User
from ..services import activity, steam_link
from ..services.subscriptions import refresh_required
from ..services.users import get_or_create, now_ms
from ..telegram_auth import parse_ref
from .deps import CurrentTg, Session

router = APIRouter(prefix="/api")


def state_out(u: User, now: int) -> dict:
    return {
        "coins": u.coins,
        "earned_total": u.earned_total,
        "souls": u.souls,
        "energy": u.energy,
        "max_energy": clicker.max_energy(u),
        "energy_regen": B.ENERGY_REGEN_PER_SEC,
        "tap_power": clicker.tap_power(u),
        "active_hero": A.active_hero(u),
        "profit_per_hour": u.profit_per_hour,
        "league": clicker.league(u),
        "server_ms": now,
    }


@router.get("/health")
async def health() -> dict:
    return {"ok": True}


@router.get("/me")
async def me(request: Request, tg: CurrentTg, s: Session) -> dict:
    u = await get_or_create(s, tg, parse_ref(tg.start_param))
    now = now_ms()
    clicker.sync(u, now)
    subscribed = await refresh_required(request.app, u, now)
    await s.commit()
    bot_username = getattr(request.app.state, "bot_username", None)
    channel = request.app.state.settings.required_channel
    return {
        "user": {"id": u.id, "first_name": u.first_name, "username": u.username, "is_premium": u.is_premium,
                 "photo_url": u.photo_url, "is_admin": u.id in request.app.state.settings.admin_id_set},
        "steam": steam_link.status(await s.get(SteamAccount, u.id)),
        "subscription": {"channel": channel, "url": f"https://t.me/{channel.lstrip('@')}", "ok": subscribed},
        "state": state_out(u, now),
        "invite_link": f"https://t.me/{bot_username}?start=ref_{u.id}" if bot_username else None,
    }


@router.post("/subscription/check")
async def check_subscription(request: Request, tg: CurrentTg, s: Session) -> dict:
    """"I've subscribed" button: check the subscription right now, bypassing the 10-minute cache."""
    u = await get_or_create(s, tg)
    ok = await refresh_required(request.app, u, now_ms(), force=True)
    await s.commit()
    return {"ok": ok}


class TapIn(BaseModel):
    taps: int = Field(ge=1, le=500)


async def require_access(s: Session, user_id: int) -> None:
    """Playing requires a linked Steam account (protection against bots and multi-accounts)
    and a subscription to the required channel (checked in /api/me at least every 10 minutes)."""
    if await s.get(SteamAccount, user_id) is None:
        await s.rollback()
        raise HTTPException(403, "steam_required")
    u = await s.get(User, user_id)
    if u is not None and not u.sub_ok:
        await s.rollback()
        raise HTTPException(403, "subscription_required")


@router.post("/tap")
async def tap(body: TapIn, request: Request, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    u = await get_or_create(s, tg)
    now = now_ms()
    accepted = clicker.apply_taps(u, body.taps, now)
    await activity.add(s, u, accepted * B.ACT_TAP, now, request.app.state.settings.timezone)
    await s.commit()
    return {"accepted": accepted, "state": state_out(u, now)}

