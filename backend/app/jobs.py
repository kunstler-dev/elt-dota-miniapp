"""Background jobs of the process."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from sqlalchemy import select

from .game import leagues
from .game.tasks import BY_ID
from .models import User, UserTask
from .services import activity, contest, market, souls
from .services.subscriptions import CheckUnavailable, task_holds
from .services.users import get_for_update, now_ms

log = logging.getLogger("elt.jobs")

RECHECK_EVERY_MS = 2 * 24 * 3600 * 1000  # every completed task is rechecked every 2 days
BATCH = 200  # per pass, to stay within Bot API limits
LOOP_SLEEP_SEC = 30 * 60


async def recheck_tasks(app: FastAPI, now: int | None = None) -> dict:
    """Unsubscribed or the boost ended: the task reopens and its souls are charged back (debt allowed)."""
    now = now or now_ms()
    stats = {"checked": 0, "revoked": 0, "skipped": 0}
    async with app.state.db.sessions() as s:
        due = (await s.execute(
            select(UserTask).where(UserTask.checked_ms < now - RECHECK_EVERY_MS)
            .order_by(UserTask.checked_ms).limit(BATCH)
        )).scalars().all()
        for ut in due:
            task = BY_ID.get(ut.task_id)
            if task is None or task.channel is None:
                ut.checked_ms = now
                continue
            try:
                holds = await task_holds(app, task.kind, task.channel, ut.user_id)
            except CheckUnavailable:
                stats["skipped"] += 1  # unknown: leave it, try again next time
                continue
            stats["checked"] += 1
            if holds:
                ut.checked_ms = now
                continue
            u = await get_for_update(s, ut.user_id)
            if u is not None:
                souls.change(s, u, -task.souls, "task_revoke", task.id, now, allow_debt=True)
            await s.delete(ut)
            stats["revoked"] += 1
        await s.commit()
    if stats["revoked"]:
        log.info("task recheck: %s", stats)
    return stats


async def pay_prizes(app: FastAPI, now: int | None = None) -> list[str]:
    """Prizes for finished weeks (souls to the top of each league) and months (claims for real items)."""
    async with app.state.db.sessions() as s:
        paid = await activity.pay_finished(s, now or now_ms(), app.state.settings.timezone)
        await s.commit()
    if paid:
        log.info("prizes paid for %s", paid)
    return paid


async def contest_views(app: FastAPI, now: int | None = None) -> dict | None:
    """Contest video views, while the contest runs (and for a day after the end, to lock in the result)."""
    now = now or now_ms()
    async with app.state.db.sessions() as s:
        start, end = await contest.window(s)
        if start is None or now > (end or 0) + 24 * 3600 * 1000:
            return None
        stats = await contest.refresh_views(s, app.state.settings.youtube_api_key, now)
        await s.commit()
    return stats


async def league_cutoffs(app: FastAPI, now: int | None = None) -> list[int]:
    """Dynamic league thresholds from all players' current ratings (ratings decay, so compute as of now)."""
    now = now or now_ms()
    async with app.state.db.sessions() as s:
        rows = (await s.execute(select(User.league_score, User.league_ms).where(User.league_score > 0))).all()
    return leagues.recompute([int(leagues.decayed(sc, ms, now)) for sc, ms in rows])


async def draft_data(app: FastAPI) -> int:
    """Heroes and matchups for the draft duel (daily; the first load takes ~2 min because of the OpenDota rate limit)."""
    from .services import draft_data as DD
    from .services.opendota import for_app
    st = app.state
    if getattr(st, "draft_data", None) is not None and now_ms() - getattr(st, "draft_loaded_ms", 0) < 24 * 3600 * 1000:
        return len(st.draft_data.heroes)
    data = await DD.load(for_app(app))
    if data.heroes:
        st.draft_data, st.draft_loaded_ms = data, now_ms()
    return len(data.heroes)


async def draft_prizes(app: FastAPI, now: int | None = None) -> str | None:
    """Monthly draft ladder: the top by points (from DRAFT_MONTH_MIN_GAMES games) gets souls, once per month."""
    from datetime import timedelta
    from .game import balance as B
    from .models import DraftMonth, PeriodPayout
    now = now or now_ms()
    tz = app.state.settings.timezone
    month_start = activity._local(now, tz).replace(day=1, hour=12)
    period = "m:" + (month_start - timedelta(days=2)).strftime("%Y-%m")
    key = "d" + period  # "dm:2026-10", separate from the monthly activity leaderboard
    async with app.state.db.sessions() as s:
        if activity.period_end_ms(period, tz) > now or await s.get(PeriodPayout, key) is not None:
            return None
        rows = (await s.execute(select(DraftMonth).where(DraftMonth.period == period,
                                                         DraftMonth.games >= B.DRAFT_MONTH_MIN_GAMES)
                                .order_by(DraftMonth.points.desc(), DraftMonth.updated_ms)
                                .limit(len(B.DRAFT_MONTH_PRIZES_SOULS)))).scalars().all()
        for place, row in enumerate(rows, start=1):
            u = await get_for_update(s, row.user_id)
            await souls.earn(s, u, B.DRAFT_MONTH_PRIZES_SOULS[place - 1], "draft_top", f"{period}#{place}", now)
        s.add(PeriodPayout(period=key, paid_ms=now))
        await s.commit()
    return key


async def guild_war_prizes(app: FastAPI, now: int | None = None) -> str | None:
    """Guild wars: after last week, the top 3 guilds by points pay souls to every member
    who contributed at least GUILD_MIN_CONTRIB points (and passed the Steam check). Once per week."""
    from sqlalchemy import func
    from .game import balance as B
    from .models import GuildPoints, PeriodPayout, SteamAccount
    now = now or now_ms()
    tz = app.state.settings.timezone
    period = activity.week_key(now - 7 * 24 * 3600 * 1000, tz)
    key = "g" + period
    async with app.state.db.sessions() as s:
        if activity.period_end_ms(period, tz) > now or await s.get(PeriodPayout, key) is not None:
            return None
        total = func.sum(GuildPoints.points)
        top = (await s.execute(select(GuildPoints.guild_id, total).where(GuildPoints.period == period)
                               .group_by(GuildPoints.guild_id).having(total > 0).order_by(total.desc())
                               .limit(len(B.GUILD_WAR_PRIZES)))).all()
        for place, (gid, _) in enumerate(top, start=1):
            members = (await s.execute(
                select(GuildPoints.user_id).join(SteamAccount, SteamAccount.user_id == GuildPoints.user_id)
                .where(GuildPoints.guild_id == gid, GuildPoints.period == period,
                       GuildPoints.points >= B.GUILD_MIN_CONTRIB, SteamAccount.passed.is_(True)))).scalars().all()
            for uid in members:
                u = await get_for_update(s, uid)
                await souls.earn(s, u, B.GUILD_WAR_PRIZES[place - 1], "guild_war", f"{period}#{place}", now)
        s.add(PeriodPayout(period=key, paid_ms=now))
        await s.commit()
    return key


async def shop_prices(app: FastAPI) -> dict:
    """Showcase prices from the Steam Community Market, once a day per item."""
    return await market.refresh_prices(app.state.db, now_ms())


async def draft_loader(app: FastAPI) -> None:
    """Draft data: until loaded, retry every 2 minutes (OpenDota rate limit), then refresh once a day."""
    while True:
        try:
            n = await draft_data(app)
        except Exception:  # noqa: BLE001
            log.exception("draft_data failed")
            n = 0
        await asyncio.sleep(24 * 3600 if n else 120)


async def loop(app: FastAPI, with_bot: bool) -> None:
    while True:
        jobs = [league_cutoffs, pay_prizes, draft_prizes, guild_war_prizes, contest_views, shop_prices] + ([recheck_tasks] if with_bot else [])  # subscriptions can't be checked without the bot
        for job in jobs:
            try:
                await job(app)
            except Exception:  # noqa: BLE001 — the background loop must never crash
                log.exception("%s failed", job.__name__)
        await asyncio.sleep(LOOP_SLEEP_SEC)
