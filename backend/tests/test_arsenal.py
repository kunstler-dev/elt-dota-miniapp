from pathlib import Path

import pytest

from app.game import arsenal as A
from app.models import User

from .conftest import player

PUBLIC = Path(__file__).resolve().parents[2] / "frontend" / "public"


@pytest.mark.needs_assets
def test_every_item_and_hero_has_model_file():
    missing = [i.model for i in A.ITEMS.values() if not (PUBLIC / i.model.lstrip("/")).exists()]
    for h in A.HEROES:
        for f in (h.dir + h.body, *(h.dir + e for e in h.extras)):
            if not (PUBLIC / f.lstrip("/")).exists():
                missing.append(f)
    assert not missing


def test_tap_power_and_set_bonus():
    u = User(id=1, equipped=None, active_hero="pudge")
    assert A.tap_power(u) == 1  # default Pudge
    A.equip(u, "pudge:trapper:weapon")
    assert A.tap_power(u) == 2
    for slot in A.gear_slots("pudge"):
        A.equip(u, f"pudge:trapper:{slot}")
    assert A.full_set("pudge", A.equipped(u, "pudge")).id == "trapper"
    assert A.tap_power(u) == round((1 + 7) * (1 + A.SET_BONUS_PER_TIER))
    A.equip(u, "pudge:arcana:body")  # an arcana doesn't break the set
    assert A.full_set("pudge", A.equipped(u, "pudge")).id == "trapper"
    A.equip(u, "pudge:dragonclaw:weapon")
    assert A.full_set("pudge", A.equipped(u, "pudge")) is None


def test_partial_set_counts_with_default_slots():
    """The Axe Unleashed set has no misc slot: the set counts as complete if that slot holds the default item."""
    g = A.SET_BY_KEY[("axe", "unleashed")]
    u = User(id=2, equipped=None, active_hero="axe")
    for slot in g.models:
        A.equip(u, f"axe:unleashed:{slot}")
    assert A.full_set("axe", A.equipped(u, "axe")) is g


def test_heroes_get_stronger():
    powers = [h.power for h in A.HEROES]
    prices = [h.price for h in A.HEROES]
    assert powers == sorted(powers) and prices == sorted(prices) and A.HEROES[0].price == 0


async def test_buy_hero_select_and_items(client, app):
    h = await player(client, 100)
    r = (await client.get("/api/arsenal", headers=h)).json()
    assert r["hero"] == "pudge" and r["tap_power"] == 1
    assert (await client.post("/api/arsenal/axe:red_conqueror:weapon/buy", headers=h)).json()["detail"] == "hero_not_owned"
    assert (await client.post("/api/heroes/axe/buy", headers=h)).json()["detail"] == "not_enough_coins"
    async with app.state.db.sessions() as s:
        (await s.get(User, 100)).coins = 10_000_000
        await s.commit()
    b = (await client.post("/api/heroes/axe/buy", headers=h)).json()
    axe = A.HERO_BY_ID["axe"]
    assert b["state"]["active_hero"] == "axe" and b["state"]["tap_power"] == axe.power
    assert b["state"]["profit_per_hour"] == axe.income
    i = (await client.post("/api/arsenal/axe:red_conqueror:weapon/buy", headers=h)).json()
    assert i["state"]["tap_power"] == axe.power + 1
    sel = (await client.post("/api/heroes/pudge/select", headers=h)).json()
    assert sel["state"]["active_hero"] == "pudge" and sel["state"]["tap_power"] == 1
    assert (await client.post("/api/heroes/invoker/select", headers=h)).status_code == 403
    ax = (await client.get("/api/arsenal?hero=axe", headers=h)).json()
    assert ax["equipped"]["weapon"] == "axe:red_conqueror:weapon" and ax["model"]["dir"] == axe.dir
