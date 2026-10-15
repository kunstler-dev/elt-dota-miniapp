"""OpenDota API client: DB cache (od_cache) and a shared request rate gate.

OpenDota free tier: ~60 requests/min and ~2000/day. So all requests are spaced at least
MIN_INTERVAL apart, responses are cached per request type, and on 429/network errors we serve the stale cache."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from ..db import Database
from ..models import OdCache

log = logging.getLogger(__name__)
BASE = "https://api.opendota.com/api"
STEAM64_BASE = 76561197960265728
MIN_INTERVAL = 1.05          # seconds between requests (~57/min)
DAILY_LIMIT = 1800           # soft daily limit (headroom below 2000)

TTL = {"player": 3600, "recent": 600, "heroes": 6 * 3600, "match": 30 * 86400, "match_unparsed": 300,
       "benchmarks": 86400, "heroStats": 12 * 3600, "parsereq": 600, "matchups": 7 * 86400}


class OpenDotaError(Exception):
    """code: rate_limited | unavailable | not_found"""


Fetcher = Callable[[str, str], Awaitable[tuple[int, Any]]]   # (method, path) -> (status, json)


async def http_fetch(method: str, path: str) -> tuple[int, Any]:
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "ELT/2.0 (+https://t.me/ELT_TG)"}) as c:
        r = await c.request(method, BASE + path)
        try:
            data = r.json()
        except ValueError:
            data = None
        return r.status_code, data


def keyed_fetch(api_key: str) -> Fetcher:
    """Requests with an OpenDota key (OPENDOTA_API_KEY): higher limits, pay-as-you-go on opendota.com."""
    async def fetch(method: str, path: str) -> tuple[int, Any]:
        return await http_fetch(method, path + ("&" if "?" in path else "?") + "api_key=" + api_key)
    return fetch


def for_app(app) -> "OpenDota":
    """Shared client for the process: with a key it's faster and has no free-tier daily limit."""
    st = app.state
    if getattr(st, "opendota", None) is None:
        key = st.settings.opendota_api_key
        st.opendota = OpenDota(st.db, keyed_fetch(key), min_interval=0.1, daily_limit=None) if key else OpenDota(st.db)
    return st.opendota


class OpenDota:
    def __init__(self, db: Database, fetch: Fetcher = http_fetch, min_interval: float = MIN_INTERVAL,
                 daily_limit: int | None = DAILY_LIMIT):
        self.db, self.fetch, self.min_interval, self.daily_limit = db, fetch, min_interval, daily_limit
        self._lock = asyncio.Lock()
        self._last = 0.0
        self._day = ""
        self._count = 0

    async def _throttled(self, method: str, path: str) -> tuple[int, Any]:
        async with self._lock:
            day = time.strftime("%Y%m%d")
            if day != self._day:
                self._day, self._count = day, 0
            if self.daily_limit is not None and self._count >= self.daily_limit:
                raise OpenDotaError("rate_limited")
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            self._count += 1
        try:
            return await self.fetch(method, path)
        except (httpx.HTTPError, asyncio.TimeoutError) as e:
            log.warning("OpenDota %s %s failed: %s", method, path, e)
            raise OpenDotaError("unavailable") from e

    async def _cached(self, key: str) -> OdCache | None:
        async with self.db.sessions() as s:
            return await s.get(OdCache, key)

    async def _store(self, key: str, data: str, ttl_s: int) -> None:
        async with self.db.sessions() as s:
            row = await s.get(OdCache, key)
            if row is None:
                s.add(OdCache(key=key, data=data, fetched_ms=_now_ms(), ttl_ms=ttl_s * 1000))
            else:
                row.data, row.fetched_ms, row.ttl_ms = data, _now_ms(), ttl_s * 1000
            await s.commit()

    async def forget(self, *keys: str) -> None:
        async with self.db.sessions() as s:
            for k in keys:
                row = await s.get(OdCache, k)
                if row is not None:
                    await s.delete(row)
            await s.commit()

    async def get(self, key: str, path: str, kind: str) -> Any:
        row = await self._cached(key)
        if row and _now_ms() - row.fetched_ms < row.ttl_ms:
            return json.loads(row.data)
        try:
            status, data = await self._throttled("GET", path)
        except OpenDotaError:
            if row:
                return json.loads(row.data)
            raise
        if status == 429 or status >= 500 or (status == 200 and data is None):
            if row:
                return json.loads(row.data)
            raise OpenDotaError("rate_limited" if status == 429 else "unavailable")
        if status == 404:
            raise OpenDotaError("not_found")
        if status != 200:
            raise OpenDotaError("unavailable")
        await self._store(key, json.dumps(data, ensure_ascii=False), TTL[kind])
        return data

    # ---- endpoints ----
    async def player(self, aid: int) -> dict:
        return await self.get(f"player:{aid}", f"/players/{aid}", "player") or {}

    async def recent(self, aid: int) -> list:
        return await self.get(f"recent:{aid}", f"/players/{aid}/recentMatches", "recent") or []

    async def player_heroes(self, aid: int) -> list:
        return await self.get(f"heroes:{aid}", f"/players/{aid}/heroes?date=180", "heroes") or []

    async def match(self, mid: int) -> dict:
        key = f"match:{mid}"
        d = await self.get(key, f"/matches/{mid}", "match")
        if d and not is_parsed(d):      # an unparsed match is cached briefly while we wait for parsing
            await self._store(key, json.dumps(d, ensure_ascii=False), TTL["match_unparsed"])
        return d or {}

    async def benchmarks(self, hero_id: int) -> dict:
        d = await self.get(f"bench:{hero_id}", f"/benchmarks?hero_id={hero_id}", "benchmarks") or {}
        return d.get("result") or {}

    async def hero_stats(self) -> list:
        return await self.get("heroStats", "/heroStats", "heroStats") or []

    async def hero_matchups(self, hero_id: int) -> list:
        """Hero matchups: [{hero_id, games_played, wins}], for draft duel counters (cached for a week)."""
        return await self.get(f"matchups:{hero_id}", f"/heroes/{hero_id}/matchups", "matchups") or []

    async def request_parse(self, mid: int) -> bool:
        """POST /request/{match_id}: at most once every 10 minutes per match."""
        key = f"parsereq:{mid}"
        row = await self._cached(key)
        if row and _now_ms() - row.fetched_ms < row.ttl_ms:
            return False
        try:
            status, _ = await self._throttled("POST", f"/request/{mid}")
        except OpenDotaError:
            return False
        await self._store(key, "1", TTL["parsereq"])
        return status == 200


def _now_ms() -> int:
    return int(time.time() * 1000)


def is_parsed(match: dict) -> bool:
    return bool(match.get("version")) or any(p.get("lh_t") for p in match.get("players") or [])


def account_id(steamid64: str | int) -> int:
    return int(steamid64) - STEAM64_BASE
