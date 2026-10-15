"""Match analysis subscription via Telegram Stars (XTR) + a free weekly limit + beta mode.

Defaults come from the environment (ANALYSIS_*); an admin overrides them in app_settings.
Stars go to the bot balance (@BotFather -> bot -> Balance), withdrawals via Fragment."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import AnalysisSub, AnalysisUsage, AppSetting, StarPayment, User

PERIOD_S = 2592000             # 30 days is the only period Telegram allows for subscriptions
PAYLOAD = "analysis_sub"
WEEK_MS = 7 * 86400 * 1000


async def settings(s: AsyncSession, cfg: Settings) -> dict:
    rows = {r.key: r.value for r in (await s.execute(select(AppSetting).where(
        AppSetting.key.in_(("analysis_beta_free", "analysis_price"))))).scalars()}
    beta, price = rows.get("analysis_beta_free"), rows.get("analysis_price")
    return {"beta_free": cfg.analysis_beta_free if beta is None else beta == "1",
            "price": int(price) if price else cfg.analysis_price_stars, "free_per_week": cfg.analysis_free_per_week}


async def _put(s: AsyncSession, key: str, value: str) -> None:
    row = await s.get(AppSetting, key)
    if row is None:
        s.add(AppSetting(key=key, value=value))
    else:
        row.value = value


async def update_settings(s: AsyncSession, cfg: Settings, beta_free: bool | None = None,
                          price: int | None = None) -> dict:
    if price is not None and not 1 <= int(price) <= 10000:        # Telegram limit for subscriptions is 10000 Stars
        raise ValueError("bad_price")
    if beta_free is not None:
        await _put(s, "analysis_beta_free", "1" if beta_free else "0")
    if price is not None:
        await _put(s, "analysis_price", str(int(price)))
    await s.flush()
    return await settings(s, cfg)


def sub_out(sub: AnalysisSub | None, now: int) -> dict | None:
    if sub is None:
        return None
    return {"active": sub.expires_ms > now, "expires_ms": sub.expires_ms, "recurring": sub.recurring,
            "cancelled": sub.cancelled}


async def access(s: AsyncSession, cfg: Settings, uid: int, match_id: int | None, now: int) -> dict:
    """Whether the full analysis can be shown. Re-viewing an already opened match doesn't use the limit."""
    st = await settings(s, cfg)
    sub = await s.get(AnalysisSub, uid)
    since = now - WEEK_MS
    used = (await s.execute(select(func.count()).select_from(AnalysisUsage).where(
        AnalysisUsage.user_id == uid, AnalysisUsage.ts_ms > since))).scalar() or 0
    seen = False
    if match_id:
        u = await s.get(AnalysisUsage, (uid, match_id))
        seen = u is not None and u.ts_ms > since
    if st["beta_free"]:
        mode = "beta"
    elif sub is not None and sub.expires_ms > now:
        mode = "sub"
    elif seen or used < st["free_per_week"]:
        mode = "free"
    else:
        mode = "locked"
    nxt = None
    if mode == "locked":
        first = (await s.execute(select(func.min(AnalysisUsage.ts_ms)).where(
            AnalysisUsage.user_id == uid, AnalysisUsage.ts_ms > since))).scalar()
        nxt = first + WEEK_MS if first else None
    return {"mode": mode, "full": mode != "locked", "free_left": max(0, st["free_per_week"] - used),
            "free_per_week": st["free_per_week"], "next_free_ms": nxt, "price": st["price"],
            "beta": st["beta_free"], "subscription": sub_out(sub, now)}


async def consume(s: AsyncSession, uid: int, match_id: int, now: int) -> None:
    row = await s.get(AnalysisUsage, (uid, match_id))
    if row is None:
        s.add(AnalysisUsage(user_id=uid, match_id=match_id, ts_ms=now))
    elif row.ts_ms <= now - WEEK_MS:      # same match, but opened more than a week ago: counts as a new analysis
        row.ts_ms = now


def make_payload(uid: int) -> str:
    return f"{PAYLOAD}:{uid}"


def parse_payload(payload: str) -> int | None:
    a, _, b = (payload or "").partition(":")
    return int(b) if a == PAYLOAD and b.isdigit() else None


async def create_invoice_link(bot, price: int, uid: int) -> str:
    from aiogram.types import LabeledPrice
    return await bot.create_invoice_link(
        title="ELT Анализ — 30 дней", description="Полный разбор матчей, ошибки, тренды, позиция и герои под твой ранг",
        payload=make_payload(uid), currency="XTR", prices=[LabeledPrice(label="Подписка 30 дней", amount=price)],
        subscription_period=PERIOD_S, provider_token="")


def validate_pre_checkout(uid: int, payload: str, currency: str, amount: int) -> str | None:
    """None if payment can proceed, otherwise an error message for the user."""
    if currency != "XTR" or parse_payload(payload) != uid:
        return "Счёт недействителен. Открой оплату заново из приложения."
    if amount <= 0:
        return "Неверная сумма."
    return None


async def record_payment(s: AsyncSession, uid: int, charge_id: str, amount: int, payload: str,
                         expires_s: int | None, recurring: bool, now: int) -> AnalysisSub | None:
    """successful_payment (first payment and every renewal). Idempotent by charge_id."""
    if await s.get(StarPayment, charge_id) is not None:
        return await s.get(AnalysisSub, uid)
    sub = await s.get(AnalysisSub, uid, with_for_update=True)
    base = max(now, sub.expires_ms) if sub else now
    exp = int(expires_s) * 1000 if expires_s else base + PERIOD_S * 1000
    s.add(StarPayment(charge_id=charge_id, user_id=uid, amount=amount, payload=payload, recurring=recurring,
                      expires_ms=exp, created_ms=now))
    if sub is None:
        sub = AnalysisSub(user_id=uid, expires_ms=exp, charge_id=charge_id, recurring=recurring, cancelled=False,
                          started_ms=now, updated_ms=now)
        s.add(sub)
    else:
        sub.expires_ms, sub.charge_id, sub.recurring, sub.cancelled, sub.updated_ms = exp, charge_id, recurring, False, now
    await s.flush()
    return sub


async def mark_refunded(s: AsyncSession, charge_id: str, now: int) -> StarPayment | None:
    p = await s.get(StarPayment, charge_id)
    if p is None or p.refunded_ms:
        return None
    p.refunded_ms = now
    sub = await s.get(AnalysisSub, p.user_id)
    if sub is not None and sub.charge_id == charge_id:
        sub.expires_ms, sub.cancelled, sub.updated_ms = now, True, now
    await s.flush()
    return p


async def refund(bot, s: AsyncSession, charge_id: str, now: int) -> dict:
    """Stars refund (refundStarPayment), admins only. Raises ValueError(not_found|already_refunded)."""
    p = await s.get(StarPayment, charge_id)
    if p is None:
        raise ValueError("not_found")
    if p.refunded_ms:
        raise ValueError("already_refunded")
    await bot.refund_star_payment(user_id=p.user_id, telegram_payment_charge_id=charge_id)
    await mark_refunded(s, charge_id, now)
    return {"ok": True, "user_id": p.user_id, "amount": p.amount}


async def subscribers(s: AsyncSession, now: int, limit: int = 200) -> list[dict]:
    paid = (select(func.coalesce(func.sum(StarPayment.amount), 0)).where(
        StarPayment.user_id == AnalysisSub.user_id, StarPayment.refunded_ms.is_(None)).scalar_subquery())
    rows = (await s.execute(select(AnalysisSub, User.username, User.first_name, paid)
                            .join(User, User.id == AnalysisSub.user_id, isouter=True)
                            .order_by(AnalysisSub.expires_ms.desc()).limit(limit))).all()
    return [{"user_id": sub.user_id, "name": f"@{un}" if un else (fn or str(sub.user_id)),
             "expires_ms": sub.expires_ms, "active": sub.expires_ms > now, "recurring": sub.recurring,
             "cancelled": sub.cancelled, "charge_id": sub.charge_id, "paid": int(p or 0)}
            for sub, un, fn, p in rows]


async def payments(s: AsyncSession, limit: int = 50) -> list[dict]:
    rows = (await s.execute(select(StarPayment).order_by(StarPayment.created_ms.desc()).limit(limit))).scalars()
    return [{"charge_id": p.charge_id, "user_id": p.user_id, "amount": p.amount, "recurring": p.recurring,
             "created_ms": p.created_ms, "refunded_ms": p.refunded_ms} for p in rows]
