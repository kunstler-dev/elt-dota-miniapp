"""Draft duel: Captains Mode 5v5, position placement and a transparent outcome calculation.

The outcome is deterministic (owner decision 2026-10-15): more points wins; there are no draws,
and only an exact tie is decided by a coin flip.
Team points are the sum of five parts, each shown in the breakdown with reasons:
  1) meta: hero win rates at high rank (OpenDota);
  2) counters: how well the team's heroes beat the specific enemy heroes (OpenDota matchups);
  3) positions: whether a hero fits the position it was placed on (by hero roles);
  4) composition: carry, supports, initiation, disables, tank, push, melee/ranged mix;
  5) role synergy within the team (initiator + AoE damage, disables + damage, etc.).
The module has no DB or HTTP; only hero data goes in."""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field

# Captains Mode order (A is the first team): 7 bans and 5 picks each, 24 turns
SEQUENCE: list[tuple[str, str]] = (
    [("ban", s) for s in "ABABAB"] + [("pick", s) for s in "ABBA"]
    + [("ban", s) for s in "ABAB"] + [("pick", s) for s in "BAAB"]
    + [("ban", s) for s in "ABAB"] + [("pick", s) for s in "AB"]
)
TURN_MS = 30_000          # per turn
PLACE_MS = 45_000         # for position placement

POSITIONS = (1, 2, 3, 4, 5)
POS_NAMES = {1: "Керри", 2: "Мид", 3: "Оффлейн", 4: "Роумер", 5: "Саппорт"}
# Which hero roles fit a position (OpenDota roles): a full match is a primary role, a partial one is acceptable
POS_ROLES = {
    1: ({"Carry"}, {"Escape", "Pusher"}),
    2: ({"Nuker", "Carry"}, {"Escape", "Pusher", "Initiator"}),
    3: ({"Initiator", "Durable"}, {"Disabler", "Carry", "Pusher"}),
    4: ({"Support", "Initiator"}, {"Disabler", "Nuker", "Escape"}),
    5: ({"Support"}, {"Disabler", "Nuker"}),
}


@dataclass(frozen=True)
class Hero:
    id: int
    name: str
    roles: frozenset[str]
    attack: str           # Melee | Ranged
    attr: str             # str | agi | int | all
    winrate: float        # high rank, 0..1
    img: str = ""


@dataclass
class Data:
    heroes: dict[int, Hero]
    # matchups[(a, b)] = (games, wins of hero a against b)
    matchups: dict[tuple[int, int], tuple[int, int]] = field(default_factory=dict)


@dataclass
class Part:
    key: str
    title: str
    points: float
    reasons: list[str]


# ---------------- draft moves ----------------
def turn(step: int) -> tuple[str, str] | None:
    return SEQUENCE[step] if step < len(SEQUENCE) else None


def taken(actions: list[dict]) -> set[int]:
    return {a["hero"] for a in actions}


def picks(actions: list[dict], side: str) -> list[int]:
    return [a["hero"] for a in actions if a["kind"] == "pick" and a["side"] == side]


def validate(data: Data, actions: list[dict], side: str, hero: int) -> str | None:
    """None if the move is allowed, otherwise an error code."""
    t = turn(len(actions))
    if t is None:
        return "draft_over"
    if t[1] != side:
        return "not_your_turn"
    if hero not in data.heroes:
        return "unknown_hero"
    if hero in taken(actions):
        return "hero_taken"
    return None


# ---------------- scoring ----------------
def _pos_fit(h: Hero, pos: int) -> float:
    main, ok = POS_ROLES[pos]
    if h.roles & main:
        return 1.0
    if h.roles & ok:
        return 0.4
    return 0.0


def best_positions(data: Data, team: list[int]) -> list[int]:
    """Best placement (positions 1..5 in order), for the bot and when time runs out."""
    best, best_s = list(team), -1e9
    for perm in itertools.permutations(team):
        s = sum(_pos_fit(data.heroes[h], p) for h, p in zip(perm, POSITIONS))
        if s > best_s:
            best, best_s = list(perm), s
    return best


def _counter(data: Data, a: int, b: int) -> float:
    """Advantage of hero a over b in percentage points relative to a's overall win rate; with few games
    it is smoothed toward zero (n / (n + 300)) and capped at ±8."""
    games, wins = data.matchups.get((a, b), (0, 0))
    if games <= 0:
        return 0.0
    adv = (wins / games - data.heroes[a].winrate) * 100
    adv *= games / (games + 300)
    return max(-8.0, min(8.0, adv))


def _meta(data: Data, team: list[int]) -> Part:
    pts, reasons = 0.0, []
    for h in team:
        hero = data.heroes[h]
        d = (hero.winrate - 0.5) * 100
        pts += d
        if abs(d) >= 1.5:
            reasons.append(f"{hero.name}: винрейт {hero.winrate * 100:.1f}% ({d:+.1f})")
    return Part("meta", "Сила героев в мете", round(pts, 2), reasons)


def _counters(data: Data, team: list[int], enemy: list[int]) -> Part:
    pairs = [(a, b, _counter(data, a, b)) for a in team for b in enemy]
    pts = sum(v for _, _, v in pairs) / len(enemy)
    top = sorted(pairs, key=lambda x: -abs(x[2]))[:4]
    reasons = [f"{data.heroes[a].name} {'контрит' if v > 0 else 'уступает'} {data.heroes[b].name} ({v:+.1f})"
               for a, b, v in top if abs(v) >= 1.0]
    return Part("counters", "Контрпики", round(pts, 2), reasons)


def _positions(data: Data, order: list[int]) -> Part:
    pts, reasons = 0.0, []
    for h, p in zip(order, POSITIONS):
        f = _pos_fit(data.heroes[h], p)
        v = 2.0 if f == 1.0 else 0.0 if f > 0 else -3.0
        pts += v
        if v < 2.0:
            reasons.append(f"{data.heroes[h].name} на позиции {p} ({POS_NAMES[p]}): "
                           f"{'не основная роль' if v == 0 else 'не подходит'} ({v:+.0f})")
    return Part("positions", "Позиции", pts, reasons)


def _roles(data: Data, team: list[int]) -> tuple[dict[str, int], list[str]]:
    count: dict[str, int] = {}
    for h in team:
        for r in data.heroes[h].roles:
            count[r] = count.get(r, 0) + 1
    attacks = [data.heroes[h].attack for h in team]
    return count, attacks


# (role, how many are needed, bonus if present, penalty if missing, description)
COMPOSITION = [
    ("Carry", 1, 2.0, -4.0, "керри"),
    ("Support", 2, 2.0, -3.0, "два саппорта"),
    ("Initiator", 1, 2.0, -3.0, "инициация"),
    ("Disabler", 2, 2.0, -2.0, "контроль (2+ героя)"),
    ("Durable", 1, 1.0, -2.0, "танк"),
    ("Pusher", 1, 1.0, 0.0, "пуш строений"),
]


def _composition(data: Data, team: list[int]) -> Part:
    count, attacks = _roles(data, team)
    pts, reasons = 0.0, []
    for role, need, bonus, penalty, text in COMPOSITION:
        if count.get(role, 0) >= need:
            pts += bonus
        else:
            pts += penalty
            if penalty:
                reasons.append(f"нет: {text} ({penalty:+.0f})")
    melee = attacks.count("Melee")
    if melee == 0 or melee == 5:
        pts -= 1.0
        reasons.append(f"все герои {'дальнего' if melee == 0 else 'ближнего'} боя (−1)")
    else:
        pts += 1.0
    return Part("composition", "Состав", pts, reasons)


def _synergy(data: Data, team: list[int]) -> Part:
    count, _ = _roles(data, team)
    pts, reasons = 0.0, []
    if count.get("Initiator", 0) and count.get("Nuker", 0) >= 2:
        pts += 2.0
        reasons.append("инициация + массовый урон (+2)")
    if count.get("Disabler", 0) >= 2 and count.get("Carry", 0):
        pts += 1.5
        reasons.append("контроль прикрывает керри (+1.5)")
    if count.get("Escape", 0) >= 3:
        pts -= 1.0
        reasons.append("слишком много героев на побег, мало боя (−1)")
    if count.get("Nuker", 0) == 0:
        pts -= 1.5
        reasons.append("нет магического урона (−1.5)")
    return Part("synergy", "Синергия", pts, reasons)


def score(data: Data, team_order: list[int], enemy: list[int]) -> tuple[float, list[Part]]:
    """Team points (heroes in position order 1..5) against the opponent's lineup."""
    parts = [_meta(data, team_order), _counters(data, team_order, enemy), _positions(data, team_order),
             _composition(data, team_order), _synergy(data, team_order)]
    return round(sum(p.points for p in parts), 2), parts


def resolve(data: Data, a_order: list[int], b_order: list[int], seed: str = "") -> dict:
    """The winner has more points. No draws: only an exact tie is decided by a coin flip (match seed)."""
    sa, pa = score(data, a_order, b_order)
    sb, pb = score(data, b_order, a_order)
    coin = sa == sb
    winner = "A" if sa > sb else "B" if sb > sa else random.Random(seed).choice("AB")
    as_dict = lambda parts: [p.__dict__ for p in parts]  # noqa: E731
    # main reasons for the advantage: the parts with the biggest difference
    diffs = sorted(((x.title, round(x.points - y.points, 2)) for x, y in zip(pa, pb)), key=lambda t: -abs(t[1]))
    return {"A": {"score": sa, "parts": as_dict(pa)}, "B": {"score": sb, "parts": as_dict(pb)},
            "winner": winner, "coin": coin, "diff": round(abs(sa - sb), 2),
            "decisive": [d for d in diffs if d[1] != 0][:3]}


# ---------------- bot ----------------
def bot_choice(data: Data, actions: list[dict], side: str, skill: float, rng: random.Random) -> int:
    """Bot move: scores every free hero by point margin (for a pick) or by threat (for a ban).
    skill 0..1: the higher, the closer to the best move (a weak bot picks from a wide top list)."""
    kind = turn(len(actions))[0]
    free = [h for h in data.heroes if h not in taken(actions)]
    other = "B" if side == "A" else "A"
    mine, theirs = picks(actions, side), picks(actions, other)

    def value(h: int, for_side_mine: list[int], vs: list[int]) -> float:
        hero = data.heroes[h]
        v = (hero.winrate - 0.5) * 100
        v += sum(_counter(data, h, e) for e in vs) / max(1, len(vs)) * 1.5 if vs else 0
        if for_side_mine:
            have, _ = _roles(data, for_side_mine)
            for role, need, bonus, penalty, _t in COMPOSITION:
                if role in hero.roles and have.get(role, 0) < need:
                    v += bonus + (-penalty) * 0.5
        return v

    if kind == "pick":
        scored = sorted(free, key=lambda h: -value(h, mine, theirs))
    else:  # ban: remove whatever would strengthen the opponent most
        scored = sorted(free, key=lambda h: -value(h, theirs, mine))
    width = max(1, int(round(1 + (1 - skill) * 12)))
    return rng.choice(scored[:width])
