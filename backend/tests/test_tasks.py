from datetime import date

from sqlalchemy import select

from app.game import balance as B
from app.game import daily
from app.models import Ledger, User

from .conftest import auth, player


def test_daily_streak_rules():
    u = User(id=1, daily_streak=0, daily_last=None, coins=0, earned_total=0)
    d1 = date(2026, 10, 1)
    assert daily.claim(u, d1) == B.DAILY_REWARDS[0]
    assert daily.claim(u, d1) is None  # can't claim twice on the same day
    assert daily.claim(u, date(2026, 10, 2)) == B.DAILY_REWARDS[1]
    assert daily.claim(u, date(2026, 10, 4)) == B.DAILY_REWARDS[0]  # missed day: the streak restarts
    u.daily_streak, u.daily_last = len(B.DAILY_REWARDS), "2026-10-09"
    assert daily.claim(u, date(2026, 10, 10)) == B.DAILY_REWARDS[0]  # after the last day: loops around
    assert u.coins == u.earned_total


async def test_daily_api(client):
    h = await player(client, 50)
    t = (await client.get("/api/tasks", headers=h)).json()
    assert t["daily"] == {"day": 1, "claimable": True, "rewards": B.DAILY_REWARDS}
    r = (await client.post("/api/daily/claim", headers=h)).json()
    assert r["reward"] == B.DAILY_REWARDS[0] and r["state"]["coins"] == B.DAILY_REWARDS[0]
    assert (await client.post("/api/daily/claim", headers=h)).status_code == 409


async def test_subscribe_task_gives_souls_once(client, app):
    subscribed: set[tuple[str, int]] = set()

    async def sub_checker(channel, user_id):
        return channel == "@ELT_TG" or (channel, user_id) in subscribed  # required channel: subscribed

    app.state.sub_checker = sub_checker
    h = await player(client, 60)
    r = await client.post("/api/tasks/sub_elt_deadlock/check", headers=h)
    assert r.status_code == 400 and r.json()["detail"] == "not_subscribed"
    subscribed.add(("@ELT_TV_deadlockED", 60))
    r = (await client.post("/api/tasks/sub_elt_deadlock/check", headers=h)).json()
    assert r["souls"] == 50 and r["state"]["souls"] == 50
    assert (await client.post("/api/tasks/sub_elt_deadlock/check", headers=h)).status_code == 409
    tasks = {t["id"]: t for t in (await client.get("/api/tasks", headers=h)).json()["tasks"]}
    assert tasks["sub_elt_deadlock"]["done"] and not tasks["boost_elt_tg"]["done"]
    assert "sub_elt_cs2" not in tasks
    async with app.state.db.sessions() as s:
        rows = (await s.execute(select(Ledger).where(Ledger.user_id == 60))).scalars().all()
        assert [(x.amount, x.reason, x.ref) for x in rows] == [(50, "task", "sub_elt_deadlock")]


async def test_boost_task(client, app):
    boosted: set[int] = set()

    async def boost_checker(channel, user_id):
        assert channel == "@ELT_TG"
        return user_id in boosted

    app.state.boost_checker = boost_checker
    h = await player(client, 65)
    assert (await client.post("/api/tasks/boost_elt_tg/check", headers=h)).json()["detail"] == "not_boosted"
    boosted.add(65)
    assert (await client.post("/api/tasks/boost_elt_tg/check", headers=h)).json()["souls"] == 200


async def test_recheck_revokes_unsubscribed_with_debt(client, app):
    from app.jobs import RECHECK_EVERY_MS, recheck_tasks
    from app.services.users import now_ms
    members = {("@ELT_TV_deadlockED", 90), ("@ELT_TV_deadlockED", 91)}

    async def sub_checker(channel, user_id):
        return channel == "@ELT_TG" or (channel, user_id) in members

    app.state.sub_checker = sub_checker
    for uid in (90, 91):
        h = await player(client, uid)
        await client.post("/api/tasks/sub_elt_deadlock/check", headers=h)
    async with app.state.db.sessions() as s:
        (await s.get(User, 90)).souls = 10  # spent part of the souls
        await s.commit()
    members.discard(("@ELT_TV_deadlockED", 90))  # 90 unsubscribed, 91 stayed
    later = now_ms() + RECHECK_EVERY_MS + 1
    assert await recheck_tasks(app, later) == {"checked": 2, "revoked": 1, "skipped": 0}
    async with app.state.db.sessions() as s:
        assert (await s.get(User, 90)).souls == 10 - 50  # the debt is paid off by future souls
        assert (await s.get(User, 91)).souls == 50
    tasks = {t["id"]: t for t in (await client.get("/api/tasks", headers=auth(90))).json()["tasks"]}
    assert not tasks["sub_elt_deadlock"]["done"]  # the task can be completed again
    assert (await recheck_tasks(app, later))["checked"] == 0  # 91 was already rechecked


async def test_tasks_require_steam(client):
    h = auth(70)
    await client.get("/api/me", headers=h)
    assert (await client.post("/api/daily/claim", headers=h)).json()["detail"] == "steam_required"
    assert (await client.post("/api/tasks/sub_elt_deadlock/check", headers=h)).json()["detail"] == "steam_required"


async def test_required_channel_gate(client, app):
    subscribed = {"on": False}

    async def sub_checker(channel, user_id):
        return subscribed["on"] if channel == "@ELT_TG" else False

    app.state.sub_checker = sub_checker
    h = await player(client, 95)
    me = (await client.get("/api/me", headers=h)).json()
    assert me["subscription"] == {"channel": "@ELT_TG", "url": "https://t.me/ELT_TG", "ok": False}
    assert (await client.post("/api/tap", json={"taps": 1}, headers=h)).json()["detail"] == "subscription_required"
    subscribed["on"] = True
    assert (await client.post("/api/subscription/check", headers=h)).json() == {"ok": True}
    assert (await client.post("/api/tap", json={"taps": 1}, headers=h)).json()["accepted"] == 1
    tasks = {t["id"] for t in (await client.get("/api/tasks", headers=h)).json()["tasks"]}
    assert "sub_elt_tg" not in tasks  # the main channel subscription is an entry condition, not a task
