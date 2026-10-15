""""Guess the Hero by 3D silhouette": streaks until the first mistake, difficulty grows, heroes don't repeat
until the player has seen the whole pool. Pool: playable heroes + showcase heroes + guess_pool.json (models/guess/)."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from . import arsenal as A
from .upgrades import CATALOG as SHOWCASE


@dataclass(frozen=True)
class PoolHero:
    id: str
    name: str
    dir: str
    body: str
    items: tuple[str, ...]
    # looks in sets (a full item set, paths relative to dir), from the 3rd hero of a streak
    sets: tuple[tuple[str, ...], ...] = ()


def _load() -> list[PoolHero]:
    pool: dict[str, PoolHero] = {}
    pudge = A.SET_BY_KEY[("pudge", "default")]
    pool["pudge"] = PoolHero("pudge", "Pudge", "/models/pudge/", "pudge.glb",
                             tuple(m for s, m in pudge.models.items() if s != "body"))
    for h in SHOWCASE:
        pool[h.id] = PoolHero(h.id, h.name, h.model_dir, "body.glb", tuple(f"{i}.glb" for i in h.items))
    extra = Path(__file__).with_name("guess_pool.json")
    if extra.exists():
        for hid, h in json.loads(extra.read_text(encoding="utf-8")).items():
            pool[hid] = PoolHero(hid, h["name"], f"/models/guess/{hid}/", "body.glb", tuple(h["items"]))
    looks = Path(__file__).with_name("guess_sets.json")
    if looks.exists():
        for hid, sets in json.loads(looks.read_text(encoding="utf-8")).items():
            if hid in pool:
                h = pool[hid]
                pool[hid] = PoolHero(h.id, h.name, h.dir, h.body, h.items, tuple(tuple(s) for s in sets))
    return list(pool.values())


POOL = _load()
BY_ID = {h.id: h for h in POOL}

MAX_STREAK = 20

# Primary attribute: wrong options come from the same one, similar in silhouette and role, so guessing at random doesn't work
ATTR = {
    "str": {"pudge", "axe", "legion_commander", "earthshaker", "sven", "tiny", "kunkka", "tidehunter", "bristleback",
            "ogre_magi", "dragon_knight"},
    "int": {"crystal_maiden", "lina", "zeus", "storm_spirit", "lion", "lich", "witch_doctor", "queenofpain", "rubick"},
    "uni": {"invoker", "mirana", "windrunner"},
}


def attr(hero_id: str) -> str:
    return next((a for a, ids in ATTR.items() if hero_id in ids), "agi")


def round_params(streak: int) -> dict:
    """Difficulty by streak length: less time, faster rotation, trickier camera angle, more options;
    from the 3rd hero in a random set (unfamiliar silhouette), from the 8th without items (body only)."""
    seconds = max(5, 12 - streak)
    spin = round(0.6 + 0.15 * streak, 2)
    if streak >= 7:
        view = "odd"        # awkward fixed angle (from below/side), almost no rotation
    elif streak >= 5:
        view = "close"      # only the upper body in close-up
    elif streak >= 3:
        view = "high"       # from above
    elif streak >= 1:
        view = "back"       # from behind
    else:
        view = "front"
    return {"seconds": seconds, "spin": spin, "view": view, "choices": 4 if streak < 5 else 6,
            "set": 3 <= streak < 8, "items": streak < 8}


def pick(seen: set[str], exclude: set[str], rng: random.Random, choices: int = 4) -> tuple[PoolHero, list[PoolHero], bool]:
    """A new hero the player hasn't seen yet (whole pool done: start over) + wrong options
    of the same attribute (topped up from the rest if there are not enough)."""
    fresh = [h for h in POOL if h.id not in seen and h.id not in exclude]
    reset = not fresh
    if reset:
        fresh = [h for h in POOL if h.id not in exclude] or POOL
    answer = rng.choice(fresh)
    same = [h for h in POOL if h.id != answer.id and attr(h.id) == attr(answer.id)]
    other = [h for h in POOL if h.id != answer.id and attr(h.id) != attr(answer.id)]
    need = choices - 1
    wrong = rng.sample(same, min(need, len(same)))
    wrong += rng.sample(other, need - len(wrong))
    options = wrong + [answer]
    rng.shuffle(options)
    return answer, options, reset
