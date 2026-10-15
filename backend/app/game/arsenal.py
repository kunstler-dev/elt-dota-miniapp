"""Tappable heroes and their Arsenal. Pudge is free, the others are bought (pricier = stronger).
Each hero has its own slots and Dota 2 sets; an item adds tap power, a full set adds a multiplier.
Models: Pudge in /models/pudge/, the others in /models/heroes/<hero>/ (sets in hero_sets.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..models import User


@dataclass(frozen=True)
class Hero:
    id: str
    name: str
    price: int       # ELT COIN; 0 = given right away
    power: int       # base tap power
    income: int      # income per hour while the hero is owned
    dir: str         # model directory
    body: str        # default body (relative to dir)
    extras: tuple[str, ...] = field(default=())  # parts always on the hero (SF wings, Axe hair)


# Placeholder numbers, tuned in the "Economy" stage
HEROES: list[Hero] = [
    Hero("pudge", "Pudge", 0, 1, 0, "/models/pudge/", "pudge.glb"),
    Hero("axe", "Axe", 25_000, 3, 150, "/models/heroes/axe/", "body.glb", ("axe_hair.glb",)),
    Hero("antimage", "Anti-Mage", 90_000, 6, 350, "/models/heroes/antimage/", "body.glb"),
    Hero("drow", "Drow Ranger", 300_000, 10, 700, "/models/heroes/drow/", "body.glb"),
    Hero("invoker", "Invoker", 900_000, 16, 1_300, "/models/heroes/invoker/", "body.glb"),
    Hero("shadow_fiend", "Shadow Fiend", 2_500_000, 25, 2_400, "/models/heroes/shadow_fiend/", "body.glb",
         ("shadow_fiend_wings.glb",)),
]
HERO_BY_ID = {h.id: h for h in HEROES}
DEFAULT_HERO = "pudge"

SLOT_NAMES = {
    "weapon": "Оружие", "offhand": "Тесак", "offhand_weapon": "Второе оружие", "shoulder": "Наплечье",
    "back": "Спина", "belt": "Пояс", "arms": "Наручи", "head": "Голова", "armor": "Броня", "legs": "Ноги",
    "misc": "Колчан", "body_head": "Лицо", "body": "Облик",
}
PUDGE_SLOTS = ["weapon", "offhand", "shoulder", "back", "belt", "arms", "head", "body"]


@dataclass(frozen=True)
class GearSet:
    hero: str
    id: str
    name: str
    tier: int
    models: dict[str, str]  # slot -> model path relative to the hero directory


def _pudge_items(prefix: str, files: dict[str, str]) -> dict[str, str]:
    return {slot: f"items/{prefix}{name}.glb" for slot, name in files.items()}


PUDGE_SETS: list[GearSet] = [
    GearSet("pudge", "default", "Мясник", 0, {
        "weapon": "weapon.glb", "offhand": "leftweapon.glb", "shoulder": "leftarm.glb", "back": "back.glb",
        "belt": "belt.glb", "arms": "bracer.glb", "head": "hair.glb", "body": "pudge.glb"}),
    GearSet("pudge", "trapper", "Капканщик", 1, _pudge_items("trapper_", {
        "weapon": "weapon", "offhand": "offhand", "shoulder": "shoulder", "back": "back", "belt": "belt",
        "arms": "arms", "head": "head"})),
    GearSet("pudge", "war_path", "Тропа войны", 2, {
        "weapon": "items/war_path_mancatcher.glb", "offhand": "items/war_path_off_hand.glb",
        "shoulder": "items/war_path_pauldron.glb", "back": "items/war_path_back.glb",
        "belt": "items/war_path_belt.glb", "arms": "items/warpath_guard.glb", "head": "items/war_path_head.glb"}),
    GearSet("pudge", "dapper", "Джентльмен", 3, _pudge_items("pudge_dapper_disguise_", {
        "weapon": "weapon", "offhand": "off_hand", "shoulder": "shoulder", "back": "back", "belt": "belt",
        "arms": "arms", "head": "head"})),
    GearSet("pudge", "frozen_pig", "Ледяной хряк", 4, _pudge_items("pudge_frozen_pig_face_", {
        "weapon": "weapon", "offhand": "off_hand", "shoulder": "shoulder", "back": "back", "belt": "belt",
        "arms": "arms", "head": "head"})),
    GearSet("pudge", "deep_sea", "Ужас глубин", 5, _pudge_items("pudge_deep_sea_abomination_", {
        "weapon": "weapon", "offhand": "off_hand", "shoulder": "shoulder", "back": "back", "belt": "belt",
        "arms": "arms", "head": "head"})),
    GearSet("pudge", "regrowth", "Запретная поросль", 6, _pudge_items("pudge_forbidden_regrowth_", {
        "weapon": "weapon", "offhand": "offhand_weapon", "shoulder": "shoulder", "back": "back", "belt": "belt",
        "arms": "arms", "head": "head"})),
    GearSet("pudge", "hungry_clown", "Голодный клоун", 7, _pudge_items("pudge_hungry_clown_", {
        "weapon": "weapon", "offhand": "offhand_weapon", "shoulder": "shoulder", "back": "back", "belt": "belt",
        "arms": "arms", "head": "head"})),
    GearSet("pudge", "horrorfest", "Мясник ужасов", 8, _pudge_items("horrorfest_butcher_", {
        "weapon": "weapon", "offhand": "offhand", "shoulder": "shoulder", "back": "back", "belt": "belt",
        "arms": "arm", "head": "head"})),
    GearSet("pudge", "dendi", "Free to Play (Денди)", 9, _pudge_items("ftp_dendi_", {
        "weapon": "weapon", "offhand": "offhand", "shoulder": "shoulder", "back": "back", "belt": "belt",
        "arms": "arm", "head": "head"})),
    GearSet("pudge", "dragonclaw", "Dragonclaw Hook", 10, {"weapon": "items/pudge_skeleton_hook_body.glb"}),
    # An arcana replaces the body itself (it has its own animations); the arcana back piece is part of the look, set on the frontend
    GearSet("pudge", "arcana", "Feast of Abscession", 12, {"body": "pudge_arcana.glb"}),
]


def _load_hero_sets() -> tuple[dict[str, list[str]], list[GearSet]]:
    data = json.loads((Path(__file__).with_name("hero_sets.json")).read_text(encoding="utf-8"))
    slots: dict[str, list[str]] = {"pudge": PUDGE_SLOTS}
    sets: list[GearSet] = list(PUDGE_SETS)
    for hero, h in data.items():
        slots[hero] = h["slots"]
        sets.append(GearSet(hero, "default", "Стандартный", 0, h["default"]))
        sets += [GearSet(hero, s["id"], s["name"], s["tier"], s["parts"]) for s in h["sets"]]
    return slots, sets


HERO_SLOTS, SETS = _load_hero_sets()
SET_BY_KEY = {(g.hero, g.id): g for g in SETS}

# Placeholder numbers, tuned in the "Economy" stage
BASE_PRICE = 1_500
PRICE_GROWTH = 2.3
SET_BONUS_PER_TIER = 0.2
HERO_PRICE_FACTOR = {h.id: 1 + i * 0.6 for i, h in enumerate(HEROES)}  # items of expensive heroes cost more


@dataclass(frozen=True)
class Item:
    id: str  # "<hero>:<set>:<slot>"
    set: GearSet
    slot: str

    @property
    def hero(self) -> str:
        return self.set.hero

    @property
    def power(self) -> int:
        return self.set.tier

    @property
    def price(self) -> int:
        if self.set.tier == 0:
            return 0
        return round(BASE_PRICE * PRICE_GROWTH ** (self.set.tier - 1) * HERO_PRICE_FACTOR[self.hero])

    @property
    def model(self) -> str:
        return HERO_BY_ID[self.hero].dir + self.set.models[self.slot]


ITEMS: dict[str, Item] = {
    f"{g.hero}:{g.id}:{slot}": Item(f"{g.hero}:{g.id}:{slot}", g, slot) for g in SETS for slot in g.models
}


def default_item(hero: str, slot: str) -> str | None:
    key = f"{hero}:default:{slot}"
    return key if key in ITEMS else None


def gear_slots(hero: str) -> list[str]:
    """Slots that make up a set (the look / arcana is not included)."""
    return [s for s in HERO_SLOTS[hero] if s != "body"]


def _all_equipped(u: User) -> dict[str, dict[str, str]]:
    return json.loads(u.equipped) if u.equipped else {}


def equipped(u: User, hero: str) -> dict[str, str | None]:
    data = _all_equipped(u).get(hero) or {}
    out: dict[str, str | None] = {}
    for slot in HERO_SLOTS[hero]:
        item = data.get(slot)
        out[slot] = item if item in ITEMS and ITEMS[item].hero == hero else default_item(hero, slot)
    return out


def full_set(hero: str, eq: dict[str, str | None]) -> GearSet | None:
    """The set, if all its items are equipped and the slots outside the set hold default items."""
    first = eq.get(gear_slots(hero)[0])
    if not first:
        return None
    g = ITEMS[first].set
    if g.tier == 0:
        return None
    for slot in gear_slots(hero):
        want = f"{hero}:{g.id}:{slot}" if slot in g.models else default_item(hero, slot)
        if eq.get(slot) != want:
            return None
    return g


def set_mult(g: GearSet | None) -> float:
    return 1.0 if g is None else 1 + SET_BONUS_PER_TIER * g.tier


def active_hero(u: User) -> str:
    return u.active_hero if u.active_hero in HERO_BY_ID else DEFAULT_HERO


def hero_power(u: User, hero: str) -> int:
    eq = equipped(u, hero)
    base = HERO_BY_ID[hero].power + sum(ITEMS[i].power for i in eq.values() if i)
    return max(1, round(base * set_mult(full_set(hero, eq))))


def tap_power(u: User) -> int:
    return hero_power(u, active_hero(u))


def equip(u: User, item_id: str) -> None:
    item = ITEMS[item_id]
    data = _all_equipped(u)
    data.setdefault(item.hero, {})[item.slot] = item_id
    u.equipped = json.dumps(data)
