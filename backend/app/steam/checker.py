"""Anti-bot check of a Steam account: age, public profile, Dota 2 play (Steam hours or OpenDota matches).

With STEAM_API_KEY: GetPlayerSummaries/GetOwnedGames; without a key: the Steam XML profile. Matches come from OpenDota."""

from __future__ import annotations

import html
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from .openid import UA

STEAM64_BASE = 76561197960265728
DOTA_APPID = 570

GetJson = Callable[[str, dict], Awaitable[Any]]
GetText = Callable[[str], Awaitable[str]]


@dataclass
class Thresholds:
    min_age_days: int = 180
    min_hours: int = 100
    min_matches: int = 100


async def _get_json(url: str, params: dict) -> Any:
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=15) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def _get_text(url: str) -> str:
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=15, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.text


def _xml_field(x: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</{tag}>", x, re.S)
    return html.unescape(m.group(1).strip()) if m else None


class SteamChecker:
    def __init__(self, api_key: str = "", get_json: GetJson = _get_json, get_text: GetText = _get_text):
        self.api_key = api_key
        self.get_json, self.get_text = get_json, get_text

    async def check(self, steam_id: str, th: Thresholds, now: float | None = None) -> dict:
        now = now or time.time()
        info: dict[str, Any] = {"public": None, "created": None, "age_days": None, "dota_hours": None,
                                "od_matches": None, "persona": None, "avatar": None}
        if self.api_key:
            try:
                d = await self.get_json("https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                                        {"key": self.api_key, "steamids": steam_id})
                pl = (d.get("response", {}).get("players") or [{}])[0]
                info["public"] = pl.get("communityvisibilitystate") == 3
                info["created"] = pl.get("timecreated")
                info["persona"] = pl.get("personaname")
                info["avatar"] = pl.get("avatarfull")
                g = await self.get_json("https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
                                        {"key": self.api_key, "steamid": steam_id, "include_played_free_games": 1,
                                         "appids_filter[0]": DOTA_APPID})
                games = g.get("response", {}).get("games") or []
                mins = next((x.get("playtime_forever", 0) for x in games if x.get("appid") == DOTA_APPID), None)
                info["dota_hours"] = None if mins is None else round(mins / 60, 1)
            except Exception:  # noqa: BLE001 — fall back to XML
                pass
        if info["public"] is None or info["created"] is None or info["persona"] is None:
            try:
                x = await self.get_text(f"https://steamcommunity.com/profiles/{steam_id}/?xml=1")
                if info["public"] is None:
                    info["public"] = _xml_field(x, "privacyState") == "public"
                info["persona"] = info["persona"] or _xml_field(x, "steamID")
                info["avatar"] = info["avatar"] or _xml_field(x, "avatarFull")
                since = _xml_field(x, "memberSince")
                if since and info["created"] is None:
                    for fmt in ("%B %d, %Y", "%d %B, %Y", "%B %d %Y"):
                        try:
                            info["created"] = int(datetime.strptime(since, fmt).timestamp())
                            break
                        except ValueError:
                            continue
            except Exception:  # noqa: BLE001
                pass
        try:
            wl = await self.get_json(f"https://api.opendota.com/api/players/{int(steam_id) - STEAM64_BASE}/wl", {})
            info["od_matches"] = int(wl.get("win", 0)) + int(wl.get("lose", 0))
        except Exception:  # noqa: BLE001
            pass
        if info["created"]:
            info["age_days"] = int((now - info["created"]) // 86400)
        ok_age = info["age_days"] is not None and info["age_days"] >= th.min_age_days
        ok_play = (info["dota_hours"] or 0) >= th.min_hours or (info["od_matches"] or 0) >= th.min_matches
        reasons = [r for r, ok in (("private", bool(info["public"])), ("young", ok_age), ("low_dota", ok_play)) if not ok]
        return {**info, "passed": not reasons, "reasons": reasons}
