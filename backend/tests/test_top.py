from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.game import balance as B
from app.jobs import pay_prizes
from app.services.users import now_ms
from app.models import Activity, PrizeClaim, SteamAccount, User
from app.services import activity

from .conftest import player

TZ = "Europe/Moscow"


def ms(*args) -> int:
    return int(datetime(*args, tzinfo=ZoneInfo(TZ)).timestamp() * 1000)


def test_period_keys_and_ends():
    t = ms(2026, 10, 14, 12)  # Wednesday
    assert activity.week_key(t, TZ) == "w:2026-W42" and activity.month_key(t, TZ) == "m:2026-10"
    assert activity.period_end_ms("w:2026-W42", TZ) == ms(2026, 10, 19)  # Monday 00:00
    assert activity.period_end_ms("m:2026-12", TZ) == ms(2027, 1, 1)


async def test_taps_give_points_and_week_is_per_league(client, app):
    h1 = await player(client, 301)
    await player(client, 302)
    r = (await client.post("/api/tap", json={"taps": 5}, headers=h1)).json()
    assert r["accepted"] == 5
    async with app.state.db.sessions() as s:
        u2 = await s.get(User, 302)
        u2.league_score, u2.league_ms = 30_000_000, now_ms()  # high rating: a different league
        await activity.add(s, u2, 999, now_ms(), TZ)
        await s.commit()
    week = (await client.get("/api/top/week", headers=h1)).json()
    assert [(t["name"], t["points"]) for t in week["top"]] == [("dev301", 5)]  # another league isn't visible
    assert week["me"] == {"rank": 1, "points": 5} and week["league"]["index"] == 0
    month = (await client.get("/api/top/month", headers=h1)).json()
    assert [t["points"] for t in month["top"]] == [999, 5] and month["me"]["rank"] == 2
    assert month["prizes"][0] == {"place": 1, "item": "Аркана"}


async def test_unverified_steam_not_ranked(client, app):
    h = await player(client, 310)
    await client.post("/api/tap", json={"taps": 3}, headers=h)
    async with app.state.db.sessions() as s:
        (await s.get(SteamAccount, 310)).passed = False
        await s.commit()
    r = (await client.get("/api/top/month", headers=h)).json()
    assert r["top"] == [] and r["me"] == {"rank": None, "points": 3}


async def test_payouts_once(client, app):
    for uid, pts in ((320, 50), (321, 80), (322, 10)):
        await player(client, uid)
        async with app.state.db.sessions() as s:
            await activity.add(s, await s.get(User, uid), pts, ms(2026, 9, 30, 12), TZ)  # W40 and September
            await s.commit()
    later = ms(2026, 10, 7, 12)  # next week and already October
    paid = await pay_prizes(app, later)
    assert set(paid) == {"w:2026-W40", "m:2026-09"}
    async with app.state.db.sessions() as s:
        souls = {uid: (await s.get(User, uid)).souls for uid in (320, 321, 322)}
        claims = (await s.execute(select(PrizeClaim).order_by(PrizeClaim.place))).scalars().all()
    assert souls == {321: B.WEEK_PRIZES_SOULS[0], 320: B.WEEK_PRIZES_SOULS[1], 322: B.WEEK_PRIZES_SOULS[2]}
    assert [(c.user_id, c.prize) for c in claims] == [(321, "arcana"), (320, "immortal"), (322, "immortal")]
    assert await pay_prizes(app, later) == []  # never paid twice
    async with app.state.db.sessions() as s:
        assert (await s.execute(select(Activity).where(Activity.period == "w:2026-W40"))).scalars().first()
