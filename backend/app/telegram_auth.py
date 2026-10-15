"""Validation of Telegram Mini App initData (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class AuthError(Exception):
    pass


@dataclass
class TgUser:
    id: int
    first_name: str = ""
    username: str | None = None
    language: str | None = None
    is_premium: bool = False
    start_param: str | None = None
    photo_url: str | None = None


def validate_init_data(init_data: str, bot_token: str, max_age: int, now: float | None = None) -> TgUser:
    if not bot_token:
        raise AuthError("bot token is not configured")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received = pairs.pop("hash", None)
    if not received:
        raise AuthError("no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("bad signature")
    auth_date = int(pairs.get("auth_date", "0"))
    if max_age and (now or time.time()) - auth_date > max_age:
        raise AuthError("init data expired")
    try:
        raw = json.loads(pairs["user"])
    except (KeyError, ValueError) as e:
        raise AuthError("no user") from e
    return TgUser(
        id=int(raw["id"]),
        first_name=raw.get("first_name", ""),
        username=raw.get("username"),
        language=raw.get("language_code"),
        is_premium=bool(raw.get("is_premium")),
        start_param=pairs.get("start_param"),
        photo_url=raw.get("photo_url"),
    )


def parse_ref(start_param: str | None) -> int | None:
    """`ref_<telegram id>` -> inviter id."""
    if start_param and start_param.startswith("ref_") and start_param[4:].isdigit():
        return int(start_param[4:])
    return None
