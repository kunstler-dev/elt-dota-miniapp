from __future__ import annotations

import json
import secrets

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SteamAccount, SteamLinkToken

TOKEN_TTL_MS = 10 * 60 * 1000


async def new_token(s: AsyncSession, user_id: int, now_ms: int) -> str:
    await s.execute(delete(SteamLinkToken).where(SteamLinkToken.expires_ms < now_ms))
    token = secrets.token_urlsafe(24)
    s.add(SteamLinkToken(token=token, user_id=user_id, expires_ms=now_ms + TOKEN_TTL_MS))
    return token


async def token_owner(s: AsyncSession, token: str, now_ms: int) -> int | None:
    t = await s.get(SteamLinkToken, token)
    return t.user_id if t and t.expires_ms >= now_ms else None


async def link(s: AsyncSession, user_id: int, steam_id: str, now_ms: int) -> str:
    """Links Steam to a player. Returns ok | taken (Steam belongs to another player) | other_linked (player has another Steam)."""
    owner = (await s.execute(select(SteamAccount.user_id).where(SteamAccount.steam_id == steam_id))).scalar()
    if owner is not None and owner != user_id:
        return "taken"
    mine = await s.get(SteamAccount, user_id)
    if mine is not None:
        return "ok" if mine.steam_id == steam_id else "other_linked"
    s.add(SteamAccount(user_id=user_id, steam_id=steam_id, linked_ms=now_ms))
    try:
        await s.flush()
    except IntegrityError:  # race: the same Steam was linked in parallel
        await s.rollback()
        return "taken"
    return "ok"


def apply_check(acc: SteamAccount, chk: dict, now_ms: int) -> None:
    acc.passed = bool(chk.get("passed"))
    acc.checked_ms = now_ms
    acc.check_json = json.dumps(chk, ensure_ascii=False)
    acc.persona = (chk.get("persona") or acc.persona or "")[:64] or None
    acc.avatar_url = chk.get("avatar") or acc.avatar_url


def status(acc: SteamAccount | None) -> dict | None:
    if acc is None:
        return None
    reasons = json.loads(acc.check_json).get("reasons", []) if acc.check_json else []
    return {"steam_id": acc.steam_id, "persona": acc.persona, "avatar": acc.avatar_url,
            "verified": acc.passed, "reasons": reasons}
