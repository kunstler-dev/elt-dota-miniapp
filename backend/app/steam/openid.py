"""Steam sign-in (OpenID 2.0). Steam itself verifies the signature (check_authentication), so the ID can't be forged."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

import httpx

OPENID = "https://steamcommunity.com/openid/login"
NS = "http://specs.openid.net/auth/2.0"
CLAIMED_RE = re.compile(r"^https://steamcommunity\.com/openid/id/(7656119\d{10})$")
UA = "ELT/2.0 (+https://t.me/ELT_TG)"

Post = Callable[[str, dict], Awaitable[str]]


def auth_url(return_to: str, realm: str) -> str:
    return OPENID + "?" + urlencode({
        "openid.ns": NS, "openid.mode": "checkid_setup", "openid.return_to": return_to, "openid.realm": realm,
        "openid.identity": NS + "/identifier_select", "openid.claimed_id": NS + "/identifier_select"})


async def _post(url: str, data: dict) -> str:
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=15) as c:
        r = await c.post(url, data=data)
        return r.text


async def verify_assertion(params: dict, return_to: str, post: Post = _post) -> str | None:
    """Validates Steam's response: required fields + check_authentication with Steam itself. Returns steamid64."""
    p = {k: v for k, v in params.items() if k.startswith("openid.")}
    if p.get("openid.mode") != "id_res" or p.get("openid.ns") != NS or p.get("openid.op_endpoint") != OPENID:
        return None
    if p.get("openid.return_to") != return_to:  # protection against a swapped return_to (it carries our one-time token)
        return None
    m = CLAIMED_RE.match(p.get("openid.claimed_id", ""))
    if not m or p.get("openid.identity") != p.get("openid.claimed_id"):
        return None
    signed = set((p.get("openid.signed") or "").split(","))
    if not {"claimed_id", "identity", "return_to", "response_nonce", "op_endpoint"} <= signed:
        return None
    body = await post(OPENID, {**p, "openid.mode": "check_authentication"})
    if "is_valid:true" not in body.replace(" ", ""):
        return None
    return m.group(1)
