from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..game import clicker
from ..models import User
from ..telegram_auth import TgUser


def now_ms() -> int:
    return int(time.time() * 1000)


async def get_for_update(s: AsyncSession, user_id: int) -> User | None:
    # FOR UPDATE in Postgres serializes parallel requests of one player; SQLite ignores it
    return (await s.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one_or_none()


async def get_or_create(s: AsyncSession, tg: TgUser, referrer_id: int | None = None) -> User:
    """Finds a player (with a row lock) or creates one. The inviter is recorded only on creation."""
    u = await get_for_update(s, tg.id)
    if u is None:
        if referrer_id == tg.id or (referrer_id and await s.get(User, referrer_id) is None):
            referrer_id = None
        u = User(id=tg.id, referrer_id=referrer_id)
        clicker.init_new(u, now_ms())
        s.add(u)
        try:
            await s.flush()
        except IntegrityError:  # parallel first login: another request already created the row
            await s.rollback()
            u = await get_for_update(s, tg.id)
            assert u is not None
    u.first_name = tg.first_name or u.first_name or ""
    u.username = tg.username
    u.is_premium = tg.is_premium
    u.language = tg.language
    if tg.photo_url:
        u.photo_url = tg.photo_url
    u.seen_ms = now_ms()
    return u
