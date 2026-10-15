"""Activity points and leaderboards: weekly (within your league, prizes in souls) and monthly (overall, real prizes).

Only players who passed the Steam check take part in rankings and prizes (option A);
unverified players still collect points, which count once they pass the check."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..game import balance as B
from ..game import clicker
from ..models import Activity, GuildMember, GuildPoints, PeriodPayout, PrizeClaim, SteamAccount, User
from . import souls


def _local(now_ms: int, tz: str) -> datetime:
    return datetime.fromtimestamp(now_ms / 1000, ZoneInfo(tz))


def week_key(now_ms: int, tz: str) -> str:
    y, w, _ = _local(now_ms, tz).isocalendar()
    return f"w:{y}-W{w:02d}"


def month_key(now_ms: int, tz: str) -> str:
    return "m:" + _local(now_ms, tz).strftime("%Y-%m")


def period_end_ms(period: str, tz: str) -> int:
    z = ZoneInfo(tz)
    if period.startswith("w:"):
        y, w = period[2:].split("-W")
        monday = datetime.fromisocalendar(int(y), int(w), 1).replace(tzinfo=z)
        return int((monday + timedelta(days=7)).timestamp() * 1000)
    y, m = map(int, period[2:].split("-"))
    nxt = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=z)
    return int(nxt.timestamp() * 1000)


async def add(s: AsyncSession, u: User, points: int, now_ms: int, tz: str) -> None:
    """Add activity points to the current week and month. Call while holding the player's row lock."""
    if points <= 0:
        return
    for period in (week_key(now_ms, tz), month_key(now_ms, tz)):
        row = await s.get(Activity, (u.id, period), with_for_update=True)
        if row is None:
            row = Activity(user_id=u.id, period=period, points=0, league=clicker.league(u)["index"])
            s.add(row)
        row.points += points
        row.updated_ms = now_ms
    member = await s.get(GuildMember, u.id)
    if member is not None:
        key = (member.guild_id, u.id, week_key(now_ms, tz))
        gp = await s.get(GuildPoints, key, with_for_update=True)
        if gp is None:
            gp = GuildPoints(guild_id=key[0], user_id=u.id, period=key[2], points=0)
            s.add(gp)
        gp.points += points


def _ranked(period: str, league: int | None):
    q = (select(Activity, User)
         .join(User, User.id == Activity.user_id)
         .join(SteamAccount, and_(SteamAccount.user_id == User.id, SteamAccount.passed.is_(True)))
         .where(Activity.period == period, Activity.points > 0))
    if league is not None:
        q = q.where(Activity.league == league)
    return q.order_by(Activity.points.desc(), Activity.updated_ms, Activity.user_id)


async def top(s: AsyncSession, period: str, league: int | None, limit: int) -> list[tuple[Activity, User]]:
    return list((await s.execute(_ranked(period, league).limit(limit))).tuples().all())


async def my_place(s: AsyncSession, user_id: int, period: str, league: int | None) -> tuple[int | None, int, int | None]:
    """(place or None, my points, my league for the week)."""
    mine = await s.get(Activity, (user_id, period))
    if mine is None or mine.points <= 0:
        return None, 0, None
    acc = await s.get(SteamAccount, user_id)
    lg = mine.league if league is not None else None
    if acc is None or not acc.passed:
        return None, mine.points, mine.league
    better = (select(func.count()).select_from(Activity)
              .join(SteamAccount, and_(SteamAccount.user_id == Activity.user_id, SteamAccount.passed.is_(True)))
              .where(Activity.period == period, Activity.points > 0,
                     (Activity.points > mine.points)
                     | ((Activity.points == mine.points) & (Activity.updated_ms < mine.updated_ms))
                     | ((Activity.points == mine.points) & (Activity.updated_ms == mine.updated_ms)
                        & (Activity.user_id < user_id))))
    if lg is not None:
        better = better.where(Activity.league == lg)
    return 1 + (await s.execute(better)).scalar_one(), mine.points, mine.league


async def pay_finished(s: AsyncSession, now_ms: int, tz: str) -> list[str]:
    """Pays out prizes for finished weeks and months (once). Called by a background job."""
    paid: list[str] = []
    prev_week = week_key(now_ms - 7 * 24 * 3600 * 1000, tz)
    month_start = _local(now_ms, tz).replace(day=1, hour=12)
    prev_month = "m:" + (month_start - timedelta(days=2)).strftime("%Y-%m")
    for period in (prev_week, prev_month):
        if period_end_ms(period, tz) > now_ms or await s.get(PeriodPayout, period) is not None:
            continue
        if period.startswith("w:"):
            leagues = (await s.execute(select(Activity.league).where(Activity.period == period).distinct())).scalars()
            for lg in list(leagues):
                for place, (_, u) in enumerate(await top(s, period, lg, len(B.WEEK_PRIZES_SOULS)), start=1):
                    winner = await s.get(User, u.id, with_for_update=True)
                    await souls.earn(s, winner, B.WEEK_PRIZES_SOULS[place - 1], "weekly_top", f"{period}#{place}", now_ms)
        else:
            for place, (_, u) in enumerate(await top(s, period, None, len(B.MONTH_PRIZES)), start=1):
                s.add(PrizeClaim(user_id=u.id, period=period, place=place, prize=B.MONTH_PRIZES[place - 1],
                                 status="pending", created_ms=now_ms))
        s.add(PeriodPayout(period=period, paid_ms=now_ms))
        paid.append(period)
    return paid
