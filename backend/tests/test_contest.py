import httpx
import pytest

from app.services import contest as C
from app.services.users import now_ms

from .conftest import auth, player


def test_parse_url():
    assert C.parse_url("https://youtube.com/shorts/dQw4w9WgXcQ?feature=share")[:2] == ("youtube", "dQw4w9WgXcQ")
    assert C.parse_url("youtu.be/dQw4w9WgXcQ")[1] == "dQw4w9WgXcQ"
    assert C.parse_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3")[2] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert C.parse_url("https://www.tiktok.com/@elt/video/7312345678901234567?lang=ru")[:2] == ("tiktok", "7312345678901234567")
    assert C.parse_url("https://vm.tiktok.com/ZMabc123/")[:2] == ("tiktok", None)
    for bad in ("https://vk.com/video1", "https://youtube.com/@channel", "hello"):
        with pytest.raises(C.BadUrl):
            C.parse_url(bad)


def fake_fetch(views):
    async def fetch(url, headers):
        req = httpx.Request("GET", url)
        if "googleapis" in url:
            ids = url.split("&id=")[1].split("&")[0].split(",")
            items = [{"id": i, "statistics": {"viewCount": str(views[i])},
                      "snippet": {"title": "ELT", "channelTitle": "ch", "publishedAt": "2026-10-15T10:00:00Z"}}
                     for i in ids if i in views]
            return httpx.Response(200, json={"items": items}, request=req)
        vid = C.TT_VIDEO.search(url).group(1)
        html = f'<script>{{"createTime":"1792000000","uniqueId":"tt_user","stats":{{"playCount":{views[vid]}}}}}</script>'
        return httpx.Response(200, text=html, request=req)
    return fetch


async def test_contest_flow(client, app):
    app.state.settings.admin_ids = "1"
    h = await player(client, 700)
    h2 = await player(client, 701)
    url = "https://youtube.com/shorts/AAAAAAAAAAA"
    assert (await client.post("/api/contest/entries", json={"url": url}, headers=h)).json()["detail"] == "contest_closed"
    assert (await client.get("/api/contest", headers=h)).json()["phase"] == "soon"
    assert (await client.post("/api/admin/contest/start", headers=h)).status_code == 403
    await client.get("/api/me", headers=auth(1))
    assert (await client.post("/api/admin/contest/start", headers=auth(1))).status_code == 200

    assert (await client.post("/api/contest/entries", json={"url": url}, headers=h)).status_code == 200
    assert (await client.post("/api/contest/entries", json={"url": url}, headers=h2)).json()["detail"] == "already_submitted"
    assert (await client.post("/api/contest/entries", json={"url": "https://vk.com/x"}, headers=h)).json()["detail"] == "bad_url"
    tt = "https://www.tiktok.com/@x/video/7312345678901234567"
    assert (await client.post("/api/contest/entries", json={"url": tt}, headers=h2)).status_code == 200

    async with app.state.db.sessions() as s:
        st = await C.refresh_views(s, "KEY", now_ms(), fetch=fake_fetch({"AAAAAAAAAAA": 1500, "7312345678901234567": 9000}))
        await s.commit()
    assert st == {"updated": 2, "failed": 0}
    d = (await client.get("/api/contest", headers=h)).json()
    assert d["phase"] == "active" and [r["id"] for r in d["top"]] == [701, 700]
    assert d["top"][0]["prize_rub"] == 30_000 and d["me"]["rank"] == 2 and d["me"]["views"] == 1500
    assert d["me"]["entries"][0]["title"] == "ELT"

    # admin: manual views and rejection
    a = (await client.get("/api/admin/contest", headers=auth(1))).json()
    tid = next(e["id"] for e in a["entries"] if e["platform"] == "tiktok")
    yid = next(e["id"] for e in a["entries"] if e["platform"] == "youtube")
    await client.post(f"/api/admin/contest/entries/{yid}", json={"views": 20000}, headers=auth(1))
    await client.post(f"/api/admin/contest/entries/{tid}", json={"status": "rejected", "note": "накрутка"}, headers=auth(1))
    d = (await client.get("/api/contest", headers=h2)).json()
    assert [r["id"] for r in d["top"]] == [700] and d["top"][0]["views"] == 20000
    assert d["me"]["entries"][0]["status"] == "rejected" and d["me"]["entries"][0]["note"] == "накрутка"
