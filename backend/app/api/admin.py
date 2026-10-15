"""Admin panel (ADMIN_IDS only): online users, sign-ups, tasks, mini-games, economy, monthly prizes."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from ..game import daily
from ..game.tasks import TASKS
from ..models import (AnalysisSub, GameDay, Guild, PrizeClaim, StarPayment, SteamAccount, User, UserTask)
from ..services.users import now_ms
from .deps import AdminTg, Session

router = APIRouter(prefix="/api/admin")

ONLINE_MS = 5 * 60 * 1000
DAY_MS = 24 * 3600 * 1000


async def _count(s: Session, q) -> int:
    return int((await s.execute(q)).scalar() or 0)


def _uname(u: User | None, uid: int) -> str:
    if u is None:
        return str(uid)
    return f"@{u.username}" if u.username else (u.first_name or str(uid))


@router.get("/stats")
async def stats(request: Request, _: AdminTg, s: Session) -> dict:
    tz = request.app.state.settings.timezone
    now = now_ms()
    today = daily.game_day(now, tz)
    day_start = int(datetime.combine(today, datetime.min.time(), tzinfo=ZoneInfo(tz)).timestamp() * 1000)
    users = select(func.count()).select_from(User)
    tasks = []
    for t in TASKS:
        done = await _count(s, select(func.count()).select_from(UserTask).where(UserTask.task_id == t.id))
        today_done = await _count(s, select(func.count()).select_from(UserTask).where(
            UserTask.task_id == t.id, UserTask.done_ms >= day_start))
        tasks.append({"id": t.id, "title": t.title, "souls": t.souls, "done": done, "today": today_done})
    games = {}
    for g in ("hook", "guess"):
        row = (await s.execute(select(func.count(), func.coalesce(func.sum(GameDay.plays), 0)).where(
            GameDay.game == g, GameDay.day == today.isoformat()))).one()
        games[g] = {"players_today": int(row[0]), "plays_today": int(row[1])}
    return {
        "server_ms": now,
        "users": {
            "total": await _count(s, users),
            "online": await _count(s, users.where(User.seen_ms >= now - ONLINE_MS)),
            "today": await _count(s, users.where(User.seen_ms >= day_start)),
            "week": await _count(s, users.where(User.seen_ms >= now - 7 * DAY_MS)),
            "new_today": await _count(s, users.where(User.created_ms >= day_start)),
            "new_week": await _count(s, users.where(User.created_ms >= now - 7 * DAY_MS)),
            "subscribed": await _count(s, users.where(User.sub_ok.is_(True))),
            "steam_linked": await _count(s, select(func.count()).select_from(SteamAccount)),
            "steam_verified": await _count(s, select(func.count()).select_from(SteamAccount).where(
                SteamAccount.passed.is_(True))),
            "referred": await _count(s, users.where(User.ref_confirmed_ms.is_not(None))),
        },
        "daily_claims_today": await _count(s, users.where(User.daily_last == today.isoformat())),
        "tasks": tasks,
        "games": games,
        "economy": {
            "coins": await _count(s, select(func.coalesce(func.sum(User.coins), 0))),
            "earned_total": await _count(s, select(func.coalesce(func.sum(User.earned_total), 0))),
            "souls": await _count(s, select(func.coalesce(func.sum(User.souls), 0))),
        },
        "guilds": await _count(s, select(func.count()).select_from(Guild)),
        "analysis": {
            "active_subs": await _count(s, select(func.count()).select_from(AnalysisSub).where(AnalysisSub.expires_ms > now)),
            "stars_total": await _count(s, select(func.coalesce(func.sum(StarPayment.amount), 0)).where(
                StarPayment.refunded_ms.is_(None))),
        },
    }


@router.get("/prizes")
async def prizes(_: AdminTg, s: Session) -> dict:
    rows = (await s.execute(select(PrizeClaim, User, SteamAccount)
                            .join(User, User.id == PrizeClaim.user_id)
                            .join(SteamAccount, SteamAccount.user_id == PrizeClaim.user_id, isouter=True)
                            .order_by(PrizeClaim.status, PrizeClaim.period.desc(), PrizeClaim.place).limit(200))).all()
    return {"prizes": [{"id": p.id, "period": p.period, "place": p.place, "prize": p.prize, "status": p.status,
                        "user_id": u.id, "name": _uname(u, u.id),
                        "steam_id": acc.steam_id if acc else None, "persona": acc.persona if acc else None}
                       for p, u, acc in rows]}


@router.post("/prizes/{prize_id}/sent")
async def prize_sent(prize_id: int, _: AdminTg, s: Session) -> dict:
    p = await s.get(PrizeClaim, prize_id)
    if p is None:
        raise HTTPException(404, "prize_not_found")
    p.status = "sent"
    await s.commit()
    return {"ok": True}
