"""Hero data for the draft duel from OpenDota: roles, attack type, attribute, high-rank win rate, matchups.

Loaded by a background job (~2 min the first time because of the OpenDota rate limit, then from the od_cache)
and kept in memory (app.state.draft_data). Until loaded, the draft answers 503 draft_data_loading."""

from __future__ import annotations

import asyncio
import logging

from ..game.draft import Data, Hero
from .opendota import OpenDota, OpenDotaError

log = logging.getLogger("elt.draft")

CDN = "https://cdn.cloudflare.steamstatic.com"
ATTR = {"str": "str", "agi": "agi", "int": "int", "all": "all"}


def hero_from_stats(h: dict) -> Hero | None:
    # high rank: Divine (7); for Immortal/Titan (8) OpenDota often returns empty statistics
    for b in (7, 6, 5):
        p, w = h.get(f"{b}_pick") or 0, h.get(f"{b}_win") or 0
        if p >= 200:
            break
    else:
        p, w = h.get("pub_pick") or 0, h.get("pub_win") or 0
    if not h.get("id") or p <= 0:
        return None
    img = h.get("img") or ""
    return Hero(id=int(h["id"]), name=h.get("localized_name") or str(h["id"]), roles=frozenset(h.get("roles") or []),
                attack=h.get("attack_type") or "Melee", attr=ATTR.get(h.get("primary_attr"), "all"),
                winrate=round(w / p, 4), img=(CDN + img.split("?")[0]) if img else "")


async def load(od: OpenDota) -> Data:
    stats = await od.hero_stats()
    heroes = {x.id: x for x in (hero_from_stats(h) for h in stats) if x}
    matchups: dict[tuple[int, int], tuple[int, int]] = {}
    for hid in heroes:
        rows: list = []
        for attempt in range(4):
            try:
                rows = await od.hero_matchups(hid)
                break
            except OpenDotaError as e:
                if str(e) != "rate_limited" or attempt == 3:
                    log.warning("matchups %s: %s", hid, e)  # without a hero's matchups there are no counters for it
                    break
                await asyncio.sleep(30 * (attempt + 1))     # OpenDota per-minute rate limit: wait and retry
            except Exception as e:  # noqa: BLE001
                log.warning("matchups %s: %s", hid, e)
                break
        for r in rows:
            other = r.get("hero_id")
            if other in heroes:
                matchups[(hid, other)] = (int(r.get("games_played") or 0), int(r.get("wins") or 0))
    log.info("draft data: %s heroes, %s matchups", len(heroes), len(matchups))
    return Data(heroes=heroes, matchups=matchups)
