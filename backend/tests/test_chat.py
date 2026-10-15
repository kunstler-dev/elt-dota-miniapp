import base64

from app.game import balance as B
from app.models import User

from .conftest import auth, player

IMG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"0" * 200).decode()


async def test_world_and_guild_chat(client, app):
    app.state.settings.admin_ids = "1"
    a, b = await player(client, 950), await player(client, 951)
    r = await client.post("/api/chat/world", json={"text": "  привет   всем "}, headers=a)
    assert r.status_code == 200 and r.json()["message"]["text"] == "привет всем"
    assert (await client.post("/api/chat/world", json={"text": "ещё"}, headers=a)).json()["detail"] == "too_fast"
    assert (await client.post("/api/chat/world", json={"text": "заходи на example.com"}, headers=b)).json()["detail"] == "no_links"
    async with app.state.db.sessions() as s:
        (await s.get(User, 950)).coins = B.GUILD_CREATE_COST
        await s.commit()
    hist = (await client.get("/api/chat/world", headers=b)).json()["messages"]
    assert [m["text"] for m in hist] == ["привет всем"] and not hist[0]["me"]
    after = (await client.get(f"/api/chat/world?after={hist[0]['id']}", headers=b)).json()["messages"]
    assert after == []

    gid = (await client.post("/api/guilds", json={"name": "Chat Guild", "image": IMG}, headers=a)).json()["guild"]["id"]
    ch = f"/api/chat/g:{gid}"
    assert (await client.get(ch, headers=b)).json()["detail"] == "not_in_guild"
    await client.post(f"/api/guilds/{gid}/join", headers=b)
    r = await client.post(ch, json={"text": "го в хук"}, headers=b)
    mid = r.json()["message"]["id"]
    assert [m["text"] for m in (await client.get(ch, headers=a)).json()["messages"]] == ["го в хук"]
    # a guild owner deletes messages in the guild chat
    assert (await client.delete(f"/api/chat/msg/{mid}", headers=a)).status_code == 200
    assert (await client.get(ch, headers=a)).json()["messages"] == []
    # in the world chat only the author or an admin
    wid = hist[0]["id"]
    assert (await client.delete(f"/api/chat/msg/{wid}", headers=b)).status_code == 403
    await client.get("/api/me", headers=auth(1))
    assert (await client.delete(f"/api/chat/msg/{wid}", headers=auth(1))).status_code == 200


async def test_moderation(client, app):
    app.state.settings.admin_ids = "1"
    a, b, c, d = [await player(client, uid) for uid in (960, 961, 962, 963)]
    await client.get("/api/me", headers=auth(1))
    # profanity is replaced with asterisks
    r = (await client.post("/api/chat/world", json={"text": "ну ты и сука"}, headers=a)).json()
    assert r["message"]["text"] == "ну ты и ****"
    mid = r["message"]["id"]
    # reports: can't report your own; hidden after three
    assert (await client.post(f"/api/chat/msg/{mid}/report", headers=a)).json()["detail"] == "own_message"
    for h in (b, c):
        assert not (await client.post(f"/api/chat/msg/{mid}/report", headers=h)).json()["hidden"]
    assert (await client.post(f"/api/chat/msg/{mid}/report", headers=d)).json()["hidden"]
    assert (await client.get("/api/chat/world", headers=b)).json()["messages"] == []
    st = (await client.get("/api/chat/admin/state", headers=auth(1))).json()
    assert st["reports"][0]["id"] == mid and st["reports"][0]["reports"] == 3
    assert (await client.get("/api/chat/admin/state", headers=a)).status_code == 403
    # an admin restored the message, then muted the author for 60 minutes and deleted all their messages
    await client.post(f"/api/chat/admin/msg/{mid}/restore", headers=auth(1))
    assert len((await client.get("/api/chat/world", headers=b)).json()["messages"]) == 1
    r = (await client.post("/api/chat/admin/ban", json={"user_id": 960, "minutes": 60, "reason": "мат", "purge": True},
                           headers=auth(1))).json()
    assert r["purged"] == 1
    assert (await client.get("/api/chat/world", headers=b)).json()["messages"] == []
    assert (await client.post("/api/chat/world", json={"text": "я снова тут"}, headers=a)).json()["detail"] == "muted"
    me = (await client.get("/api/chat/world", headers=a)).json()
    assert me["muted_until"] and me["muted_reason"] == "мат"
    # permanent ban and lifting it
    st = (await client.post("/api/chat/admin/ban", json={"user_id": 960, "minutes": 0}, headers=auth(1))).json()
    assert (await client.get("/api/chat/admin/state", headers=auth(1))).json()["bans"][0]["permanent"]
    await client.delete("/api/chat/admin/ban/960", headers=auth(1))
    async with app.state.db.sessions() as s:   # previous message was long ago (anti-spam 3 s)
        from sqlalchemy import update
        from app.models import ChatMessage
        await s.execute(update(ChatMessage).values(created_ms=0))
        await s.commit()
    assert (await client.post("/api/chat/world", json={"text": "я исправился"}, headers=a)).status_code == 200
