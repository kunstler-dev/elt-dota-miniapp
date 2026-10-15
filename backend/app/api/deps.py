from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..telegram_auth import AuthError, TgUser, validate_init_data


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db.sessions() as s:
        yield s


def get_tg_user(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> TgUser:
    """`Authorization: tma <initData>`; locally with DEV_AUTH=1: `tma dev:<id>[:start_param]`."""
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(401, "auth required")
    raw = authorization[4:]
    if settings.dev_auth and raw.startswith("dev:"):
        parts = raw.split(":")
        if not parts[1].isdigit():
            raise HTTPException(401, "bad dev auth")
        return TgUser(id=int(parts[1]), first_name=f"dev{parts[1]}", username=f"dev{parts[1]}",
                      start_param=parts[2] if len(parts) > 2 else None)
    try:
        return validate_init_data(raw, settings.bot_token, settings.init_data_max_age)
    except AuthError as e:
        raise HTTPException(401, str(e)) from e


def get_admin(settings: Annotated[Settings, Depends(get_settings)],
              tg: Annotated[TgUser, Depends(get_tg_user)]) -> TgUser:
    if tg.id not in settings.admin_id_set:
        raise HTTPException(403, "admin_only")
    return tg


Session = Annotated[AsyncSession, Depends(get_session)]
CurrentTg = Annotated[TgUser, Depends(get_tg_user)]
AdminTg = Annotated[TgUser, Depends(get_admin)]
