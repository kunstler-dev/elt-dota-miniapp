"""Rule-based "coach" in the spirit of Dotabuff: last match breakdown, mistakes, trends, position, heroes, meta.

Pure functions over OpenDota JSON only, no paid LLMs. All player-facing text is in Russian."""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

POS_NAMES = {1: "Pos 1 — керри", 2: "Pos 2 — мидер", 3: "Pos 3 — оффлейнер", 4: "Pos 4 — роумер/саппорт",
             5: "Pos 5 — полный саппорт"}
POS_ROLES = {1: {"Carry"}, 2: {"Nuker", "Carry", "Escape"}, 3: {"Initiator", "Durable"},
             4: {"Support", "Disabler", "Initiator", "Nuker"}, 5: {"Support", "Disabler"}}
LANE_NAMES = {1: "лёгкая", 2: "мид", 3: "сложная", 4: "лес"}
# last-hit targets at minute 10 by position (public games, average rank)
LH10_TARGET = {1: 55, 2: 50, 3: 35, 4: 12, 5: 8}
# key items whose timing we show
KEY_ITEMS = {
    "blink": "Blink Dagger", "black_king_bar": "Black King Bar", "battle_fury": "Battle Fury", "manta": "Manta Style",
    "radiance": "Radiance", "desolator": "Desolator", "maelstrom": "Maelstrom", "mjollnir": "Mjollnir",
    "skadi": "Eye of Skadi", "butterfly": "Butterfly", "satanic": "Satanic", "abyssal_blade": "Abyssal Blade",
    "sange_and_yasha": "Sange and Yasha", "kaya_and_sange": "Kaya and Sange", "yasha_and_kaya": "Yasha and Kaya",
    "orchid": "Orchid Malevolence", "bloodthorn": "Bloodthorn", "ultimate_scepter": "Aghanim's Scepter",
    "aether_lens": "Aether Lens", "force_staff": "Force Staff", "glimmer_cape": "Glimmer Cape",
    "pipe": "Pipe of Insight", "crimson_guard": "Crimson Guard", "vanguard": "Vanguard", "hand_of_midas": "Hand of Midas",
    "armlet": "Armlet", "echo_sabre": "Echo Sabre", "harpoon": "Harpoon", "silver_edge": "Silver Edge",
    "invis_sword": "Shadow Blade", "sphere": "Linken's Sphere", "assault": "Assault Cuirass", "shivas_guard": "Shiva's Guard",
    "refresher": "Refresher Orb", "octarine_core": "Octarine Core", "aghanims_shard": "Aghanim's Shard",
    "spirit_vessel": "Spirit Vessel", "solar_crest": "Solar Crest", "lotus_orb": "Lotus Orb", "guardian_greaves": "Guardian Greaves",
    "travel_boots": "Boots of Travel", "power_treads": "Power Treads", "phase_boots": "Phase Boots", "arcane_boots": "Arcane Boots",
    "tranquil_boots": "Tranquil Boots", "monkey_king_bar": "Monkey King Bar", "daedalus": "Daedalus", "heart": "Heart of Tarrasque",
    "greater_crit": "Daedalus", "basher": "Skull Basher", "diffusal_blade": "Diffusal Blade", "dragon_lance": "Dragon Lance",
    "hurricane_pike": "Hurricane Pike", "witch_blade": "Witch Blade", "eternal_shroud": "Eternal Shroud", "heavens_halberd": "Heaven's Halberd",
    "gungir": "Gleipnir", "disperser": "Disperser", "wind_waker": "Wind Waker", "cyclone": "Eul's Scepter", "rod_of_atos": "Rod of Atos",
    "veil_of_discord": "Veil of Discord", "mekansm": "Mekansm", "bfury": "Battle Fury",
}
CORE_BIG = {"blink", "black_king_bar", "battle_fury", "bfury", "manta", "radiance", "desolator", "maelstrom", "mjollnir",
            "sange_and_yasha", "kaya_and_sange", "yasha_and_kaya", "orchid", "ultimate_scepter", "hand_of_midas",
            "armlet", "echo_sabre", "harpoon", "invis_sword", "diffusal_blade", "dragon_lance", "witch_blade", "skadi"}
FIRST_CORE_TARGET = {1: 17, 2: 15, 3: 18}   # minute by which the first major item should be done
MEDALS = {1: "Рекрут", 2: "Страж", 3: "Рыцарь", 4: "Герой", 5: "Легенда", 6: "Властелин", 7: "Божество", 8: "Титан"}


# ---------------- utilities ----------------
def is_radiant(slot: int) -> bool:
    return (slot or 0) < 128


def won(m: dict) -> bool:
    return bool(m.get("radiant_win")) == is_radiant(m.get("player_slot", 0))


def kda(k, d, a) -> float:
    return round(((k or 0) + (a or 0)) / max(1, d or 0), 2)


def mmss(sec) -> str:
    sec = int(sec or 0)
    return f"{'-' if sec < 0 else ''}{abs(sec) // 60}:{abs(sec) % 60:02d}"


def bracket(rank_tier) -> int:
    """Medal 1..8 (for heroStats `N_pick`/`N_win`). Hidden rank defaults to 5 (Legend, the middle of the distribution)."""
    if not rank_tier:
        return 5
    return max(1, min(8, int(rank_tier) // 10))


def percentile(bench: list[dict], value: float) -> float | None:
    """Share of players on this hero with a stat below value (from /benchmarks)."""
    if not bench or value is None:
        return None
    pts = sorted(((b["percentile"], b["value"]) for b in bench if b.get("value") is not None), key=lambda x: x[1])
    if not pts:
        return None
    if value <= pts[0][1]:
        return round(pts[0][0] * value / pts[0][1], 2) if pts[0][1] else pts[0][0]
    for (p0, v0), (p1, v1) in zip(pts, pts[1:]):
        if value <= v1:
            return round(p0 + (p1 - p0) * (value - v0) / ((v1 - v0) or 1), 2)
    return 0.99


def bench_value(bench: list[dict], p: float = 0.5):
    for b in bench or []:
        if abs(b.get("percentile", 0) - p) < 1e-6:
            return b.get("value")
    return None


def guess_pos(lane_role, lh_per_min: float, obs: int | None = None, is_roaming: bool = False) -> int:
    """Position 1-5 from lane and farm (OpenDota lane_role: 1 safe, 2 mid, 3 off, 4 jungle)."""
    core = lh_per_min >= 3.2
    if is_roaming:
        return 4
    if lane_role == 2:
        return 2 if lh_per_min >= 2.5 else 4
    if lane_role == 1:
        return 1 if core else 5
    if lane_role == 3:
        return 3 if lh_per_min >= 2.3 else 4
    if lane_role == 4:
        return 1 if core else 4
    return 1 if core else (5 if (obs or 0) >= 5 else 4)


def hero_index(hero_stats: list[dict]) -> dict[int, dict]:
    return {h["id"]: h for h in hero_stats or [] if h.get("id")}


def hero_name(heroes: dict, hid) -> str:
    h = heroes.get(hid) or {}
    return h.get("localized_name") or f"Герой #{hid}"


def hero_img(heroes: dict, hid) -> str | None:
    h = heroes.get(hid) or {}
    img = h.get("img")
    return ("https://cdn.cloudflare.steamstatic.com" + img.split("?")[0]) if img else None


def meta_rows(hero_stats: list[dict], b: int, min_pick_share: float = 0.004) -> list[dict]:
    rows = []
    total = sum(h.get(f"{b}_pick") or 0 for h in hero_stats) or 1
    for h in hero_stats:
        p, w = h.get(f"{b}_pick") or 0, h.get(f"{b}_win") or 0
        if p <= 0:
            continue
        rows.append({"hero_id": h["id"], "name": h.get("localized_name"), "roles": h.get("roles") or [],
                     "winrate": round(w / p, 4), "pickrate": round(p * 10 / total, 4), "picks": p})
    return [r for r in rows if r["pickrate"] >= min_pick_share]


# ---------------- last match ----------------
def find_me(match: dict, aid: int) -> dict | None:
    for p in match.get("players") or []:
        if p.get("account_id") == aid:
            return p
    return None


def lane_outcome(match: dict, me: dict) -> dict:
    """Lane result by net worth at minute 10 against opponents in the same lane (needs a parsed match)."""
    if me.get("lane_role") is None or not me.get("gold_t") or len(me["gold_t"]) <= 10:
        eff = me.get("lane_efficiency_pct")
        if eff is None:
            return {"known": False, "text": "Нет данных по линии — матч ещё не разобран"}
        res = "win" if eff >= 70 else "lose" if eff < 50 else "draw"
        return {"known": True, "result": res, "text": _lane_text(res, None), "efficiency": eff}
    my_rad = is_radiant(me.get("player_slot", 0))
    lane = me.get("lane")
    allies = [p for p in match["players"] if is_radiant(p.get("player_slot", 0)) == my_rad and p.get("lane") == lane and p.get("gold_t")]
    enemies = [p for p in match["players"] if is_radiant(p.get("player_slot", 0)) != my_rad and p.get("lane") == lane and p.get("gold_t")]
    if not enemies:
        return {"known": True, "result": "free", "text": "Свободная линия — против тебя никого не было", "diff": 0}
    a = sum(p["gold_t"][10] for p in allies if len(p["gold_t"]) > 10)
    e = sum(p["gold_t"][10] for p in enemies if len(p["gold_t"]) > 10)
    diff = a - e
    rel = diff / max(1, e)
    res = "win" if rel > 0.12 else "lose" if rel < -0.12 else "draw"
    return {"known": True, "result": res, "diff": diff, "text": _lane_text(res, diff)}


def _lane_text(res: str, diff) -> str:
    d = f" ({'+' if diff >= 0 else ''}{diff} золота линии к 10:00)" if diff is not None else ""
    return {"win": "Линия выиграна ✅", "lose": "Линия проиграна ❌", "draw": "Линия вничью ➖"}[res] + d


def item_timings(me: dict) -> list[dict]:
    out, seen = [], set()
    for e in me.get("purchase_log") or []:
        k = e.get("key")
        if k in KEY_ITEMS and k not in seen and (e.get("time") or 0) > 0:
            seen.add(k)
            out.append({"key": k, "name": KEY_ITEMS[k], "time": e["time"], "t": mmss(e["time"])})
    return out[:8]


def match_breakdown(match: dict, aid: int, bench: dict, heroes: dict) -> dict | None:
    me = find_me(match, aid)
    if not me:
        return None
    dur = max(60, match.get("duration") or 0)
    mins = dur / 60
    lh_t = me.get("lh_t") or []
    lh10 = lh_t[10] if len(lh_t) > 10 else None
    obs = me.get("obs_placed")
    sen = me.get("sen_placed")
    pos = guess_pos(me.get("lane_role"), (me.get("last_hits") or 0) / mins, obs, bool(me.get("is_roaming")))
    team_kills = sum((p.get("kills") or 0) for p in match.get("players") or []
                     if is_radiant(p.get("player_slot", 0)) == is_radiant(me.get("player_slot", 0)))
    stats = {
        "gpm": me.get("gold_per_min") or 0, "xpm": me.get("xp_per_min") or 0,
        "last_hits": me.get("last_hits") or 0, "denies": me.get("denies") or 0, "lh10": lh10,
        "hero_damage": me.get("hero_damage") or 0, "tower_damage": me.get("tower_damage") or 0,
        "hero_healing": me.get("hero_healing") or 0, "obs": obs, "sen": sen,
        "kp": round(((me.get("kills") or 0) + (me.get("assists") or 0)) / max(1, team_kills), 2),
    }
    cmp_ = []

    def add(label, key, value, per_min=False):
        b = bench.get(key) or []
        v = value / mins if per_min else value
        pct = percentile(b, v)
        med = bench_value(b, 0.5)
        if med is not None and per_min:
            med = med * mins
        cmp_.append({"label": label, "value": round(value, 1), "median": round(med, 1) if med is not None else None,
                     "pct": pct})

    add("GPM", "gold_per_min", stats["gpm"])
    add("XPM", "xp_per_min", stats["xpm"])
    add("Добивания", "last_hits_per_min", stats["last_hits"], per_min=True)
    add("Урон по героям", "hero_damage_per_min", stats["hero_damage"], per_min=True)
    add("Урон по строениям", "tower_damage", stats["tower_damage"])
    win = won({"radiant_win": match.get("radiant_win"), "player_slot": me.get("player_slot")})
    return {
        "match_id": match.get("match_id"), "hero_id": me.get("hero_id"), "hero": hero_name(heroes, me.get("hero_id")),
        "hero_img": hero_img(heroes, me.get("hero_id")), "win": win, "duration": mmss(dur), "duration_s": dur,
        "start_time": match.get("start_time"), "kills": me.get("kills") or 0, "deaths": me.get("deaths") or 0,
        "assists": me.get("assists") or 0, "kda": kda(me.get("kills"), me.get("deaths"), me.get("assists")),
        "pos": pos, "pos_name": POS_NAMES[pos], "lane_role": me.get("lane_role"),
        "lane_name": LANE_NAMES.get(me.get("lane_role"), "—"), "stats": stats, "benchmarks": cmp_,
        "items": item_timings(me), "lane": lane_outcome(match, me), "parsed": bool(lh_t),
        "deaths_before10": _early_deaths(match, me, heroes),
    }


def _early_deaths(match: dict, me: dict, heroes: dict) -> int:
    npc = (heroes.get(me.get("hero_id")) or {}).get("name")
    if not npc:
        return 0
    my_rad = is_radiant(me.get("player_slot", 0))
    return sum(1 for p in match.get("players") or [] if is_radiant(p.get("player_slot", 0)) != my_rad
               for k in p.get("kills_log") or [] if k.get("key") == npc and (k.get("time") or 9e9) < 600)


def mistakes(b: dict) -> list[dict]:
    """List of mistakes with concrete advice. severity: high | mid | low."""
    out = []
    pos, s, mins = b["pos"], b["stats"], b["duration_s"] / 60
    core = pos <= 3
    pct = {c["label"]: c["pct"] for c in b["benchmarks"]}

    def m(sev, title, tip):
        out.append({"severity": sev, "title": title, "tip": tip})

    if b["deaths"] >= max(7, round(mins / 5)):
        m("high", f"Много смертей: {b['deaths']}",
          "Перед каждым выходом на карту смотри миникарту: если 2+ врагов пропали — не фарми дальнюю линию. "
          "Покупай ТП и держи его в слоте, а предмет на выживание (BKB/Force/Glimmer) — раньше второго «урона».")
    if b["lane"].get("result") == "lose":
        m("high" if core else "mid", "Проигранная линия",
          "Возьми 2 танго + лишний Healing Salve, добивай под своей вышкой и вызывай саппорта на ротацию к 3–5 минуте. "
          "Если линия совсем не стоит — уходи в лес/на другую линию с 7–8 минуты вместо смертей.")
    if core and s["lh10"] is not None and s["lh10"] < LH10_TARGET[pos] * 0.8:
        m("high", f"Мало добиваний к 10:00: {s['lh10']} (цель ~{LH10_TARGET[pos]})",
          "10 минут в демо-режиме каждый день: добивание с атаки по таймингу анимации, отвод крипов на 0:30. "
          "На линии не трать ману на харас, если это стоит тебе добиваний.")
    if core and (pct.get("GPM") or 1) < 0.3:
        m("high", f"Низкий фарм: {s['gpm']} GPM (хуже {int((1 - pct['GPM']) * 100)}% игр на этом герое)",
          "Между драками всегда фарми ближайший лагерь или линию: в паблике цель ядра — 0 секунд «простоя». "
          "Стакай/фарми древних, если герой это умеет, и не ходи в драки без ключевого предмета.")
    if core and (pct.get("XPM") or 1) < 0.3:
        m("mid", f"Мало опыта: {s['xpm']} XPM", "Не пропускай волны крипов на линиях с вышками: опыт — это уровни для драк.")
    if (pct.get("Урон по героям") or 1) < 0.25 and pos != 5:
        m("mid", "Низкий урон по героям", "Ищи драки, где твоя команда сильнее (после ключевого таймингa/рошана), "
          "и стой на дистанции атаки, а не позади команды.")
    if core and (pct.get("Урон по строениям") or 1) < 0.25 and b["win"] is False:
        m("mid", "Мало урона по строениям", "После выигранной драки сразу бей вышку/барак, а не иди фармить лес — "
          "в паблике игры выигрывают строения, а не убийства.")
    if pos >= 4 and s["obs"] is not None and s["obs"] < max(3, mins / 6):
        m("high", f"Мало вардов: {s['obs']} observer за {int(mins)} мин",
          "Саппорт ставит обсервер почти каждый раз, когда он есть в лавке (~каждые 2–3 мин). "
          "Ставь варды перед своими таймингами (рошан, смок, пуш), а не после.")
    if pos >= 4 and s["sen"] is not None and s["sen"] < 2 and mins > 25:
        m("low", "Почти нет сентри", "1–2 сентри на ключевые точки врага сильно снижают ганки и защищают твоих ядер.")
    if s["kp"] < 0.4 and mins > 20:
        m("mid", f"Мало участия в убийствах: {int(s['kp'] * 100)}%",
          "Держи ТП и реагируй на драки на линиях. Для саппорта: после 10 минуты ходи с ядрами, а не один по карте.")
    first = next((i for i in b["items"] if i["key"] in CORE_BIG), None)
    if core and first and first["time"] > FIRST_CORE_TARGET[pos] * 60 + 180:
        m("mid", f"Поздний первый крупный предмет: {first['name']} в {first['t']}",
          f"Для {POS_NAMES[pos].split(' — ')[1]} ориентир — до {FIRST_CORE_TARGET[pos]}:00. Не покупай лишние расходники/"
          "ветки после линии и фарми лагеря рядом с линией между волнами.")
    if b["deaths_before10"] >= 3:
        m("high", f"{b['deaths_before10']} смерти до 10:00", "Ранние смерти отдают врагу линию и руны. Играй от вышки, "
          "пока у врага есть ротации, и следи за рунами на 2:00/4:00.")
    out.sort(key=lambda x: {"high": 0, "mid": 1, "low": 2}[x["severity"]])
    return out


# ---------------- trends over the last 20 ----------------
def trends(recent: list[dict], heroes: dict) -> dict:
    ms = recent[:20]
    if not ms:
        return {"games": 0}
    wins = [won(m) for m in ms]
    gpm = [m.get("gold_per_min") or 0 for m in ms]
    xpm = [m.get("xp_per_min") or 0 for m in ms]
    deaths = [m.get("deaths") or 0 for m in ms]
    kd = [kda(m.get("kills"), m.get("deaths"), m.get("assists")) for m in ms]
    half = len(ms) // 2 or 1
    new, old = ms[:half], ms[half:] or ms[:half]

    def avg(rows, f):
        return round(mean(f(m) for m in rows), 1) if rows else 0

    streak, sw = 0, wins[0]
    for w in wins:
        if w != sw:
            break
        streak += 1
    hc = Counter(m.get("hero_id") for m in ms)
    top = []
    for hid, n in hc.most_common(5):
        w = sum(1 for m in ms if m.get("hero_id") == hid and won(m))
        top.append({"hero_id": hid, "name": hero_name(heroes, hid), "img": hero_img(heroes, hid), "games": n,
                    "winrate": round(w / n, 2)})
    return {
        "games": len(ms), "wins": sum(wins), "winrate": round(sum(wins) / len(ms), 2),
        "avg": {"kda": round(mean(kd), 2), "gpm": round(mean(gpm)), "xpm": round(mean(xpm)), "deaths": round(mean(deaths), 1)},
        "delta": {"gpm": avg(new, lambda m: m.get("gold_per_min") or 0) - avg(old, lambda m: m.get("gold_per_min") or 0),
                  "deaths": round(avg(new, lambda m: m.get("deaths") or 0) - avg(old, lambda m: m.get("deaths") or 0), 1),
                  "winrate": round(sum(won(m) for m in new) / len(new) - sum(won(m) for m in old) / len(old), 2)},
        "streak": {"win": sw, "n": streak},
        "series": [{"win": w, "gpm": g, "kda": k, "hero_id": m.get("hero_id")} for w, g, k, m in zip(wins, gpm, kd, ms)][::-1],
        "heroes": top, "distinct_heroes": len(hc),
        "party_share": round(sum(1 for m in ms if (m.get("party_size") or 1) > 1) / len(ms), 2),
    }


# ---------------- best position ----------------
def positions(recent: list[dict]) -> dict:
    by = defaultdict(list)
    for m in recent[:20]:
        mins = max(1, (m.get("duration") or 60) / 60)
        p = guess_pos(m.get("lane_role"), (m.get("last_hits") or 0) / mins, None, bool(m.get("is_roaming")))
        by[p].append(m)
    rows = []
    for p in range(1, 6):
        ms = by.get(p, [])
        n = len(ms)
        w = sum(won(m) for m in ms)
        wr_s = (w + 2.5) / (n + 5)                         # Bayesian smoothing toward 50%
        impact = mean(kda(m.get("kills"), m.get("deaths"), m.get("assists")) for m in ms) if ms else 0
        score = wr_s * 100 + min(impact, 6) * 2 + min(n, 15) * 1.0
        rows.append({"pos": p, "name": POS_NAMES[p], "games": n, "winrate": round(w / n, 2) if n else None,
                     "kda": round(impact, 2), "score": round(score, 1)})
    played = [r for r in rows if r["games"]]
    best = max(played or rows, key=lambda r: r["score"])
    most = max(rows, key=lambda r: r["games"])
    why = [f"{best['games']} игр на этой позиции из последних {sum(r['games'] for r in rows)}"]
    if best["winrate"] is not None:
        why.append(f"винрейт {int(best['winrate'] * 100)}% и KDA {best['kda']}")
    if most["pos"] != best["pos"] and most["games"]:
        mw = int((most["winrate"] or 0) * 100)
        why.append(f"чаще всего ты играешь {most['name'].split(' — ')[0]} ({most['games']} игр, {mw}% побед), "
                   f"но на {best['name'].split(' — ')[0]} результат лучше — попробуй сделать её основной")
    return {"best": best["pos"], "name": best["name"], "rows": rows, "explanation": "; ".join(why) + "."}


# ---------------- heroes ----------------
def ideal_heroes(pos: int, hero_stats: list[dict], player_heroes: list[dict], recent: list[dict], b: int) -> dict:
    heroes = hero_index(hero_stats)
    meta = {r["hero_id"]: r for r in meta_rows(hero_stats, b)}
    comfort = {}
    for h in player_heroes or []:
        g = h.get("games") or 0
        if g:
            comfort[int(h["hero_id"])] = {"games": g, "winrate": (h.get("win") or 0) / g}
    roles = POS_ROLES[pos]
    cands = []
    for hid, mr in meta.items():
        hroles = set(mr["roles"])
        if not hroles & roles:
            continue
        if pos in (4, 5) and "Support" not in hroles and pos == 5:
            continue
        if pos == 1 and "Carry" not in hroles:
            continue
        c = comfort.get(hid, {"games": 0, "winrate": 0.5})
        my_wr = (c["winrate"] * c["games"] + 0.5 * 5) / (c["games"] + 5)
        score = (mr["winrate"] - 0.5) * 100 * 1.4 + (my_wr - 0.5) * 100 + min(c["games"], 30) * 0.15 + mr["pickrate"] * 20
        reason = [f"винрейт {mr['winrate'] * 100:.1f}% на {MEDALS[b]}"]
        if c["games"] >= 3:
            reason.append(f"у тебя {c['games']} игр, {int(c['winrate'] * 100)}% побед")
        else:
            reason.append(f"роль: {', '.join(sorted(hroles & roles))}")
        cands.append({"hero_id": hid, "name": mr["name"], "img": hero_img(heroes, hid), "score": round(score, 1),
                      "meta_winrate": mr["winrate"], "my_games": c["games"], "reason": ", ".join(reason)})
    cands.sort(key=lambda x: -x["score"])
    drop = []
    for hid, c in comfort.items():
        mr = meta.get(hid)
        if c["games"] >= 8 and c["winrate"] < 0.45:
            drop.append({"hero_id": hid, "name": hero_name(heroes, hid), "img": hero_img(heroes, hid), "games": c["games"],
                         "winrate": round(c["winrate"], 2),
                         "reason": f"{int(c['winrate'] * 100)}% побед за {c['games']} игр"
                                   + (f", в мете {mr['winrate'] * 100:.1f}%" if mr else "")})
    drop.sort(key=lambda x: (x["winrate"], -x["games"]))
    return {"top": cands[:3], "drop": drop[:3]}


def meta_for_rank(hero_stats: list[dict], b: int, pos: int | None = None) -> dict:
    rows = meta_rows(hero_stats, b)
    rows = [r for r in rows if r["pickrate"] >= 0.03] or rows
    best = sorted(rows, key=lambda r: -r["winrate"])[:8]
    worst = sorted(rows, key=lambda r: r["winrate"])[:5]
    heroes = hero_index(hero_stats)
    f = lambda r: {"hero_id": r["hero_id"], "name": r["name"], "img": hero_img(heroes, r["hero_id"]),  # noqa: E731
                   "winrate": r["winrate"], "pickrate": r["pickrate"]}
    return {"bracket": b, "bracket_name": MEDALS[b], "best": [f(r) for r in best], "worst": [f(r) for r in worst]}


# ---------------- how to gain MMR ----------------
def mmr_tips(tr: dict, pos_info: dict, last: dict | None, errs: list[dict]) -> list[dict]:
    tips = []
    if not tr.get("games"):
        return [{"title": "Сыграй пару матчей", "text": "Нужна история хотя бы из нескольких игр с открытой статистикой."}]
    a = tr["avg"]
    if a["deaths"] >= 7:
        tips.append({"title": "Умирай меньше — это самый быстрый +ММР",
                     "text": f"В среднем {a['deaths']} смертей за игру. Цель — ≤5: каждая смерть = ~300–600 золота врагу "
                             "и минута без фарма. Правило: нет обзора на 2+ врагов — ты не на их половине карты."})
    if tr["distinct_heroes"] >= 10:
        tips.append({"title": "Сузь пул героев до 3–4",
                     "text": f"{tr['distinct_heroes']} разных героев за {tr['games']} игр. Стабильный рост ММР — "
                             "это 3–4 героя на 1–2 позиции: ты знаешь их тайминги и сильные окна."})
    rows = [r for r in pos_info["rows"] if r["games"]]
    if len(rows) >= 4:
        tips.append({"title": f"Играй в основном {pos_info['name']}",
                     "text": "Ты играешь почти все позиции. Выбирай свою позицию в подборе с ролями, "
                             "а на остальных бери простых и сильных в мете героев."})
    if tr["streak"]["n"] >= 3 and not tr["streak"]["win"]:
        tips.append({"title": "Стоп после 2 поражений подряд",
                     "text": f"Сейчас серия из {tr['streak']['n']} поражений. Тилт стоит больше ММР, чем любые ошибки: "
                             "после двух лузов — перерыв 20–30 минут или анализ записи."})
    if last and last["pos"] <= 3:
        gpm_pct = next((c["pct"] for c in last["benchmarks"] if c["label"] == "GPM"), None)
        if gpm_pct is not None and gpm_pct < 0.4:
            tips.append({"title": "Фарм — твоя главная точка роста",
                         "text": "GPM ниже медианы для героя. Учись «фармить по кругу»: линия → ближний лагерь → "
                                 "вторая линия, и не стой без дела после драк."})
    if last and last["pos"] >= 4 and last["stats"].get("obs") is not None and last["stats"]["obs"] < 8:
        tips.append({"title": "Обзор выигрывает игры на твоей позиции",
                     "text": "Обсерверы на ходах к рошану и в лес врага до таймингов команды — и меньше смертей у ядер."})
    if tr["winrate"] >= 0.55:
        tips.append({"title": "Ты в форме — играй больше сейчас",
                     "text": f"{int(tr['winrate'] * 100)}% побед за последние игры: это лучшее время для каток на ММР."})
    if tr.get("party_share", 0) > 0.6 and tr["winrate"] < 0.5:
        tips.append({"title": "Попробуй соло-игры", "text": "Большинство последних игр — в пати, и винрейт ниже 50%. "
                     "В пати против тебя подбирают более сильных соперников."})
    for e in errs[:2]:
        if len(tips) >= 5:
            break
        tips.append({"title": "Исправь: " + e["title"].split(":")[0].lower(), "text": e["tip"]})
    generic = [
        {"title": "Смотри свои проигрыши", "text": "Разбери 1 проигранный матч в неделю: найди 3 смерти, которых можно было избежать."},
        {"title": "Покупай ТП всегда", "text": "Свиток телепорта в слоте спасает вышки и даёт участвовать в драках по всей карте."},
        {"title": "Играй от таймингов", "text": "Знай, когда твой герой сильнее всего (предмет/уровень), и форсируй драки в это окно."},
    ]
    for g in generic:
        if len(tips) >= 3:
            break
        tips.append(g)
    return tips[:5]


def build_report(*, aid: int, player: dict, recent: list, match: dict | None, bench: dict, hero_stats: list,
                 player_heroes: list) -> dict:
    heroes = hero_index(hero_stats)
    rank_tier = (player or {}).get("rank_tier")
    medal = b = bracket(rank_tier)
    while b > 1 and not any(h.get(f"{b}_pick") for h in hero_stats or []):   # OpenDota doesn't return Titan statistics
        b -= 1
    last = match_breakdown(match, aid, bench, heroes) if match else None
    errs = mistakes(last) if last else []
    tr = trends(recent, heroes)
    pos = positions(recent)
    ih = ideal_heroes(pos["best"], hero_stats, player_heroes, recent, b)
    prof = (player or {}).get("profile") or {}
    return {"profile": {"name": prof.get("personaname"), "avatar": prof.get("avatarfull"), "rank_tier": rank_tier,
                        "bracket": medal, "bracket_name": MEDALS[medal], "account_id": aid},
            "last": last, "mistakes": errs, "trends": tr, "position": pos, "heroes": ih,
            "meta": meta_for_rank(hero_stats, b), "tips": mmr_tips(tr, pos, last, errs)}
