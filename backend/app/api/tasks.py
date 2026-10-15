from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..game import daily
from ..game.tasks import BY_ID, TASKS
from ..models import UserTask
from ..game import balance as B
from ..services import activity, souls
from ..services.subscriptions import has_boost, is_member
from ..services.users import get_or_create, now_ms
from .deps import CurrentTg, Session
from .routes import require_access, state_out

router = APIRouter(prefix="/api")


def _today(request: Request, now: int):
    return daily.game_day(now, request.app.state.settings.timezone)


@router.get("/tasks")
async def tasks(request: Request, tg: CurrentTg, s: Session) -> dict:
    u = await get_or_create(s, tg)
    done = set((await s.execute(select(UserTask.task_id).where(UserTask.user_id == u.id))).scalars())
    await s.commit()
    return {
        "daily": daily.status(u, _today(request, now_ms())),
        "tasks": [{"id": t.id, "kind": t.kind, "title": t.title, "badge": t.badge, "url": t.url, "souls": t.souls,
                   "done": t.id in done} for t in TASKS],
    }


@router.post("/daily/claim")
async def claim_daily(request: Request, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    u = await get_or_create(s, tg)
    now = now_ms()
    reward = daily.claim(u, _today(request, now))
    if reward is None:
        await s.rollback()
        raise HTTPException(409, "already_claimed")
    await activity.add(s, u, B.ACT_DAILY, now, request.app.state.settings.timezone)
    await s.commit()
    return {"reward": reward, "daily": daily.status(u, _today(request, now)), "state": state_out(u, now)}


@router.post("/tasks/{task_id}/check")
async def check_task(task_id: str, request: Request, tg: CurrentTg, s: Session) -> dict:
    t = BY_ID.get(task_id)
    if t is None:
        raise HTTPException(404, "unknown task")
    await require_access(s, tg.id)
    if await s.get(UserTask, (tg.id, t.id)) is not None:
        raise HTTPException(409, "already_done")
    if t.kind == "subscribe" and not await is_member(request, t.channel or "", tg.id):
        raise HTTPException(400, "not_subscribed")
    if t.kind == "boost" and not await has_boost(request, t.channel or "", tg.id):
        raise HTTPException(400, "not_boosted")
    u = await get_or_create(s, tg)
    now = now_ms()
    s.add(UserTask(user_id=u.id, task_id=t.id, done_ms=now, checked_ms=now))
    await souls.earn(s, u, t.souls, "task", t.id, now)
    await activity.add(s, u, B.ACT_TASK, now, request.app.state.settings.timezone)
    try:
        await s.commit()  # the (user_id, task_id) primary key prevents a double reward in a race
    except IntegrityError:
        await s.rollback()
        raise HTTPException(409, "already_done") from None
    return {"souls": t.souls, "state": state_out(u, now)}
