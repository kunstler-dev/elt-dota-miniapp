"""Video contest: link parsing, views (YouTube Data API / TikTok page), dates and ranking.

Contest dates are stored in app_settings (an admin starts the contest with a button: 30 days from the start).
Prizes are Steam top-up codes / Dota 2 items of equivalent value, not cash."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AppSetting, ContestEntry, User

log = logging.getLogger("elt.contest")

CONTEST_ID = "video1"
DURATION_MS = 30 * 24 * 3600 * 1000
PRIZES_RUB = [30_000, 20_000, 15_000, 10_000, 7_000, 6_000, 4_000, 3_000, 3_000, 2_000]
MAX_ENTRIES = 5                 # videos per participant; the score is the sum of views
REFRESH_EVERY_MS = 2 * 3600 * 1000
HASHTAG = "#ELTdota"

YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
TT_VIDEO = re.compile(r"/video/(\d{8,25})")
TT_PLAY = re.compile(r'"playCount"\s*:\s*"?(\d+)')
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")


class BadUrl(ValueError):
    pass


def parse_url(raw: str) -> tuple[str, str | None, str]:
    """(platform, video_id or None for short TikTok links, normalized url)."""
    raw = raw.strip()
    if not re.match(r"^https?://", raw):
        raw = "https://" + raw
    u = urlparse(raw)
    host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    path = u.path.rstrip("/")
    if host in ("youtube.com", "music.youtube.com"):
        vid = None
        if path == "/watch":
            vid = (parse_qs(u.query).get("v") or [None])[0]
        elif path.startswith(("/shorts/", "/live/", "/embed/")):
            vid = path.split("/")[2]
        if vid and YT_ID.match(vid):
            return "youtube", vid, f"https://www.youtube.com/watch?v={vid}"
    elif host == "youtu.be":
        vid = path.lstrip("/")
        if YT_ID.match(vid):
            return "youtube", vid, f"https://www.youtube.com/watch?v={vid}"
    elif host == "tiktok.com" or host.endswith(".tiktok.com"):
        m = TT_VIDEO.search(path)
        if m:
            return "tiktok", m.group(1), f"https://www.tiktok.com{path}"
        if host in ("vm.tiktok.com", "vt.tiktok.com") or path.startswith("/t/"):
            return "tiktok", None, raw            # short link: the id is resolved via the redirect
    raise BadUrl("bad_url")


# ---- dates ----
async def _setting(s: AsyncSession, key: str) -> str | None:
    row = await s.get(AppSetting, key)
    return row.value if row else None


async def window(s: AsyncSession) -> tuple[int | None, int | None]:
    start = await _setting(s, f"contest_{CONTEST_ID}_start")
    end = await _setting(s, f"contest_{CONTEST_ID}_end")
    return (int(start) if start else None, int(end) if end else None)


async def start(s: AsyncSession, now: int) -> tuple[int, int]:
    for key, value in ((f"contest_{CONTEST_ID}_start", now), (f"contest_{CONTEST_ID}_end", now + DURATION_MS)):
        row = await s.get(AppSetting, key)
        if row is None:
            s.add(AppSetting(key=key, value=str(value)))
        else:
            row.value = str(value)
    return now, now + DURATION_MS


def phase(start_ms: int | None, end_ms: int | None, now: int) -> str:
    if start_ms is None:
        return "soon"
    return "active" if now < (end_ms or 0) else "finished"


# ---- ranking ----
async def leaderboard(s: AsyncSession, limit: int = 10) -> list[dict]:
    total = func.sum(ContestEntry.views)
    rows = (await s.execute(
        select(User, total.label("views"), func.count().label("videos"))
        .join(ContestEntry, ContestEntry.user_id == User.id)
        .where(ContestEntry.contest == CONTEST_ID, ContestEntry.status != "rejected")
        .group_by(User.id).having(total > 0)
        .order_by(total.desc(), func.min(ContestEntry.created_ms)).limit(limit))).all()
    return [{"rank": i + 1, "id": u.id, "name": u.username or u.first_name or f"id{u.id}", "photo_url": u.photo_url,
             "views": int(v), "videos": int(n), "prize_rub": PRIZES_RUB[i] if i < len(PRIZES_RUB) else 0}
            for i, (u, v, n) in enumerate(rows)]


# ---- views ----
Fetch = Callable[[str, dict], Awaitable[httpx.Response]]


async def _get(url: str, headers: dict) -> httpx.Response:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as c:
        return await c.get(url)


async def youtube_stats(ids: list[str], key: str, fetch: Fetch = _get) -> dict[str, dict]:
    """videos.list: up to 50 ids per request (1 quota unit out of 10,000 per day)."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        r = await fetch("https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet"
                        f"&id={','.join(chunk)}&key={key}", {})
        if r.status_code != 200:
            raise RuntimeError(f"youtube {r.status_code}")
        for it in r.json().get("items", []):
            sn = it.get("snippet") or {}
            pub = sn.get("publishedAt")
            out[it["id"]] = {
                "views": int((it.get("statistics") or {}).get("viewCount") or 0),
                "title": (sn.get("title") or "")[:256], "author": (sn.get("channelTitle") or "")[:128],
                "published_ms": int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp() * 1000) if pub else None,
            }
    return out


async def tiktok_stats(url: str, fetch: Fetch = _get) -> dict:
    """Views from the video page (embedded JSON). TikTok may serve a captcha; then it's an error and an admin enters views by hand."""
    r = await fetch(url, {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    final = str(r.url)
    m = TT_VIDEO.search(urlparse(final).path)
    html = r.text
    pc = TT_PLAY.search(html)
    if r.status_code != 200 or not pc:
        raise RuntimeError("tiktok_unavailable")
    res: dict = {"views": int(pc.group(1)), "video_id": m.group(1) if m else None, "url": final.split("?")[0]}
    ct = re.search(r'"createTime"\s*:\s*"?(\d{9,11})', html)
    if ct:
        res["published_ms"] = int(ct.group(1)) * 1000
    au = re.search(r'"uniqueId"\s*:\s*"([^"]{1,64})"', html)
    if au:
        res["author"] = au.group(1)
    desc = re.search(r'"desc"\s*:\s*"((?:[^"\\]|\\.){0,400})"', html)
    if desc:
        try:
            res["title"] = json.loads(f'"{desc.group(1)}"')[:256]
        except ValueError:
            pass
    return res


async def refresh_views(s: AsyncSession, yt_key: str, now: int, force: bool = False,
                        fetch: Fetch = _get) -> dict:
    """Refreshes views of non-rejected videos (at most every 2 hours, unless force). Manual values are left alone."""
    q = select(ContestEntry).where(ContestEntry.contest == CONTEST_ID, ContestEntry.status != "rejected",
                                   ContestEntry.manual.is_(False))
    if not force:
        q = q.where(ContestEntry.views_ms < now - REFRESH_EVERY_MS)
    entries = list((await s.execute(q.limit(300))).scalars())
    stats = {"updated": 0, "failed": 0}
    yt = [e for e in entries if e.platform == "youtube"]
    if yt and yt_key:
        try:
            data = await youtube_stats([e.video_id for e in yt], yt_key, fetch)
        except Exception as ex:  # noqa: BLE001
            log.warning("youtube stats failed: %s", ex)
            data = None
        for e in yt:
            d = (data or {}).get(e.video_id)
            if d is None:
                e.fetch_error = "unavailable" if data is None else "not_found"
                stats["failed"] += 1
                continue
            e.views, e.title, e.author, e.published_ms = d["views"], d["title"], d["author"], d["published_ms"]
            e.views_ms, e.fetch_error = now, None
            stats["updated"] += 1
    for e in (e for e in entries if e.platform == "tiktok"):
        try:
            d = await tiktok_stats(e.url, fetch)
        except Exception as ex:  # noqa: BLE001
            e.fetch_error = str(ex)[:64]
            stats["failed"] += 1
            continue
        e.views, e.views_ms, e.fetch_error = d["views"], now, None
        for k in ("title", "author", "published_ms"):
            if d.get(k):
                setattr(e, k, d[k])
        if d.get("video_id") and e.video_id.startswith("short:"):
            e.video_id, e.url = d["video_id"], d["url"]
        stats["updated"] += 1
    return stats
