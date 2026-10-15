"""Leaderboards by activity points: weekly within your league, monthly across everyone."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..game import balance as B
from ..game import clicker
from ..services import activity
from ..services.users import get_or_create, now_ms
from .deps import CurrentTg, Session

router = APIRouter(prefix="/api/top")

PRIZE_NAMES = {"arcana": "Аркана", "immortal": "Immortal", "dota_plus": "Dota Plus"}


def _name(u) -> str:
    return u.username or u.first_name or f"id{u.id}"


@router.get("/{kind}")
async def leaderboard(kind: str, request: Request, tg: CurrentTg, s: Session) -> dict:
    if kind not in ("week", "month"):
        raise HTTPException(404)
    tz = request.app.state.settings.timezone
    me = await get_or_create(s, tg)
    now = now_ms()
    period = activity.week_key(now, tz) if kind == "week" else activity.month_key(now, tz)
    league = None
    if kind == "week":
        mine = await s.get(activity.Activity, (me.id, period))
        league = mine.league if mine else clicker.league(me)["index"]
    rows = await activity.top(s, period, league, B.TOP_SIZE)
    place, points, _ = await activity.my_place(s, me.id, period, league)
    await s.commit()
    prizes = ([{"place": i + 1, "souls": v} for i, v in enumerate(B.WEEK_PRIZES_SOULS)] if kind == "week"
              else [{"place": i + 1, "item": PRIZE_NAMES[p]} for i, p in enumerate(B.MONTH_PRIZES)])
    return {
        "period": period,
        "ends_ms": activity.period_end_ms(period, tz),
        "league": None if league is None else {"index": league, "name": B.LEAGUES[league][0]},
        "prizes": prizes,
        "top": [{"rank": i + 1, "id": u.id, "name": _name(u), "photo_url": u.photo_url, "points": a.points, "me": u.id == me.id}
                for i, (a, u) in enumerate(rows)],
        "me": {"rank": place, "points": points},
    }
