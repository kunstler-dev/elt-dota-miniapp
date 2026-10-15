"""Video contest (100,000 RUB): entries (video links), top 10 by views, admin review."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..models import ContestEntry, SteamAccount, User
from ..services import contest as C
from ..services.users import get_or_create, now_ms
from .deps import AdminTg, CurrentTg, Session
from .routes import require_access

router = APIRouter(prefix="/api")


def _entry(e: ContestEntry) -> dict:
    return {"id": e.id, "platform": e.platform, "url": e.url, "title": e.title, "author": e.author,
            "views": e.views, "views_ms": e.views_ms, "status": e.status, "note": e.note,
            "published_ms": e.published_ms, "created_ms": e.created_ms}


@router.get("/contest")
async def contest_info(tg: CurrentTg, s: Session) -> dict:
    me = await get_or_create(s, tg)
    now = now_ms()
    start, end = await C.window(s)
    mine = (await s.execute(select(ContestEntry).where(ContestEntry.contest == C.CONTEST_ID, ContestEntry.user_id == me.id)
                            .order_by(ContestEntry.created_ms))).scalars().all()
    top = await C.leaderboard(s, len(C.PRIZES_RUB))
    await s.commit()
    my_views = sum(e.views for e in mine if e.status != "rejected")
    return {"id": C.CONTEST_ID, "phase": C.phase(start, end, now), "start_ms": start, "end_ms": end,
            "prizes": C.PRIZES_RUB, "max_entries": C.MAX_ENTRIES, "hashtag": C.HASHTAG,
            "top": [{**r, "me": r["id"] == me.id} for r in top],
            "me": {"views": my_views, "rank": next((r["rank"] for r in top if r["id"] == me.id), None),
                   "entries": [_entry(e) for e in mine]}}


class EntryIn(BaseModel):
    url: str = Field(min_length=8, max_length=512)


@router.post("/contest/entries")
async def submit(body: EntryIn, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    acc = await s.get(SteamAccount, tg.id)
    if acc is None or not acc.passed:
        raise HTTPException(403, "steam_not_verified")
    now = now_ms()
    start, end = await C.window(s)
    if C.phase(start, end, now) != "active":
        raise HTTPException(400, "contest_closed")
    try:
        platform, vid, url = C.parse_url(body.url)
    except C.BadUrl as e:
        raise HTTPException(400, "bad_url") from e
    n = (await s.execute(select(func.count()).select_from(ContestEntry).where(
        ContestEntry.contest == C.CONTEST_ID, ContestEntry.user_id == tg.id,
        ContestEntry.status != "rejected"))).scalar_one()
    if n >= C.MAX_ENTRIES:
        raise HTTPException(400, "too_many_entries")
    e = ContestEntry(contest=C.CONTEST_ID, user_id=tg.id, platform=platform, video_id=vid or f"short:{url[-40:]}",
                     url=url, views=0, views_ms=0, manual=False, status="pending", created_ms=now)
    s.add(e)
    try:
        await s.flush()
    except IntegrityError as ex:
        await s.rollback()
        raise HTTPException(409, "already_submitted") from ex
    await s.commit()
    return {"entry": _entry(e)}


@router.delete("/contest/entries/{entry_id}")
async def remove(entry_id: int, tg: CurrentTg, s: Session) -> dict:
    e = await s.get(ContestEntry, entry_id)
    if e is None or e.user_id != tg.id:
        raise HTTPException(404, "entry_not_found")
    await s.delete(e)
    await s.commit()
    return {"ok": True}


# ---------------- admin ----------------
@router.get("/admin/contest")
async def admin_list(_: AdminTg, s: Session) -> dict:
    start, end = await C.window(s)
    rows = (await s.execute(select(ContestEntry, User).join(User, User.id == ContestEntry.user_id)
                            .where(ContestEntry.contest == C.CONTEST_ID)
                            .order_by(ContestEntry.views.desc(), ContestEntry.id))).all()
    return {"phase": C.phase(start, end, now_ms()), "start_ms": start, "end_ms": end,
            "entries": [{**_entry(e), "user_id": u.id, "user": u.username or u.first_name or str(u.id),
                         "manual": e.manual, "fetch_error": e.fetch_error} for e, u in rows]}


@router.post("/admin/contest/start")
async def admin_start(_: AdminTg, s: Session) -> dict:
    start, end = await C.window(s)
    if start is not None:
        raise HTTPException(409, "already_started")
    start, end = await C.start(s, now_ms())
    await s.commit()
    return {"start_ms": start, "end_ms": end}


class ReviewIn(BaseModel):
    status: str | None = Field(default=None, pattern="^(pending|approved|rejected)$")
    views: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=256)


@router.post("/admin/contest/entries/{entry_id}")
async def admin_review(entry_id: int, body: ReviewIn, _: AdminTg, s: Session) -> dict:
    e = await s.get(ContestEntry, entry_id)
    if e is None:
        raise HTTPException(404, "entry_not_found")
    if body.status:
        e.status = body.status
    if body.note is not None:
        e.note = body.note or None
    if body.views is not None:
        e.views, e.manual, e.views_ms = body.views, True, now_ms()
    await s.commit()
    return {"entry": _entry(e)}


@router.post("/admin/contest/refresh")
async def admin_refresh(request: Request, _: AdminTg, s: Session) -> dict:
    stats = await C.refresh_views(s, request.app.state.settings.youtube_api_key, now_ms(), force=True)
    await s.commit()
    return stats
