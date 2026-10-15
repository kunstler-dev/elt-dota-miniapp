from urllib.parse import parse_qs, urlparse

from app.api import steam as steam_api
from app.steam.checker import STEAM64_BASE, SteamChecker, Thresholds
from app.steam.openid import NS, OPENID, verify_assertion

from .conftest import auth, steam_id

SID = "76561198000000001"
RETURN_TO = "http://test/auth/steam/callback?t=abc"


def assertion(sid=SID, return_to=RETURN_TO, **over):
    p = {"openid.ns": NS, "openid.mode": "id_res", "openid.op_endpoint": OPENID,
         "openid.claimed_id": f"https://steamcommunity.com/openid/id/{sid}",
         "openid.identity": f"https://steamcommunity.com/openid/id/{sid}", "openid.return_to": return_to,
         "openid.response_nonce": "n", "openid.assoc_handle": "h",
         "openid.signed": "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle",
         "openid.sig": "x"}
    return {**p, **over}


async def steam_says(valid: bool):
    async def post(url, data):
        assert data["openid.mode"] == "check_authentication"
        return f"ns:{NS}\nis_valid:{'true' if valid else 'false'}\n"
    return post


async def test_verify_assertion():
    assert await verify_assertion(assertion(), RETURN_TO, await steam_says(True)) == SID
    assert await verify_assertion(assertion(), RETURN_TO, await steam_says(False)) is None
    # swapped return_to (someone else's token) and a foreign provider
    assert await verify_assertion(assertion(), RETURN_TO + "x", await steam_says(True)) is None
    assert await verify_assertion(assertion(**{"openid.op_endpoint": "https://evil/"}), RETURN_TO,
                                  await steam_says(True)) is None


async def test_checker_thresholds():
    now = 2_000_000_000
    xml = "<profile><privacyState>public</privacyState><steamID><![CDATA[Ana]]></steamID></profile>"

    async def get_text(url):
        return xml

    async def get_json(url, params):
        if "GetPlayerSummaries" in url:
            return {"response": {"players": [{"communityvisibilitystate": 3, "timecreated": now - 400 * 86400,
                                               "personaname": "Ana", "avatarfull": "https://a/x.jpg"}]}}
        if "GetOwnedGames" in url:
            return {"response": {"games": [{"appid": 570, "playtime_forever": 30 * 60}]}}
        assert url.endswith(f"/players/{int(SID) - STEAM64_BASE}/wl")
        return {"win": 80, "lose": 40}

    chk = await SteamChecker("KEY", get_json, get_text).check(SID, Thresholds(), now)
    assert chk["passed"] and chk["persona"] == "Ana" and chk["od_matches"] == 120  # 30 h is too little, but 120 matches

    async def young_json(url, params):
        if "GetPlayerSummaries" in url:
            return {"response": {"players": [{"communityvisibilitystate": 1, "timecreated": now - 5 * 86400}]}}
        return {"response": {}} if "GetOwnedGames" in url else {"win": 0, "lose": 0}

    chk = await SteamChecker("KEY", young_json, get_text).check(SID, Thresholds(), now)
    assert not chk["passed"] and set(chk["reasons"]) == {"private", "young", "low_dota"}


async def test_link_flow_via_steam(client, monkeypatch):
    h = auth(30)
    me = (await client.get("/api/me", headers=h)).json()
    assert me["steam"] is None
    url = (await client.post("/api/steam/link", headers=h)).json()["url"]
    token = parse_qs(urlparse(url).query)["t"][0]

    start = await client.get(f"/auth/steam/start?t={token}")
    assert start.status_code == 307 and start.headers["location"].startswith(OPENID)

    async def fake_verify(params, return_to, post=None):
        assert return_to.endswith(f"/auth/steam/callback?t={token}")
        return SID
    monkeypatch.setattr(steam_api, "verify_assertion", fake_verify)
    cb = await client.get(f"/auth/steam/callback?t={token}&openid.mode=id_res")
    assert cb.status_code == 200 and "Steam привязан" in cb.text
    me = (await client.get("/api/me", headers=h)).json()
    assert me["steam"]["steam_id"] == SID and me["steam"]["verified"] is True
    # the token is single-use
    assert (await client.get(f"/auth/steam/callback?t={token}")).status_code == 400


async def test_one_steam_one_telegram(client):
    h1, h2 = auth(41), auth(42)
    for h in (h1, h2):
        await client.get("/api/me", headers=h)
    assert (await client.post("/api/steam/dev-link", json={"steam_id": SID}, headers=h1)).status_code == 200
    r = await client.post("/api/steam/dev-link", json={"steam_id": SID}, headers=h2)
    assert r.status_code == 409 and r.json()["detail"] == "taken"
    r = await client.post("/api/steam/dev-link", json={"steam_id": steam_id(41)}, headers=h1)
    assert r.json()["detail"] == "other_linked"
