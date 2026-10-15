"""Dynamic leagues: rating = ELT earned with exponential decay, league by percentile.

Thresholds (how much rating a league needs right now) are recomputed by a background job over all players;
between recomputations the last thresholds are used. Without a recomputation, the minimum thresholds from balance apply."""

from __future__ import annotations

import time

from ..models import User
from . import balance as B

# Current league thresholds: CUTOFFS[i] is the rating where league i starts (CUTOFFS[0] = 0)
CUTOFFS: list[int] = [m for _, _, m in B.LEAGUE_TABLE]


def decayed(score: int, since_ms: int, now_ms: int) -> float:
    if score <= 0 or since_ms <= 0:
        return float(max(score, 0))
    return score * 0.5 ** (max(0, now_ms - since_ms) / B.LEAGUE_HALF_LIFE_MS)


def rating(u: User, now_ms: int | None = None) -> int:
    return int(decayed(u.league_score or 0, u.league_ms or 0, now_ms or int(time.time() * 1000)))


def add(u: User, amount: int, now_ms: int | None = None) -> None:
    """Earnings go into the league rating (old rating decays up to now, then we add)."""
    if amount <= 0:
        return
    now = now_ms or int(time.time() * 1000)
    u.league_score = int(decayed(u.league_score or 0, u.league_ms or 0, now)) + amount
    u.league_ms = now


def recompute(ratings: list[int]) -> list[int]:
    """Percentile thresholds among players with rating > 0 (never below the minimums)."""
    xs = sorted((r for r in ratings if r > 0), reverse=True)
    cut = [0]
    for _, share, minimum in B.LEAGUE_TABLE[1:]:
        if xs:
            k = max(1, int(len(xs) * share))       # top `share` of players
            cut.append(max(minimum, xs[min(k, len(xs)) - 1]))
        else:
            cut.append(minimum)
    for i in range(1, len(cut)):                    # thresholds never decrease
        cut[i] = max(cut[i], cut[i - 1])
    CUTOFFS[:] = cut
    return cut


def league(u: User, now_ms: int | None = None) -> dict:
    r = rating(u, now_ms)
    idx = max(i for i, c in enumerate(CUTOFFS) if r >= c)
    name = B.LEAGUE_TABLE[idx][0]
    nxt = idx + 1 if idx + 1 < len(CUTOFFS) else None
    if nxt is None:
        progress = 1.0
    else:
        lo, hi = CUTOFFS[idx], CUTOFFS[nxt]
        progress = (r - lo) / (hi - lo) if hi > lo else 1.0
    return {"index": idx, "name": name, "next": B.LEAGUE_TABLE[nxt][0] if nxt else None,
            "next_at": CUTOFFS[nxt] if nxt else None, "progress": round(min(max(progress, 0.0), 1.0), 4),
            "rating": r}
