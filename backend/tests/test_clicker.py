from app.game import balance as B
from app.game import clicker
from app.models import User

from .conftest import auth, player


def fresh(now=0) -> User:
    u = User(id=1)
    clicker.init_new(u, now)
    return u


def test_taps_limited_by_energy_and_rate():
    u = fresh()
    # right after start the window is 0 ms -> only the TAP_BURST allowance
    assert clicker.apply_taps(u, 500, 0) == B.TAP_BURST
    # after 2 s: 2*15 + 30 = 60 taps by the rate limit
    assert clicker.apply_taps(u, 500, 2000) == 2 * B.MAX_TAPS_PER_SEC + B.TAP_BURST
    assert u.coins == u.earned_total == B.TAP_BURST + 60


def test_no_taps_without_energy_and_regen():
    u = fresh()
    u.energy = 0
    assert clicker.apply_taps(u, 10, 0) == 0
    clicker.regen_energy(u, 1000)
    assert u.energy == B.ENERGY_REGEN_PER_SEC
    clicker.regen_energy(u, 10_000_000)
    assert u.energy == clicker.max_energy(u)


def test_passive_income_and_offline_cap():
    u = fresh()
    u.profit_per_hour = 3600  # 1 coin per second
    assert clicker.accrue_passive(u, 10_500) == 10
    assert clicker.accrue_passive(u, 11_000) == 1  # the 0.5 s remainder was not lost
    assert clicker.accrue_passive(u, 11_000 + 24 * 3600 * 1000) == B.OFFLINE_CAP_SEC


def test_league_progress():
    u = fresh()
    clicker.earn(u, 5_000)  # earnings go into the league rating; without other players the minimum thresholds apply
    lg = clicker.league(u)
    assert lg["name"] == "Страж" and lg["next"] == "Рыцарь" and 0.49 < lg["progress"] < 0.51 and lg["rating"] == 5_000


async def test_me_tap_and_referral(client):
    r = (await client.get("/api/me", headers=auth(10))).json()
    assert r["state"]["energy"] == B.ENERGY_BASE and r["invite_link"].endswith("start=ref_10")
    # the referral is recorded on first login; you can't invite yourself
    await client.get("/api/me", headers=auth(11, "ref_10"))
    await client.get("/api/me", headers=auth(12, "ref_12"))
    async with client._transport.app.state.db.sessions() as s:  # type: ignore[attr-defined]
        assert (await s.get(User, 11)).referrer_id == 10
        assert (await s.get(User, 12)).referrer_id is None
    assert (await client.post("/api/tap", json={"taps": 5}, headers=auth(10))).json()["detail"] == "steam_required"
    await player(client, 10)
    t = (await client.post("/api/tap", json={"taps": 5}, headers=auth(10))).json()
    assert t["accepted"] == 5 and t["state"]["coins"] == 5
    assert (await client.post("/api/tap", json={"taps": 0}, headers=auth(10))).status_code == 422
