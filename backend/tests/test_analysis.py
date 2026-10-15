import time

from app.services import dota_analysis as an
from app.services import stars
from app.services.opendota import OpenDota, OpenDotaError

from . import od_mock as M
from .conftest import auth


def report(parsed=True):
    return an.build_report(aid=M.AID, player=M.player(), recent=M.recent(), match=M.match(parsed),
                           bench=M.bench()["result"], hero_stats=M.hero_stats(), player_heroes=M.player_heroes())


def test_report_breakdown_and_mistakes():
    r = report()
    last = r["last"]
    assert last["hero"] == "Juggernaut" and last["kills"] == 4 and not last["win"]
    assert last["stats"]["lh10"] == 30 and last["pos"] == 1
    assert last["lane"]["result"] == "lose"
    assert [i["name"] for i in last["items"]][:2] == ["Power Treads", "Battle Fury"]
    titles = " ".join(m["title"] for m in r["mistakes"])
    assert "Много смертей" in titles and "Проигранная линия" in titles
    assert r["mistakes"][0]["severity"] == "high"
    assert r["position"]["best"] == 1 and 3 <= len(r["tips"]) <= 5
    assert r["heroes"]["drop"][0]["name"] == "Anti-Mage"


async def test_opendota_cache_and_stale(app):
    fake = M.FakeOD()
    od = OpenDota(app.state.db, fake, min_interval=0)
    await od.player(M.AID)
    await od.player(M.AID)
    assert len(fake.calls) == 1                              # second time: from the cache
    await od.forget(f"player:{M.AID}")
    fake.status = 429
    try:
        await od.player(M.AID)
        raise AssertionError
    except OpenDotaError as e:
        assert str(e) == "rate_limited"
    fake.status = 200
    assert await od.request_parse(1) and not await od.request_parse(1)   # at most once every 10 min


async def _linked(client, uid):
    h = auth(uid)
    await client.get("/api/me", headers=h)
    r = await client.post("/api/steam/dev-link", json={"steam_id": M.STEAMID}, headers=h)
    assert r.status_code == 200, r.text
    return h


async def test_api_beta_paywall_and_subscription(app, client):
    app.state.settings.admin_ids = "1"
    fake = M.FakeOD(parsed=False)
    app.state.opendota = OpenDota(app.state.db, fake, min_interval=0)
    links = []

    class Bot:
        async def create_invoice_link(self, **kw):
            links.append(kw)
            return "https://t.me/$inv"
    h = await _linked(client, 10)
    app.state.bot = Bot()
    d = (await client.get("/api/analysis", headers=h)).json()
    assert d["status"] == "ok" and d["pay"]["mode"] == "beta" and not d["parsed"] and d["parse_requested"]
    assert ("POST", "/request/8000000000") in fake.calls
    assert d["report"]["last"]["hero"] == "Juggernaut"
    assert (await client.post("/api/analysis/invoice", headers=h)).status_code == 400   # beta: free

    assert (await client.post("/api/admin/analysis/settings", headers=h, json={"beta_free": False})).status_code == 403
    await client.get("/api/me", headers=auth(1))
    r = await client.post("/api/admin/analysis/settings", headers=auth(1), json={"beta_free": False, "price": 250})
    assert r.json()["settings"] == {"beta_free": False, "price": 250, "free_per_week": 1}
    assert (await client.post("/api/admin/analysis/settings", headers=auth(1), json={"price": 0})).status_code == 400

    d = (await client.get("/api/analysis", headers=h)).json()      # same match: free again
    assert d["status"] == "ok" and d["pay"]["mode"] == "free"
    async with app.state.db.sessions() as s:
        await stars.consume(s, 10, 1, int(time.time() * 1000))     # another match already opened this week
        from app.models import AnalysisUsage
        await s.delete(await s.get(AnalysisUsage, (10, 8000000000)))
        await s.commit()
    d = (await client.get("/api/analysis", headers=h)).json()
    assert d["status"] == "locked" and d["preview"]["hero"] == "Juggernaut" and d["pay"]["price"] == 250
    r = await client.post("/api/analysis/invoice", headers=h)
    assert r.json()["url"].startswith("https://t.me/")
    kw = links[0]
    assert kw["currency"] == "XTR" and kw["subscription_period"] == 2592000 and kw["prices"][0].amount == 250
    assert stars.validate_pre_checkout(10, kw["payload"], "XTR", 250) is None
    assert stars.validate_pre_checkout(11, kw["payload"], "XTR", 250)

    now = int(time.time() * 1000)
    async with app.state.db.sessions() as s:
        await stars.record_payment(s, 10, "c1", 250, kw["payload"], None, True, now)
        await stars.record_payment(s, 10, "c1", 250, kw["payload"], None, True, now)        # duplicate: ignored
        await s.commit()
    d = (await client.get("/api/analysis", headers=h)).json()
    assert d["status"] == "ok" and d["pay"]["mode"] == "sub"
    a = (await client.get("/api/admin/analysis", headers=auth(1))).json()
    assert a["subscribers"][0]["user_id"] == 10 and a["subscribers"][0]["paid"] == 250
    assert len(a["payments"]) == 1

    assert (await client.get("/api/analysis?refresh=1", headers=h)).status_code == 200
    assert (await client.get("/api/analysis?refresh=1", headers=h)).status_code == 429


async def test_api_private_and_down(app, client):
    h = await _linked(client, 10)
    app.state.opendota = OpenDota(app.state.db, M.FakeOD(private=True), min_interval=0)
    d = (await client.get("/api/analysis", headers=h)).json()
    assert d["status"] == "private" and "Expose Public Match Data" in d["message"]
    app.state.opendota = OpenDota(app.state.db, M.FakeOD(status=503), min_interval=0)
    async with app.state.db.sessions() as s:
        from app.models import OdCache
        from sqlalchemy import delete
        await s.execute(delete(OdCache))
        await s.commit()
    r = await client.get("/api/analysis", headers=h)
    assert r.status_code == 503 and "OpenDota" in r.json()["message"]


async def test_opendota_api_key(app, monkeypatch):
    from app.services import opendota as OD
    seen = []

    async def fake(method, path):
        seen.append(path)
        return 200, []
    monkeypatch.setattr(OD, "http_fetch", fake)
    app.state.opendota = None
    app.state.settings.opendota_api_key = "KEY123"
    od = OD.for_app(app)
    assert od.daily_limit is None
    await od.hero_matchups(1)
    await od.player_heroes(7)
    assert seen == ["/heroes/1/matchups?api_key=KEY123", "/players/7/heroes?date=180&api_key=KEY123"]
