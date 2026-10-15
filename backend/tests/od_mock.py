"""OpenDota mock data for tests and the Analysis tab screenshot."""
AID = 123456789
STEAMID = str(76561197960265728 + AID)
NAMES = {1: ("Anti-Mage", ["Carry", "Escape", "Nuker"]), 8: ("Juggernaut", ["Carry", "Pusher", "Escape"]),
         11: ("Shadow Fiend", ["Carry", "Nuker"]), 14: ("Pudge", ["Disabler", "Initiator", "Durable", "Nuker"]),
         26: ("Lion", ["Support", "Disabler", "Nuker", "Initiator"]), 5: ("Crystal Maiden", ["Support", "Disabler", "Nuker"]),
         48: ("Luna", ["Carry", "Nuker", "Pusher"]), 97: ("Magnus", ["Initiator", "Disabler", "Nuker", "Escape"]),
         44: ("Phantom Assassin", ["Carry", "Escape"]), 129: ("Mars", ["Carry", "Initiator", "Disabler", "Durable"])}
WR = {1: .47, 8: .53, 11: .49, 14: .50, 26: .52, 5: .51, 48: .545, 97: .505, 44: .515, 129: .525}


def hero_stats():
    out = []
    for hid, (n, roles) in NAMES.items():
        short = n.lower().replace(" ", "_").replace("-", "")
        short = {"shadow_fiend": "nevermore", "magnus": "magnataur", "phantom_assassin": "phantom_assassin"}.get(short, short)
        h = {"id": hid, "localized_name": n, "name": "npc_dota_hero_" + short,
             "roles": roles, "img": f"/apps/dota2/images/dota_react/heroes/{short}.png?"}
        for b in range(1, 9):
            h[f"{b}_pick"] = 20000
            h[f"{b}_win"] = int(20000 * WR[hid])
        out.append(h)
    return out


def recent():
    rows = []
    heroes = [8] * 6 + [1] * 5 + [48] * 4 + [14] * 3 + [26] * 2
    for i, hid in enumerate(heroes):
        rows.append({"match_id": 8000000000 - i, "player_slot": 0 if i % 2 else 130, "radiant_win": i % 3 != 0,
                     "duration": 2400, "hero_id": hid, "kills": 6, "deaths": 9 if i < 8 else 6, "assists": 8,
                     "gold_per_min": 420 + i * 5, "xp_per_min": 520, "last_hits": 200 if hid in (8, 1, 48) else 60,
                     "lane_role": 1 if hid in (8, 1, 48) else 3, "hero_damage": 18000, "party_size": 1})
    return rows


def bench(lo=False):
    def s(vals):
        return [{"percentile": p, "value": v} for p, v in zip((0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99), vals)]
    return {"result": {"gold_per_min": s([350, 400, 440, 470, 500, 530, 560, 600, 650, 700, 800]),
                       "xp_per_min": s([400, 450, 490, 520, 550, 580, 610, 650, 700, 750, 850]),
                       "last_hits_per_min": s([3, 4, 4.6, 5.1, 5.6, 6, 6.5, 7, 7.8, 8.5, 10]),
                       "hero_damage_per_min": s([250, 320, 380, 430, 480, 530, 590, 660, 760, 850, 1000]),
                       "tower_damage": s([200, 600, 1000, 1500, 2000, 2600, 3300, 4200, 5500, 7000, 10000])}}


def match(parsed=True):
    mid = 8000000000
    players = []
    for i in range(10):
        slot = i if i < 5 else 128 + i - 5
        p = {"account_id": None, "player_slot": slot, "hero_id": [8, 26, 97, 129, 5, 44, 14, 11, 1, 48][i], "kills": 3,
             "deaths": 5, "assists": 6, "gold_per_min": 450, "xp_per_min": 500, "last_hits": 150, "hero_damage": 15000,
             "tower_damage": 1000, "lane": 1 if i in (0, 4, 5, 9) else 3 if i in (3, 6, 8) else 2, "lane_role": 1}
        if parsed:
            p.update(gold_t=[i * 300 for i in range(41)], lh_t=[i * 5 for i in range(41)], obs_placed=1, sen_placed=0,
                     purchase_log=[{"time": 900, "key": "power_treads"}, {"time": 1500, "key": "battle_fury"}],
                     kills_log=[])
        players.append(p)
    me = players[3]                      # Mars, off lane -> in the game he is pos 3 offlaner
    me.update(account_id=AID, player_slot=3, hero_id=8, kills=4, deaths=11, assists=5, gold_per_min=380, xp_per_min=430,
              last_hits=140, hero_damage=11000, tower_damage=300, lane=1, lane_role=1)
    if parsed:
        me.update(lh_t=[i * 3 for i in range(41)], gold_t=[i * 250 for i in range(41)],
                  purchase_log=[{"time": 600, "key": "power_treads"}, {"time": 1560, "key": "battle_fury"},
                                {"time": 2100, "key": "manta"}])
        players[5]["gold_t"] = players[9]["gold_t"] = [i * 500 for i in range(41)]
        players[5]["kills_log"] = [{"time": 300, "key": "npc_dota_hero_juggernaut"}, {"time": 420, "key": "npc_dota_hero_juggernaut"},
                                   {"time": 560, "key": "npc_dota_hero_juggernaut"}]
    return {"match_id": mid, "duration": 2400, "radiant_win": False, "start_time": 1760000000,
            "version": 21 if parsed else None, "players": players}


def player(private=False):
    if private:
        return {"profile": None}
    return {"profile": {"personaname": "ELT Tester", "avatarfull": None, "account_id": AID}, "rank_tier": 54}


def player_heroes():
    return [{"hero_id": "8", "games": 60, "win": 34}, {"hero_id": "1", "games": 40, "win": 15},
            {"hero_id": "48", "games": 20, "win": 12}, {"hero_id": "14", "games": 10, "win": 5}]


class FakeOD:
    """fetch(method, path) -> (status, json); counts calls."""

    def __init__(self, private=False, parsed=True, status=200):
        self.private, self.parsed, self.status, self.calls = private, parsed, status, []

    async def __call__(self, method, path):
        self.calls.append((method, path))
        if self.status != 200:
            return self.status, None
        if method == "POST" and path.startswith("/request/"):
            return 200, {"job": {"jobId": 1}}
        if path == f"/players/{AID}":
            return 200, player(self.private)
        if path.endswith("/recentMatches"):
            return 200, [] if self.private else recent()
        if path.startswith(f"/players/{AID}/heroes"):
            return 200, player_heroes()
        if path.startswith("/matches/"):
            return 200, match(self.parsed)
        if path.startswith("/benchmarks"):
            return 200, bench()
        if path == "/heroStats":
            return 200, hero_stats()
        return 404, None
