import json

import pytest

from sqlalchemy import select

from app.game import balance as B
from app.models import GameSession

from .conftest import auth, player


async def backdate(app, sid, ms):
    async with app.state.db.sessions() as s:
        (await s.get(GameSession, sid)).created_ms -= ms
        await s.commit()


async def test_hook_round_reward_and_limits(client, app):
    h = await player(client, 200)
    st = (await client.post("/api/games/hook/start", headers=h)).json()
    assert st["duration"] == B.HOOK_DURATION_SEC and st["plays_left"] == B.HOOK_PLAYS_PER_DAY - 1
    # too early: the result is rejected (and the attempt is used up)
    early = await client.post("/api/games/hook/finish", json={"session": st["session"], "hits": 3}, headers=h)
    assert early.status_code == 400
    st = (await client.post("/api/games/hook/start", headers=h)).json()
    await backdate(app, st["session"], B.HOOK_DURATION_SEC * 1000)
    too_many = B.HOOK_DURATION_SEC * 1000 // B.HOOK_COOLDOWN_MS + 1
    r = await client.post("/api/games/hook/finish", json={"session": st["session"], "hits": too_many}, headers=h)
    assert r.status_code == 400
    st = (await client.post("/api/games/hook/start", headers=h)).json()
    await backdate(app, st["session"], B.HOOK_DURATION_SEC * 1000)
    r = (await client.post("/api/games/hook/finish", json={"session": st["session"], "hits": 7}, headers=h)).json()
    assert r["reward"] == 7 * B.HOOK_COIN_PER_HIT and r["best"] == 7 and r["state"]["coins"] == r["reward"]
    again = await client.post("/api/games/hook/finish", json={"session": st["session"], "hits": 7}, headers=h)
    assert again.status_code == 409
    for _ in range(B.HOOK_PLAYS_PER_DAY - 3):
        assert (await client.post("/api/games/hook/start", headers=h)).status_code == 200
    assert (await client.post("/api/games/hook/start", headers=h)).json()["detail"] == "no_plays_left"
    g = (await client.get("/api/games", headers=h)).json()
    assert g["hook"]["plays_left"] == 0 and g["hook"]["best"] == 7


@pytest.mark.needs_assets
async def test_guess_streak_no_repeats_and_points(client, app):
    from app.models import Activity, User
    h = await player(client, 210)
    st = (await client.post("/api/games/guess/start", headers=h)).json()
    q = st["question"]
    assert len(q["options"]) == 4 and q["streak"] == 0 and q["view"] == "front"
    assert all(o["id"] not in q["model"]["body"] for o in q["options"])  # the answer isn't visible in the URL
    m = await client.get(q["model"]["body"])
    assert m.status_code == 200 and m.content[:4] == b"glTF"
    shown = []
    for expect_streak in (1, 2):
        async with app.state.db.sessions() as s:
            answer = json.loads((await s.get(GameSession, st["session"])).payload)["answer"]
        shown.append(answer)
        r = (await client.post("/api/games/guess/answer", json={"session": st["session"], "hero": answer}, headers=h)).json()
        assert r["correct"] and r["streak"] == expect_streak and r["reward"] == B.GUESS_COIN_PER_STREAK * expect_streak
        assert r["next"]["view"] == "back" and len(r["next"]["options"]) == 4
    # an old model link from the previous round is no longer served
    assert (await client.get(q["model"]["body"])).status_code == 404
    async with app.state.db.sessions() as s:
        answer = json.loads((await s.get(GameSession, st["session"])).payload)["answer"]
    wrong = next(o["id"] for o in r["next"]["options"] if o["id"] != answer)
    end = (await client.post("/api/games/guess/answer", json={"session": st["session"], "hero": wrong}, headers=h)).json()
    assert not end["correct"] and end["next"] is None and end["streak"] == 2
    assert answer not in shown  # no repeats within a streak
    async with app.state.db.sessions() as s:
        pts = sum(a.points for a in (await s.execute(select(Activity).where(Activity.user_id == 210))).scalars())
        seen = (await s.get(User, 210)).guess_seen.split(",")
    assert pts == 2 * 2 * B.ACT_GUESS_PER_STREAK  # week + month
    assert set(shown) | {answer} <= set(seen)
    g = (await client.get("/api/games", headers=h)).json()
    assert g["guess"]["best"] == 2 and g["guess"]["plays_left"] == B.GUESS_PLAYS_PER_DAY - 1


def test_guess_difficulty_ramp():
    from app.game import guess as G
    assert G.round_params(0)["view"] == "front" and G.round_params(0)["choices"] == 4
    late = G.round_params(7)
    assert late["view"] == "odd" and late["choices"] == 6 and late["set"] and late["seconds"] == 5
    assert G.round_params(3)["set"] and not G.round_params(2)["set"] and not G.round_params(8)["items"]
    import random
    ans, opts, _ = G.pick(set(), set(), random.Random(1), 6)
    assert len(opts) == 6 and ans in opts
    # wrong options share the attribute while there are enough of them
    assert sum(G.attr(o.id) == G.attr(ans.id) for o in opts) >= 4

async def test_games_require_steam(client):
    h = auth(220)
    await client.get("/api/me", headers=h)
    assert (await client.post("/api/games/hook/start", headers=h)).json()["detail"] == "steam_required"


@pytest.mark.needs_assets
def test_guess_pool_models_exist():
    from pathlib import Path

    from app.game import guess as G
    public = Path(__file__).resolve().parents[2] / "frontend" / "public"
    assert len(G.POOL) >= 40
    assert sum(1 for h in G.POOL if h.sets) >= 35   # most heroes have set looks
    missing = [f"{h.dir}{f}" for h in G.POOL for f in (h.body, *h.items, *(i for s in h.sets for i in s))
               if not (public / (h.dir + f).lstrip("/")).is_file()]
    assert not missing, missing
