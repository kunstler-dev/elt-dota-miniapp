from app.models import PrizeClaim

from .conftest import auth, player


async def test_admin_stats_and_prizes(client, app):
    app.state.settings.admin_ids = "900"
    h = await player(client, 901)
    await player(client, 902)
    await client.post("/api/daily/claim", headers=h)
    assert (await client.get("/api/admin/stats", headers=h)).status_code == 403
    me = (await client.get("/api/me", headers=auth(900))).json()
    assert me["user"]["is_admin"] and not (await client.get("/api/me", headers=h)).json()["user"]["is_admin"]
    st = (await client.get("/api/admin/stats", headers=auth(900))).json()
    u = st["users"]
    assert u["total"] == 3 and u["online"] == 3 and u["new_today"] == 3 and u["steam_linked"] == 2
    assert st["daily_claims_today"] == 1
    assert {t["id"] for t in st["tasks"]} == {"sub_elt_deadlock", "boost_elt_tg"}

    async with app.state.db.sessions() as s:
        s.add(PrizeClaim(user_id=901, period="m:2026-09", place=1, prize="arcana", status="pending", created_ms=1))
        await s.commit()
    p = (await client.get("/api/admin/prizes", headers=auth(900))).json()["prizes"]
    assert p[0]["prize"] == "arcana" and p[0]["steam_id"]
    assert (await client.post(f"/api/admin/prizes/{p[0]['id']}/sent", headers=auth(900))).status_code == 200
    assert (await client.get("/api/admin/prizes", headers=auth(900))).json()["prizes"][0]["status"] == "sent"
