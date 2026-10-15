"""Steam linking: the Mini App gets a one-time link -> browser -> Steam sign-in -> the callback links the account."""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from ..config import Settings
from ..models import SteamAccount
from ..services import referrals, steam_link
from ..services.users import get_or_create, now_ms
from ..steam.checker import SteamChecker, Thresholds
from ..steam.openid import auth_url, verify_assertion
from .deps import CurrentTg, Session

log = logging.getLogger("elt.steam")
router = APIRouter()


def _base(request: Request) -> str:
    s: Settings = request.app.state.settings
    return (s.webapp_url or str(request.base_url)).rstrip("/")


def _thresholds(s: Settings) -> Thresholds:
    return Thresholds(s.steam_min_age_days, s.steam_min_dota_hours, s.steam_min_opendota_matches)


def _checker(request: Request) -> SteamChecker:
    return getattr(request.app.state, "steam_checker", None) or SteamChecker(request.app.state.settings.steam_api_key)


async def run_check(request: Request, s: Session, acc: SteamAccount) -> None:
    try:
        chk = await _checker(request).check(acc.steam_id, _thresholds(request.app.state.settings))
    except Exception:  # noqa: BLE001 — Steam/OpenDota network errors must not break linking
        log.exception("steam check failed for %s", acc.steam_id)
        return
    steam_link.apply_check(acc, chk, now_ms())


@router.get("/api/steam")
async def steam_status(tg: CurrentTg, s: Session) -> dict:
    return {"steam": steam_link.status(await s.get(SteamAccount, tg.id))}


@router.post("/api/steam/link")
async def steam_link_start(request: Request, tg: CurrentTg, s: Session) -> dict:
    await get_or_create(s, tg)
    token = await steam_link.new_token(s, tg.id, now_ms())
    await s.commit()
    return {"url": f"{_base(request)}/auth/steam/start?t={token}"}


RECHECK_COOLDOWN_MS = 10 * 60 * 1000


@router.post("/api/steam/recheck")
async def steam_recheck(request: Request, tg: CurrentTg, s: Session) -> dict:
    """Repeat the anti-bot check (profile made public, more hours played). At most once every 10 minutes."""
    acc = await s.get(SteamAccount, tg.id)
    if acc is None:
        raise HTTPException(404, "not_linked")
    now = now_ms()
    if acc.passed:
        return {"steam": steam_link.status(acc)}
    if acc.checked_ms and now - acc.checked_ms < RECHECK_COOLDOWN_MS:
        raise HTTPException(429, "too_often")
    await run_check(request, s, acc)
    await referrals.confirm_if_ready(s, tg.id, now)
    await s.commit()
    return {"steam": steam_link.status(acc)}


class DevLinkIn(BaseModel):
    steam_id: str = Field(pattern=r"^7656119\d{10}$")


@router.post("/api/steam/dev-link", include_in_schema=False)
async def steam_dev_link(body: DevLinkIn, request: Request, tg: CurrentTg, s: Session) -> dict:
    """Local only (DEV_AUTH=1): link Steam without signing in on the Steam website, to test the UI."""
    if not request.app.state.settings.dev_auth:
        raise HTTPException(404)
    await get_or_create(s, tg)
    result = await steam_link.link(s, tg.id, body.steam_id, now_ms())
    if result != "ok":
        raise HTTPException(409, result)
    acc = await s.get(SteamAccount, tg.id)
    assert acc is not None
    await run_check(request, s, acc)
    await referrals.confirm_if_ready(s, tg.id, now_ms())
    await s.commit()
    return {"steam": steam_link.status(acc)}


@router.get("/auth/steam/start", include_in_schema=False)
async def steam_start(t: str, request: Request, s: Session):
    if await steam_link.token_owner(s, t, now_ms()) is None:
        return _page(request, False, "Ссылка устарела. Вернитесь в приложение и нажмите «Войти через Steam» ещё раз.")
    base = _base(request)
    return RedirectResponse(auth_url(f"{base}/auth/steam/callback?t={t}", base))


@router.get("/auth/steam/callback", include_in_schema=False)
async def steam_callback(t: str, request: Request, s: Session):
    now = now_ms()
    user_id = await steam_link.token_owner(s, t, now)
    if user_id is None:
        return _page(request, False, "Ссылка устарела. Вернитесь в приложение и попробуйте ещё раз.")
    steam_id = await verify_assertion(dict(request.query_params), f"{_base(request)}/auth/steam/callback?t={t}")
    if steam_id is None:
        return _page(request, False, "Steam не подтвердил вход. Попробуйте ещё раз.")
    result = await steam_link.link(s, user_id, steam_id, now)
    if result == "taken":
        return _page(request, False, "Этот Steam-аккаунт уже привязан к другому Telegram. Один Steam — один игрок.")
    if result == "other_linked":
        return _page(request, False, "К вашему Telegram уже привязан другой Steam-аккаунт.")
    tok = await s.get(steam_link.SteamLinkToken, t)
    if tok is not None:
        await s.delete(tok)
    acc = await s.get(SteamAccount, user_id)
    assert acc is not None
    await run_check(request, s, acc)
    await referrals.confirm_if_ready(s, user_id, now_ms())
    await s.commit()
    return _page(request, True, "Steam привязан. Возвращайтесь в Telegram — игра уже ждёт.")


def _page(request: Request, ok: bool, text: str) -> HTMLResponse:
    bot = getattr(request.app.state, "bot_username", None)
    back = f'<a class="btn" href="https://t.me/{html.escape(bot)}">Вернуться в Telegram</a>' if bot else ""
    mark = "&#10003;" if ok else "!"
    color = "#4ADE80" if ok else "#D4252F"
    body = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>ELT · Steam</title>
<style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#07090D;
color:#F2F5F8;font-family:system-ui,sans-serif;padding:24px;box-sizing:border-box}}
.card{{max-width:360px;text-align:center;display:flex;flex-direction:column;gap:16px;align-items:center}}
.mark{{width:64px;height:64px;border-radius:32px;border:3px solid {color};color:{color};font-size:32px;
display:flex;align-items:center;justify-content:center;font-weight:800}}
p{{margin:0;font-size:16px;line-height:1.5}}.btn{{display:block;padding:14px 22px;border-radius:14px;background:#D4252F;
color:#fff;text-decoration:none;font-weight:800}}</style></head>
<body><div class="card"><div class="mark">{mark}</div><p>{html.escape(text)}</p>{back}</div></body></html>"""
    return HTMLResponse(body, status_code=200 if ok else 400)
