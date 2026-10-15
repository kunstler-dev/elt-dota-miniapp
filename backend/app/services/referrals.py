"""Referrals in souls: a one-time bonus per counted friend and an ongoing share of their souls (2 levels)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..game import balance as B
from ..models import SteamAccount, User
from . import souls
from .users import get_for_update


async def confirm_if_ready(s: AsyncSession, friend_id: int, now_ms: int) -> bool:
    """Counts a friend once they link Steam and pass the check. Paid exactly once."""
    friend = await get_for_update(s, friend_id)
    if friend is None or friend.referrer_id is None or friend.ref_confirmed_ms is not None:
        return False
    acc = await s.get(SteamAccount, friend_id)
    if acc is None or not acc.passed:
        return False
    referrer = await get_for_update(s, friend.referrer_id)
    if referrer is None:
        return False
    friend.ref_confirmed_ms = now_ms
    bonus = B.REF_BONUS_PREMIUM if friend.is_premium else B.REF_BONUS
    souls.change(s, referrer, bonus, "ref_bonus", str(friend.id), now_ms)
    referrer.ref_count += 1
    referrer.ref_souls += bonus
    if B.REF_WELCOME:
        souls.change(s, friend, B.REF_WELCOME, "ref_welcome", str(referrer.id), now_ms)
    return True


async def share(s: AsyncSession, earner: User, amount: int, now_ms: int) -> None:
    """Share for the inviter (and the inviter's inviter) of souls earned by a counted friend."""
    child, levels = earner, ((B.REF_SHARE_L1, "ref_share"), (B.REF_SHARE_L2, "ref_share_l2"))
    for pct, reason in levels:
        if child.referrer_id is None or child.ref_confirmed_ms is None:
            return
        parent = await get_for_update(s, child.referrer_id)
        if parent is None:
            return
        cut = int(amount * pct)
        if cut > 0:
            souls.change(s, parent, cut, reason, str(earner.id), now_ms)
            parent.ref_souls += cut
        child = parent
