"""Analysis of the last Dota 2 match (OpenDota) + Telegram Stars subscription; admin settings for analysis."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..models import SteamAccount
from ..services import dota_analysis as an
from ..services import stars
from ..services.opendota import OpenDota, OpenDotaError, account_id, for_app, is_parsed
from ..services.users import now_ms
from .deps import AdminTg, CurrentTg, Session
from .routes import require_access

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

REFRESH_EVERY_S = 120
PRIVATE_HELP = ("Профиль Dota 2 закрыт — OpenDota не видит твои матчи. Включи в игре: "
                "Dota 2 → Настройки → Социальные (Social) → «Открыть публичный доступ к данным матчей» "
                "(Expose Public Match Data). Затем сыграй 1 матч и нажми «Обновить» через 10–15 минут.")
OD_ERR = {"rate_limited": "OpenDota сейчас перегружен (лимит запросов). Попробуй через минуту.",
          "unavailable": "OpenDota временно недоступен. Попробуй позже.", "not_found": "Матч не найден на OpenDota."}


def opendota(request: Request) -> OpenDota:
    return for_app(request.app)


def _od_error(e: OpenDotaError) -> JSONResponse:
    return JSONResponse({"detail": str(e), "message": OD_ERR.get(str(e), "Ошибка OpenDota")}, status_code=503)


def _preview(recent: list, heroes: dict) -> dict | None:
    if not recent:
        return None
    m = recent[0]
    return {"match_id": m.get("match_id"), "hero": an.hero_name(heroes, m.get("hero_id")),
            "hero_img": an.hero_img(heroes, m.get("hero_id")), "win": an.won(m), "kills": m.get("kills"),
            "deaths": m.get("deaths"), "assists": m.get("assists"), "duration": an.mmss(m.get("duration")),
            "gpm": m.get("gold_per_min"), "xpm": m.get("xp_per_min")}


async def _aid(s: Session, uid: int) -> int:
    await require_access(s, uid)
    acc = await s.get(SteamAccount, uid)
    return account_id(acc.steam_id)


def _pay(acc: dict) -> dict:
    return {k: acc[k] for k in ("mode", "beta", "price", "free_left", "free_per_week", "next_free_ms", "subscription")}


@router.get("/analysis")
async def analysis(request: Request, tg: CurrentTg, s: Session, refresh: bool = False):
    cfg = request.app.state.settings
    aid = await _aid(s, tg.id)
    od = opendota(request)
    if refresh:
        last = getattr(request.app.state, "analysis_refresh", None)
        if last is None:
            last = request.app.state.analysis_refresh = {}
        if time.time() - last.get(tg.id, 0) < REFRESH_EVERY_S:
            raise HTTPException(429, "too_often")
        last[tg.id] = time.time()
        await od.forget(f"recent:{aid}", f"player:{aid}")
    now = now_ms()
    try:
        player = await od.player(aid)
        recent = await od.recent(aid)
        if not player.get("profile") or not recent:
            return {"status": "private", "message": PRIVATE_HELP, "pay": _pay(await stars.access(s, cfg, tg.id, None, now))}
        hero_stats = await od.hero_stats()
        heroes = an.hero_index(hero_stats)
        mid = recent[0].get("match_id")
        acc = await stars.access(s, cfg, tg.id, mid, now)
        if not acc["full"]:
            return {"status": "locked", "preview": _preview(recent, heroes), "pay": _pay(acc)}
        match = await od.match(mid)
        parsed = is_parsed(match)
        parse_requested = False if parsed else await od.request_parse(mid)
        me = an.find_me(match, aid) or {}
        bench = await od.benchmarks(me.get("hero_id") or recent[0].get("hero_id"))
        ph = await od.player_heroes(aid)
    except OpenDotaError as e:
        return _od_error(e)
    report = an.build_report(aid=aid, player=player, recent=recent, match=match, bench=bench,
                             hero_stats=hero_stats, player_heroes=ph)
    await stars.consume(s, tg.id, mid, now)
    await s.flush()
    acc = await stars.access(s, cfg, tg.id, mid, now)
    await s.commit()
    return {"status": "ok", "report": report, "parsed": parsed, "parse_requested": parse_requested, "pay": _pay(acc)}


@router.post("/analysis/parse")
async def request_parse(request: Request, tg: CurrentTg, s: Session):
    aid = await _aid(s, tg.id)
    od = opendota(request)
    try:
        recent = await od.recent(aid)
    except OpenDotaError as e:
        return _od_error(e)
    if not recent:
        raise HTTPException(400, "private")
    mid = recent[0]["match_id"]
    ok = await od.request_parse(mid)
    await od.forget(f"match:{mid}")
    return {"ok": True, "requested": ok, "match_id": mid}


@router.post("/analysis/invoice")
async def invoice(request: Request, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    st = await stars.settings(s, request.app.state.settings)
    if st["beta_free"]:
        raise HTTPException(400, "beta")
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(503, "bot_unavailable")
    try:
        link = await stars.create_invoice_link(bot, st["price"], tg.id)
    except Exception as e:  # noqa: BLE001
        log.exception("createInvoiceLink failed")
        raise HTTPException(502, "invoice_failed") from e
    return {"url": link, "price": st["price"]}


# ---------------- admin ----------------
class AnalysisSettingsIn(BaseModel):
    beta_free: bool | None = None
    price: int | None = Field(default=None)


class RefundIn(BaseModel):
    charge_id: str = Field(min_length=1, max_length=128)


@router.get("/admin/analysis")
async def admin_state(request: Request, _: AdminTg, s: Session) -> dict:
    return {"settings": await stars.settings(s, request.app.state.settings),
            "subscribers": await stars.subscribers(s, now_ms()), "payments": await stars.payments(s)}


@router.post("/admin/analysis/settings")
async def admin_settings(request: Request, body: AnalysisSettingsIn, _: AdminTg, s: Session) -> dict:
    try:
        st = await stars.update_settings(s, request.app.state.settings, body.beta_free, body.price)
    except ValueError as e:
        raise HTTPException(400, "bad_price") from e
    await s.commit()
    return {"ok": True, "settings": st}


@router.post("/admin/analysis/refund")
async def admin_refund(request: Request, body: RefundIn, _: AdminTg, s: Session) -> dict:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(503, "bot_unavailable")
    try:
        r = await stars.refund(bot, s, body.charge_id, now_ms())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "refund_failed") from e
    await s.commit()
    return r
