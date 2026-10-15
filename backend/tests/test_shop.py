import httpx

from app.game.shop_catalog import CATALOG
from app.models import ShopItem, SteamAccount, User
from app.services import market
from app.services.users import now_ms

from .conftest import auth, player


async def give_souls(app, uid, n):
    async with app.state.db.sessions() as s:
        (await s.get(User, uid)).souls = n
        await s.commit()


async def test_catalog_rate_buy_and_admin(client, app):
    app.state.settings.admin_ids = "1"
    h = await player(client, 800)
    shop = (await client.get("/api/shop", headers=h)).json()
    assert len(shop["items"]) == len(CATALOG) and shop["souls_per_usd"] == market.DEFAULT_SOULS_PER_USD
    kinds = [i["kind"] for i in shop["items"]]
    assert kinds[0] == "crimson" and kinds[1] == "golden" and "dota_plus" not in kinds and "set" not in kinds
    feast = next(i for i in shop["items"] if i["id"] == "arc_feast")
    assert feast["price"] == 2121 * market.DEFAULT_SOULS_PER_USD // 100 and feast["usd_cents"] == 2121   # 21.21 USD x rate

    # the rate changes prices across the whole showcase
    await client.get("/api/me", headers=auth(1))
    assert (await client.post("/api/admin/shop/rate", json={"souls_per_usd": 100}, headers=h)).status_code == 403
    assert (await client.post("/api/admin/shop/rate", json={"souls_per_usd": 100}, headers=auth(1))).status_code == 200
    feast = next(i for i in (await client.get("/api/shop", headers=h)).json()["items"] if i["id"] == "arc_feast")
    assert feast["price"] == 2121

    assert (await client.post("/api/shop/arc_feast/buy", json={}, headers=h)).json()["detail"] == "not_enough_souls"
    await give_souls(app, 800, 2131)
    r = await client.post("/api/shop/arc_feast/buy", json={}, headers=h)
    assert r.status_code == 200 and r.json()["state"]["souls"] == 10
    order = r.json()["order"]

    a = (await client.get("/api/admin/shop", headers=auth(1))).json()
    assert a["orders"][0]["steam_id"] and a["souls_per_usd"] == 100
    r = await client.post(f"/api/admin/shop/orders/{order['id']}", json={"status": "cancelled", "admin_note": "нет лотов"},
                          headers=auth(1))
    assert r.json()["order"]["status"] == "cancelled"
    assert (await client.post(f"/api/admin/shop/orders/{order['id']}", json={"status": "sent"}, headers=auth(1))).status_code == 409
    assert (await client.get("/api/me", headers=h)).json()["state"]["souls"] == 2131

    # stock and hiding
    await client.patch("/api/admin/shop/items/arc_feast", json={"stock": 0}, headers=auth(1))
    assert (await client.post("/api/shop/arc_feast/buy", json={}, headers=h)).json()["detail"] == "out_of_stock"
    await client.patch("/api/admin/shop/items/arc_feast", json={"active": False}, headers=auth(1))
    assert "arc_feast" not in [i["id"] for i in (await client.get("/api/shop", headers=h)).json()["items"]]


async def test_market_refresh(client, app):
    h = await player(client, 820)
    await client.get("/api/shop", headers=h)

    async def fetch(url):
        name = httpx.URL(url).params["query"]
        res = [] if name == "Demon Eater" else [
            {"hash_name": name, "sell_price": 5000, "sell_listings": 7, "asset_description": {"icon_url": "abc"}}]
        return httpx.Response(200, json={"results": res}, request=httpx.Request("GET", url))

    stats = await market.refresh_prices(app.state.db, now_ms(), fetch=fetch, pause=0)
    assert stats == {"updated": len(CATALOG) - 1, "missing": 1, "failed": 0}
    async with app.state.db.sessions() as s:
        feast = await s.get(ShopItem, "arc_feast")
        assert feast.usd_cents == 5000 and feast.price == 50 * market.DEFAULT_SOULS_PER_USD and feast.image.endswith("/abc/256fx256f")
        assert (await s.get(ShopItem, "arc_demon_eater")).listings == 0
    # no listings on the market: can't buy
    async with app.state.db.sessions() as s:
        (await s.get(User, 820)).souls = 10**7
        await s.commit()
    assert (await client.post("/api/shop/arc_demon_eater/buy", json={}, headers=h)).json()["detail"] == "out_of_stock"
    # a second pass on the same day requests nothing
    assert (await market.refresh_prices(app.state.db, now_ms(), fetch=fetch, pause=0))["updated"] == 0


async def test_unverified_steam_cannot_buy(client, app):
    h = await player(client, 810)
    async with app.state.db.sessions() as s:
        (await s.get(SteamAccount, 810)).passed = False
        await s.commit()
    await give_souls(app, 810, 10**8)
    await client.get("/api/shop", headers=h)
    r = await client.post("/api/shop/arc_feast/buy", json={}, headers=h)
    assert r.status_code == 403 and r.json()["detail"] == "steam_not_verified"


async def test_catalog_has_images(client, app):
    h = await player(client, 830)
    items = (await client.get("/api/shop", headers=h)).json()["items"]
    assert items and all(i["image"] and i["image"].startswith("https://") for i in items)   # icons right away, without a refresh
