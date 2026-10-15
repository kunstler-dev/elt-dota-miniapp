from app.game import balance as B
from app.models import SteamAccount, User

from .conftest import auth, player


class SwitchChecker:
    """A Steam check whose result can be toggled in a test."""

    def __init__(self):
        self.passed = True

    async def check(self, steam_id, th, now=None):
        return {"passed": self.passed, "reasons": [] if self.passed else ["young"], "persona": None, "avatar": None}


async def souls_of(app, uid):
    async with app.state.db.sessions() as s:
        return (await s.get(User, uid)).souls


async def test_bonus_paid_once_on_verified_friend(client, app):
    await player(client, 1)
    await player(client, 2, "ref_1")
    assert await souls_of(app, 1) == B.REF_BONUS and await souls_of(app, 2) == 0   # no bonus for joining via a link
    f = (await client.get("/api/friends", headers=auth(1))).json()
    assert f["confirmed"] == 1 and f["friends"][0]["status"] == "confirmed" and f["friends"][0]["souls"] == B.REF_BONUS
    # relinking / rechecking doesn't pay a second time
    await client.post("/api/steam/dev-link", json={"steam_id": "76561190000000002"}, headers=auth(2))
    assert await souls_of(app, 1) == B.REF_BONUS


async def test_unverified_friend_counts_only_after_recheck(client, app):
    checker = SwitchChecker()
    app.state.steam_checker = checker
    await player(client, 10)
    checker.passed = False
    await player(client, 11, "ref_10")
    assert await souls_of(app, 10) == 0
    f = (await client.get("/api/friends", headers=auth(10))).json()
    assert f["confirmed"] == 0 and f["invited"] == 1 and f["friends"][0]["status"] == "not_verified"
    assert (await client.post("/api/steam/recheck", headers=auth(11))).status_code == 429  # just checked
    async with app.state.db.sessions() as s:
        (await s.get(SteamAccount, 11)).checked_ms = 0
        await s.commit()
    checker.passed = True
    r = (await client.post("/api/steam/recheck", headers=auth(11))).json()
    assert r["steam"]["verified"] and await souls_of(app, 10) == B.REF_BONUS


async def test_premium_friend_bonus(client, app):
    from app.game import clicker
    from app.services.referrals import confirm_if_ready
    await player(client, 20)
    async with app.state.db.sessions() as s:
        u = User(id=21, first_name="p")
        clicker.init_new(u, 0)
        u.referrer_id, u.is_premium = 20, True
        s.add(u)
        await s.flush()
        s.add(SteamAccount(user_id=21, steam_id="76561190000000021", linked_ms=0, passed=True))
        await s.flush()
        assert await confirm_if_ready(s, 21, 1)
        assert not await confirm_if_ready(s, 21, 2)  # second time: nothing
        await s.commit()
    assert await souls_of(app, 20) == B.REF_BONUS_PREMIUM


async def test_percent_two_levels(client, app):
    async def sub_checker(channel, uid):
        return True

    app.state.sub_checker = sub_checker
    await player(client, 30)
    await player(client, 31, "ref_30")
    await player(client, 32, "ref_31")
    base30, base31 = await souls_of(app, 30), await souls_of(app, 31)
    await client.post("/api/tasks/sub_elt_deadlock/check", headers=auth(32))  # friend of a friend earned 50
    assert await souls_of(app, 31) - base31 == int(50 * B.REF_SHARE_L1)
    assert await souls_of(app, 30) - base30 == int(50 * B.REF_SHARE_L2)


async def test_top_referrals(client):
    await player(client, 40)
    await player(client, 41)
    for i, ref in ((42, 40), (43, 40), (44, 41)):
        await player(client, i, f"ref_{ref}")
    top = (await client.get("/api/top/referrals", headers=auth(41))).json()
    assert [(t["name"], t["value"]) for t in top["top"][:2]] == [("dev40", 2), ("dev41", 1)]
    assert top["me"] == {"rank": 2, "value": 1}
