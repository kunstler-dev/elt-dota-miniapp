"""Tapper logic without DB or HTTP: everything is computed from server time; the client is not trusted."""

from __future__ import annotations

from ..models import User
from . import arsenal
from . import balance as B
from . import leagues


def max_energy(u: User) -> int:
    return B.ENERGY_BASE + B.ENERGY_PER_LEVEL * (u.energy_level - 1)


def tap_power(u: User) -> int:
    return arsenal.tap_power(u)


def init_new(u: User, now_ms: int) -> None:
    u.tap_level = u.energy_level = 1
    u.coins = u.earned_total = u.profit_per_hour = u.souls = u.daily_streak = 0
    u.ref_count = u.ref_souls = 0
    u.active_hero = "pudge"
    u.energy = max_energy(u)
    u.energy_ms = u.passive_ms = u.last_tap_ms = u.created_ms = now_ms


def earn(u: User, amount: int) -> None:
    u.coins += amount
    u.earned_total += amount
    leagues.add(u, amount)


def regen_energy(u: User, now_ms: int) -> None:
    cap = max_energy(u)
    if u.energy >= cap:
        u.energy, u.energy_ms = cap, now_ms
        return
    gained = (now_ms - u.energy_ms) * B.ENERGY_REGEN_PER_SEC // 1000
    if gained <= 0:
        return
    if u.energy + gained >= cap:
        u.energy, u.energy_ms = cap, now_ms
    else:
        u.energy += gained
        # move the timestamp exactly by the "spent" time so fractions of a second are not lost
        u.energy_ms += gained * 1000 // B.ENERGY_REGEN_PER_SEC


def accrue_passive(u: User, now_ms: int) -> int:
    """Accrues passive income since the last time (at most OFFLINE_CAP_SEC). Returns the amount."""
    if u.profit_per_hour <= 0:
        u.passive_ms = now_ms
        return 0
    elapsed = now_ms - u.passive_ms
    cap_ms = B.OFFLINE_CAP_SEC * 1000
    if elapsed > cap_ms:
        amount = u.profit_per_hour * B.OFFLINE_CAP_SEC // 3600
        u.passive_ms = now_ms
    else:
        amount = u.profit_per_hour * elapsed // 3_600_000
        if amount <= 0:
            return 0
        u.passive_ms += amount * 3_600_000 // u.profit_per_hour
    earn(u, amount)
    return amount


def sync(u: User, now_ms: int) -> None:
    regen_energy(u, now_ms)
    accrue_passive(u, now_ms)


def apply_taps(u: User, requested: int, now_ms: int) -> int:
    """Accepts up to `requested` taps, respecting energy and the rate limit. Returns the accepted count."""
    sync(u, now_ms)
    window = min(max(now_ms - u.last_tap_ms, 0), B.TAP_WINDOW_CAP_SEC * 1000)
    rate_cap = window * B.MAX_TAPS_PER_SEC // 1000 + B.TAP_BURST
    power = tap_power(u)
    taps = max(0, min(requested, rate_cap, u.energy // power))
    u.last_tap_ms = now_ms
    if taps:
        u.energy -= taps * power
        earn(u, taps * power)
    return taps


def league(u: User) -> dict:
    """The player's league: dynamic, by decaying rating (see game/leagues.py)."""
    return leagues.league(u)
