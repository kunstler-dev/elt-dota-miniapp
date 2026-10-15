import json
import random

from app.game import balance as B
from app.game import draft as D
from app.models import DraftMatch, DraftMonth, DraftQueue, DraftRating, User

from .conftest import player

ROLES = [
    {"Carry", "Escape"}, {"Carry", "Pusher"}, {"Nuker", "Carry"}, {"Nuker", "Escape"}, {"Initiator", "Durable"},
    {"Initiator", "Disabler", "Durable"}, {"Support", "Disabler"}, {"Support", "Nuker"}, {"Support", "Initiator"},
    {"Support", "Disabler", "Nuker"},
]


def fake_data(n=30) -> D.Data:
    heroes = {i: D.Hero(id=i, name=f"H{i}", roles=frozenset(ROLES[i % len(ROLES)]),
                        attack="Melee" if i % 3 else "Ranged", attr="str", winrate=0.46 + (i % 9) / 100)
              for i in range(1, n + 1)}
    r = random.Random(7)
    matchups = {}
    for a in heroes:
        for b in heroes:
            if a != b:
                g = 1000
                matchups[(a, b)] = (g, int(g * (heroes[a].winrate + (r.random() - 0.5) * 0.1)))
    return D.Data(heroes=heroes, matchups=matchups)


def test_sequence_and_resolve_is_explained():
    assert len(D.SEQUENCE) == 24
    assert sum(1 for k, s in D.SEQUENCE if k == "pick" and s == "A") == 5
    assert sum(1 for k, s in D.SEQUENCE if k == "ban" and s == "B") == 7
    data = fake_data()
    a = D.best_positions(data, [1, 3, 5, 7, 8])
    b = D.best_positions(data, [2, 4, 6, 9, 10])
    res = D.resolve(data, a, b, seed="x")
    assert res["winner"] in ("A", "B") and not res["coin"]
    win, lose = (res["A"], res["B"]) if res["winner"] == "A" else (res["B"], res["A"])
    assert win["score"] > lose["score"]                      # more points wins
    assert {p["key"] for p in res["A"]["parts"]} == {"meta", "counters", "positions", "composition", "synergy"}
    assert res["decisive"]                                    # there is an explanation of what decided it
    # mirror lineup -> equal points -> coin flip, but never a draw
    same = D.resolve(data, a, a, seed="m1")
    assert same["coin"] and same["winner"] in ("A", "B")


def test_positions_matter():
    data = fake_data()
    team = [1, 3, 5, 7, 8]
    good = D.best_positions(data, team)
    bad = list(reversed(good))
    assert D.score(data, good, [2, 4, 6, 9, 10])[0] > D.score(data, bad, [2, 4, 6, 9, 10])[0]


async def _play(client, h, mid):
    """Plays for the player until the draft ends, then sets the best placement."""
    for _ in range(40):
        m = (await client.get(f"/api/draft/match/{mid}", headers=h)).json()
        if m["status"] != "draft":
            return m
        t = m["turn"]
        if t["side"] != m["me"]:
            return m
        used = {a["hero"] for a in m["actions"]}
        hero = next(i for i in range(1, 31) if i not in used)
        r = await client.post(f"/api/draft/match/{mid}/act", json={"hero": hero}, headers=h)
        assert r.status_code == 200, r.text
    return m


async def test_bot_game_after_queue_timeout(client, app):
    app.state.draft_data = fake_data()
    h = await player(client, 900)
    assert (await client.post("/api/draft/queue", headers=h)).json()["match_id"] is None
    assert (await client.get("/api/draft/queue", headers=h)).json()["searching"]
    async with app.state.db.sessions() as s:
        (await s.get(DraftQueue, 900)).since_ms -= B.DRAFT_QUEUE_MS
        await s.commit()
    r = (await client.get("/api/draft/queue", headers=h)).json()
    assert r["bot"] and r["match_id"]
    mid = r["match_id"]
    m = await _play(client, h, mid)
    assert m["status"] == "place" and len(m["actions"]) == 24
    mine = [a["hero"] for a in m["actions"] if a["kind"] == "pick" and a["side"] == m["me"]]
    assert (await client.post(f"/api/draft/match/{mid}/place", json={"order": mine[::-1][:4] + [999]}, headers=h)).status_code == 400
    done = (await client.post(f"/api/draft/match/{mid}/place", json={"order": mine}, headers=h)).json()
    assert done["status"] == "done" and done["winner"] in ("A", "B")
    assert done["reward"] == B.DRAFT_BOT_COINS["win" if done["winner"] == done["me"] else "loss"]
    lobby = (await client.get("/api/draft", headers=h)).json()
    assert lobby["rating"]["elo"] == B.DRAFT_ELO_START and lobby["bot_rewards_left"] == B.DRAFT_BOT_REWARD_GAMES - 1
    assert lobby["ladder"] == []                              # games against the bot don't count for the ladder


async def test_pvp_ranked_elo_and_timeouts(client, app):
    app.state.draft_data = fake_data()
    h1, h2 = await player(client, 910), await player(client, 911)
    assert (await client.post("/api/draft/queue", headers=h1)).json()["match_id"] is None
    mid = (await client.post("/api/draft/queue", headers=h2)).json()["match_id"]
    assert (await client.get("/api/draft/queue", headers=h1)).json()["match_id"] == mid
    # one player fell asleep: their moves are made automatically after 30 s
    for _ in range(30):
        m = (await client.get(f"/api/draft/match/{mid}", headers=h1)).json()
        if m["status"] != "draft":
            break
        if m["turn"]["side"] == m["me"]:
            await _play(client, h1, mid)
        else:
            async with app.state.db.sessions() as s:
                (await s.get(DraftMatch, mid)).deadline_ms = 0
                await s.commit()
    m = (await client.get(f"/api/draft/match/{mid}", headers=h1)).json()
    assert m["status"] == "place" and any(a["auto"] for a in m["actions"])
    async with app.state.db.sessions() as s:
        (await s.get(DraftMatch, mid)).deadline_ms = 0          # placement also on timeout
        await s.commit()
    done = (await client.get(f"/api/draft/match/{mid}", headers=h2)).json()
    assert done["status"] == "done" and done["delta"]["A"] == -done["delta"]["B"] != 0
    async with app.state.db.sessions() as s:
        r1, r2 = await s.get(DraftRating, 910), await s.get(DraftRating, 911)
        assert r1.elo + r2.elo == 2 * B.DRAFT_ELO_START and r1.games == r2.games == 1
        months = (await s.execute(DraftMonth.__table__.select())).all()
        assert len(months) == 2


async def test_draft_needs_data(client, app):
    app.state.draft_data = None
    h = await player(client, 920)
    assert (await client.post("/api/draft/queue", headers=h)).json()["detail"] == "draft_data_loading"
