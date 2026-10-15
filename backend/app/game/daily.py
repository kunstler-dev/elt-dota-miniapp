"""Daily login reward in ELT COIN: a streak of days on the game calendar (TIMEZONE)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..models import User
from . import balance as B
from .clicker import earn


def game_day(now_ms: int, tz: str) -> date:
    return datetime.fromtimestamp(now_ms / 1000, ZoneInfo(tz)).date()


def next_day(u: User, today: date) -> tuple[int, bool]:
    """(streak day the player gets/got today; whether it can be claimed now)."""
    if u.daily_last == today.isoformat():
        return u.daily_streak, False
    if u.daily_last == (today - timedelta(days=1)).isoformat():
        return u.daily_streak % len(B.DAILY_REWARDS) + 1, True
    return 1, True


def status(u: User, today: date) -> dict:
    day, claimable = next_day(u, today)
    return {"day": day, "claimable": claimable, "rewards": B.DAILY_REWARDS}


def claim(u: User, today: date) -> int | None:
    day, claimable = next_day(u, today)
    if not claimable:
        return None
    reward = B.DAILY_REWARDS[day - 1]
    u.daily_streak, u.daily_last = day, today.isoformat()
    earn(u, reward)
    return reward
