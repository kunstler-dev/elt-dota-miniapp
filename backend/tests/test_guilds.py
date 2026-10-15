import base64

from app.game import balance as B
from app.models import User
from app.services import activity
from app.services.users import now_ms

from .conftest import auth, player

IMG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"0" * 200).decode()


async def coins(app, uid, amount):
    async with app.state.db.sessions() as s:
        (await s.get(User, uid)).coins = amount
        await s.commit()


async def points(app, uid, n):
    async with app.state.db.sessions() as s:
        await activity.add(s, await s.get(User, uid), n, now_ms(), app.state.settings.timezone)
        await s.commit()


async def test_create_join_points_and_quests(client, app):
    owner = await player(client, 500)
    r = await client.post("/api/guilds", json={"name": "Roshan Pit", "image": IMG}, headers=owner)
    assert r.json()["detail"] == "not_enough_coins"
    await coins(app, 500, B.GUILD_CREATE_COST + 5)
    r = await client.post("/api/guilds", json={"name": "Roshan  Pit", "image": IMG}, headers=owner)
    assert r.status_code == 200, r.text
    g = r.json()["guild"]
    assert g["name"] == "Roshan Pit" and g["my_role"] == "owner" and r.json()["state"]["coins"] == 5
    gid = g["id"]

    other = await player(client, 501)
    await coins(app, 501, B.GUILD_CREATE_COST)
    assert (await client.post("/api/guilds", json={"name": "roshan pit", "image": IMG}, headers=other)).json()["detail"] == "name_taken"
    assert (await client.post(f"/api/guilds/{gid}/join", headers=other)).status_code == 200

    # members' activity points go to the guild
    await points(app, 500, 400)
    await points(app, 501, 100)
    d = (await client.get("/api/guild", headers=owner)).json()
    assert d["guild"]["points"] == 500 and d["guild"]["members"] == 2 and d["guild"]["my_points"] == 400
    assert d["top"][0]["id"] == gid and d["top"][0]["points"] == 500 and d["guild"]["rank"] == 1
    q = {x["id"]: x for x in d["guild"]["quests"]}
    assert q["points"]["progress"] == 500 and q["active"]["progress"] == 1

    # tier done -> only those who contributed GUILD_MIN_CONTRIB points can claim
    B.GUILD_QUESTS[0]["tiers"][0] = (500, 20)
    try:
        r = await client.post("/api/guild/quests/points/0/claim", headers=owner)
        assert r.status_code == 200 and r.json()["souls"] == 20
        assert (await client.post("/api/guild/quests/points/0/claim", headers=owner)).json()["detail"] == "already_claimed"
        assert (await client.post("/api/guild/quests/points/0/claim", headers=other)).json()["detail"] == "not_ready"
        assert (await client.post("/api/guild/quests/points/1/claim", headers=owner)).json()["detail"] == "not_ready"
    finally:
        B.GUILD_QUESTS[0]["tiers"][0] = (20_000, 20)

    # a member left: their points stay with the guild, rejoining is allowed after a day
    assert (await client.post("/api/guild/leave", headers=other)).status_code == 200
    assert (await client.post(f"/api/guilds/{gid}/join", headers=other)).json()["detail"] == "rejoin_cooldown"
    await points(app, 501, 50)                 # points earned outside the guild don't go to it
    d = (await client.get("/api/guild", headers=owner)).json()
    assert d["guild"]["members"] == 1 and d["guild"]["points"] == 500


async def test_owner_leaves_and_kick(client, app):
    a, b, c = [await player(client, uid) for uid in (510, 511, 512)]
    await coins(app, 510, B.GUILD_CREATE_COST)
    gid = (await client.post("/api/guilds", json={"name": "Ancients", "image": IMG}, headers=a)).json()["guild"]["id"]
    for h in (b, c):
        assert (await client.post(f"/api/guilds/{gid}/join", headers=h)).status_code == 200
    assert (await client.post("/api/guild/kick/512", headers=b)).status_code == 403
    r = await client.post("/api/guild/kick/512", headers=a)
    assert r.status_code == 200 and r.json()["guild"]["members"] == 2
    assert (await client.post("/api/guild/leave", headers=a)).status_code == 200
    d = (await client.get("/api/guild", headers=b)).json()
    assert d["guild"]["my_role"] == "owner" and d["guild"]["owner_id"] == 511
    assert (await client.post("/api/guild/leave", headers=b)).status_code == 200
    assert (await client.get(f"/api/guilds/{gid}", headers=b)).status_code == 404     # the last member left: the guild is gone


async def test_guild_picture(client, app):
    a = await player(client, 520)
    b = await player(client, 521)
    await coins(app, 520, B.GUILD_CREATE_COST)
    r = await client.post("/api/guilds", json={"name": "Pics", "image": "data:image/gif;base64,R0lGODlh"}, headers=a)
    assert r.json()["detail"] == "bad_image"
    g = (await client.post("/api/guilds", json={"name": "Pics", "image": IMG}, headers=a)).json()["guild"]
    assert g["emblem_url"].endswith("?v=1")
    img = await client.get(g["emblem_url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert (await client.post(f"/api/guilds/{g['id']}/join", headers=b)).status_code == 200
    assert (await client.post("/api/guild/emblem", json={"image": IMG}, headers=b)).status_code == 403
    r = await client.post("/api/guild/emblem", json={"image": IMG}, headers=a)
    assert r.json()["guild"]["emblem_url"].endswith("?v=2")


async def test_guild_war_prizes(client, app):
    from app.jobs import guild_war_prizes
    from app.models import GuildPoints
    a, b = await player(client, 530), await player(client, 531)
    await coins(app, 530, B.GUILD_CREATE_COST)
    await coins(app, 531, B.GUILD_CREATE_COST)
    g1 = (await client.post("/api/guilds", json={"name": "Top One", "image": IMG}, headers=a)).json()["guild"]["id"]
    g2 = (await client.post("/api/guilds", json={"name": "Top Two", "image": IMG}, headers=b)).json()["guild"]["id"]
    now = now_ms()
    prev = activity.week_key(now - 7 * 24 * 3600 * 1000, app.state.settings.timezone)
    async with app.state.db.sessions() as s:
        s.add(GuildPoints(guild_id=g1, user_id=530, period=prev, points=5_000))
        s.add(GuildPoints(guild_id=g2, user_id=531, period=prev, points=B.GUILD_MIN_CONTRIB - 1))  # not enough contribution
        await s.commit()
    assert await guild_war_prizes(app, now) == "g" + prev
    assert await guild_war_prizes(app, now) is None            # once per week
    async with app.state.db.sessions() as s:
        assert (await s.get(User, 530)).souls == B.GUILD_WAR_PRIZES[0]
        assert (await s.get(User, 531)).souls == 0
