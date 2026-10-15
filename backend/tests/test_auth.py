import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from app.telegram_auth import AuthError, parse_ref, validate_init_data

from .conftest import BOT_TOKEN


def sign(fields: dict, token: str = BOT_TOKEN) -> str:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


USER = json.dumps({"id": 42, "first_name": "Ана", "username": "ana", "is_premium": True})


def test_valid_init_data():
    data = sign({"auth_date": "1000", "user": USER, "start_param": "ref_7"})
    u = validate_init_data(data, BOT_TOKEN, max_age=60, now=1030)
    assert (u.id, u.first_name, u.is_premium, u.start_param) == (42, "Ана", True, "ref_7")


def test_bad_signature_and_expired():
    with pytest.raises(AuthError):
        validate_init_data(sign({"auth_date": "1000", "user": USER}, "1:OTHER"), BOT_TOKEN, 60, now=1000)
    with pytest.raises(AuthError):
        validate_init_data(sign({"auth_date": "1000", "user": USER}), BOT_TOKEN, 60, now=2000)


def test_parse_ref():
    assert parse_ref("ref_123") == 123
    assert parse_ref("ref_x") is None and parse_ref(None) is None


async def test_api_requires_auth(client):
    assert (await client.get("/api/me")).status_code == 401
    assert (await client.get("/api/me", headers={"Authorization": "tma garbage"})).status_code == 401
