from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Ledger, User

# Earnings that inviters get a share of (referral payouts themselves are not shared further)
SHAREABLE = {"task", "weekly_top", "guild", "draft_top", "guild_war"}


def change(s: AsyncSession, u: User, amount: int, reason: str, ref: str | None, now_ms: int,
           allow_debt: bool = False) -> None:
    """The only way to change souls: balance + ledger entry in the same transaction.
    allow_debt is only for charge-backs of revoked tasks: the balance may go negative and is paid off by future souls."""
    if u.souls + amount < 0 and not allow_debt:
        raise ValueError("not_enough_souls")
    u.souls += amount
    s.add(Ledger(user_id=u.id, amount=amount, reason=reason, ref=ref, created_ms=now_ms))


async def earn(s: AsyncSession, u: User, amount: int, reason: str, ref: str | None, now_ms: int) -> None:
    """Credit the player + a share to their inviters (levels 1 and 2)."""
    change(s, u, amount, reason, ref, now_ms)
    if reason in SHAREABLE:
        from .referrals import share
        await share(s, u, amount, now_ms)
