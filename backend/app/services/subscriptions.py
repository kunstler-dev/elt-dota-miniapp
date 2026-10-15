"""Telegram checks for tasks: subscription (getChatMember) and boost (getUserChatBoosts).
The bot must be a channel admin, otherwise Telegram doesn't return the status."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request

log = logging.getLogger("elt.subs")

MEMBER = {"member", "administrator", "creator", "restricted"}


class CheckUnavailable(Exception):
    """Telegram didn't answer / the bot isn't an admin: the result is unknown, decision deferred."""


async def check_member(app: FastAPI, channel: str, user_id: int) -> bool:
    custom = getattr(app.state, "sub_checker", None)
    if custom is not None:
        return await custom(channel, user_id)
    bot = getattr(app.state, "bot", None)
    if bot is None:
        if app.state.settings.dev_auth:  # locally without a bot: treat as subscribed so the UI can be tested
            return True
        raise CheckUnavailable("no bot")
    try:
        m = await bot.get_chat_member(channel, user_id)
    except Exception as e:  # noqa: BLE001
        log.warning("getChatMember %s failed", channel, exc_info=True)
        raise CheckUnavailable(str(e)) from e
    return m.status in MEMBER


async def check_boost(app: FastAPI, channel: str, user_id: int) -> bool:
    custom = getattr(app.state, "boost_checker", None)
    if custom is not None:
        return await custom(channel, user_id)
    bot = getattr(app.state, "bot", None)
    if bot is None:
        if app.state.settings.dev_auth:
            return True
        raise CheckUnavailable("no bot")
    try:
        boosts = await bot.get_user_chat_boosts(channel, user_id)
    except Exception as e:  # noqa: BLE001
        log.warning("getUserChatBoosts %s failed", channel, exc_info=True)
        raise CheckUnavailable(str(e)) from e
    return bool(boosts.boosts)


SUB_RECHECK_MS = 10 * 60 * 1000


async def refresh_required(app: FastAPI, u, now_ms: int, force: bool = False) -> bool:
    """Subscription to the required channel. Ask Telegram at most every 10 minutes (or on a button press).
    If Telegram is unavailable, keep the previous result so subscribers aren't locked out by an outage."""
    channel = app.state.settings.required_channel
    if not channel:
        u.sub_ok = True
        return True
    if not force and u.sub_ok and now_ms - u.sub_checked_ms < SUB_RECHECK_MS:
        return True
    try:
        u.sub_ok = await check_member(app, channel, u.id)
    except CheckUnavailable:
        return bool(u.sub_ok)
    u.sub_checked_ms = now_ms
    return bool(u.sub_ok)


async def task_holds(app: FastAPI, kind: str, channel: str, user_id: int) -> bool:
    """Whether the task condition is met right now."""
    if kind == "subscribe":
        return await check_member(app, channel, user_id)
    if kind == "boost":
        return await check_boost(app, channel, user_id)
    return True


async def is_member(request: Request, channel: str, user_id: int) -> bool:
    try:
        return await check_member(request.app, channel, user_id)
    except CheckUnavailable:
        raise HTTPException(503, "check_unavailable") from None


async def has_boost(request: Request, channel: str, user_id: int) -> bool:
    try:
        return await check_boost(request.app, channel, user_id)
    except CheckUnavailable:
        raise HTTPException(503, "check_unavailable") from None
