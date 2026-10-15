"""Mini-games: Pudge Hook and Guess the Hero by 3D silhouette. Rewards are ELT COIN, attempts reset per game day."""

from __future__ import annotations

import json
import random
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..game import balance as B
from ..game import clicker, daily
from ..game import guess as GUESS
from ..models import GameDay, GameSession
from ..services import activity
from ..services.users import get_or_create, now_ms
from .deps import CurrentTg, Session
from .routes import require_access, state_out

router = APIRouter(prefix="/api/games")

PLAYS = {"hook": B.HOOK_PLAYS_PER_DAY, "guess": B.GUESS_PLAYS_PER_DAY}
REPO_PUBLIC = Path(__file__).resolve().parents[3] / "frontend" / "public"


def _today(request: Request, now: int) -> str:
    return daily.game_day(now, request.app.state.settings.timezone).isoformat()


async def _day(s: Session, user_id: int, game: str, day: str) -> GameDay:
    row = await s.get(GameDay, (user_id, game, day), with_for_update=True)
    if row is None:
        row = GameDay(user_id=user_id, game=game, day=day, plays=0, best=0)
        s.add(row)
    return row


async def _all_time_best(s: Session, user_id: int, game: str) -> int:
    return (await s.execute(select(func.max(GameDay.best)).where(
        GameDay.user_id == user_id, GameDay.game == game))).scalar() or 0


async def _start(request: Request, tg, s: Session, game: str, payload: dict) -> tuple[GameSession, GameDay]:
    await require_access(s, tg.id)
    await get_or_create(s, tg)
    now = now_ms()
    d = await _day(s, tg.id, game, _today(request, now))
    if d.plays >= PLAYS[game]:
        await s.rollback()
        raise HTTPException(429, "no_plays_left")
    d.plays += 1
    gs = GameSession(id=secrets.token_urlsafe(18), user_id=tg.id, game=game, payload=json.dumps(payload),
                     created_ms=now)
    s.add(gs)
    return gs, d


async def _session(s: Session, sid: str, user_id: int, game: str) -> GameSession:
    gs = await s.get(GameSession, sid, with_for_update=True)
    if gs is None or gs.user_id != user_id or gs.game != game:
        raise HTTPException(404, "unknown_session")
    if gs.finished_ms is not None:
        raise HTTPException(409, "already_finished")
    return gs


@router.get("")
async def games(request: Request, tg: CurrentTg, s: Session) -> dict:
    await get_or_create(s, tg)
    day = _today(request, now_ms())
    out = {}
    for game, limit in PLAYS.items():
        d = await s.get(GameDay, (tg.id, game, day))
        out[game] = {"plays_left": limit - (d.plays if d else 0), "plays_per_day": limit,
                     "best": await _all_time_best(s, tg.id, game)}
    await s.commit()
    return out


# ---------------- Pudge Hook ----------------

@router.post("/hook/start")
async def hook_start(request: Request, tg: CurrentTg, s: Session) -> dict:
    seed = secrets.randbelow(2**31)
    gs, d = await _start(request, tg, s, "hook", {"seed": seed})
    await s.commit()
    return {"session": gs.id, "seed": seed, "duration": B.HOOK_DURATION_SEC, "cooldown_ms": B.HOOK_COOLDOWN_MS,
            "coin_per_hit": B.HOOK_COIN_PER_HIT, "plays_left": PLAYS["hook"] - d.plays}


class HookFinish(BaseModel):
    session: str
    hits: int = Field(ge=0, le=500)       # enemies hooked (for activity points)
    score: int | None = Field(default=None, ge=-500, le=5000)  # round points with combo; without it, an old client


@router.post("/hook/finish")
async def hook_finish(body: HookFinish, request: Request, tg: CurrentTg, s: Session) -> dict:
    gs = await _session(s, body.session, tg.id, "hook")
    now = now_ms()
    elapsed = now - gs.created_ms
    # the result is plausible: the round actually lasted, and there are no more hooks than the cooldown allows
    max_hits = B.HOOK_DURATION_SEC * 1000 // B.HOOK_COOLDOWN_MS
    score = body.hits if body.score is None else body.score
    if (elapsed < B.HOOK_DURATION_SEC * 800 or elapsed > (B.HOOK_DURATION_SEC + 120) * 1000 or body.hits > max_hits
            or score > max_hits * B.HOOK_MAX_POINTS_PER_THROW):
        gs.finished_ms = now
        await s.commit()
        raise HTTPException(400, "rejected")
    gs.finished_ms = now
    u = await get_or_create(s, tg)
    clicker.sync(u, now)
    score = max(0, score)
    reward = score * B.HOOK_COIN_PER_HIT
    clicker.earn(u, reward)
    await activity.add(s, u, body.hits * B.ACT_HOOK_HIT, now, request.app.state.settings.timezone)
    d = await _day(s, tg.id, "hook", _today(request, gs.created_ms))
    d.best = max(d.best, score)
    await s.commit()
    return {"reward": reward, "best": await _all_time_best(s, tg.id, "hook"), "state": state_out(u, now)}


# ---------------- Guess the Hero by 3D silhouette: streaks until the first mistake ----------------

def _models_root(request: Request) -> Path:
    static = getattr(request.app.state, "static_dir", None)
    for root in (static, REPO_PUBLIC):
        if root and (Path(root) / "models" / "heroes").is_dir():
            return Path(root)
    raise HTTPException(503, "models_unavailable")


def _question(gs: GameSession, payload: dict) -> dict:
    """Round question. The model is served by session and round number, so the answer can't be read from the file URL."""
    hero = GUESS.BY_ID[payload["answer"]]
    base = f"/api/games/guess/{gs.id}/r/{payload['round']}"
    params = GUESS.round_params(payload["streak"])
    params.pop("set")
    items = range(len(_look(hero, payload))) if params.pop("items") else ()
    return {"round": payload["round"], "streak": payload["streak"], **params,
            "reward": B.GUESS_COIN_PER_STREAK * (payload["streak"] + 1),
            "options": payload["options"],
            "model": {"body": f"{base}/body.glb", "items": [f"{base}/{i}.glb" for i in items]}}


def _look(hero, payload: dict) -> tuple[str, ...]:
    """Items for the round's look: a set (if one was rolled) or the default items."""
    i = payload.get("look", -1)
    return hero.sets[i] if 0 <= i < len(hero.sets) else hero.items


def _new_round(u, payload: dict) -> None:
    seen = {x for x in (u.guess_seen or "").split(",") if x}
    choices = GUESS.round_params(payload.get("streak", 0))["choices"]
    answer, options, reset = GUESS.pick(seen, set(payload.get("used", [])), random.Random(), choices)
    if reset:
        seen = set()
    seen.add(answer.id)
    u.guess_seen = ",".join(sorted(seen))
    p = GUESS.round_params(payload.get("streak", 0))
    look = random.randrange(len(answer.sets)) if p["set"] and answer.sets else -1
    payload.update(answer=answer.id, look=look, asked_ms=now_ms(), round=payload.get("round", 0) + 1,
                   options=[{"id": h.id, "name": h.name} for h in options],
                   used=[*payload.get("used", []), answer.id])


@router.post("/guess/start")
async def guess_start(request: Request, tg: CurrentTg, s: Session) -> dict:
    gs, d = await _start(request, tg, s, "guess", {})
    u = await get_or_create(s, tg)
    payload = {"streak": 0}
    _new_round(u, payload)
    gs.payload = json.dumps(payload)
    await s.commit()
    return {"session": gs.id, "plays_left": PLAYS["guess"] - d.plays, "question": _question(gs, payload)}


@router.get("/guess/{sid}/r/{rnd}/{name}.glb", include_in_schema=False)
async def guess_model(sid: str, rnd: int, name: str, request: Request, s: Session) -> FileResponse:
    gs = await s.get(GameSession, sid)
    if gs is None or gs.game != "guess":
        raise HTTPException(404)
    payload = json.loads(gs.payload)
    if payload.get("round") != rnd:
        raise HTTPException(404)
    hero = GUESS.BY_ID[payload["answer"]]
    if name == "body":
        rel = hero.body
    elif name.isdigit() and int(name) < len(_look(hero, payload)):
        rel = _look(hero, payload)[int(name)]
    else:
        raise HTTPException(404)
    path = _models_root(request) / hero.dir.strip("/") / rel
    return FileResponse(path, media_type="model/gltf-binary", headers={"Cache-Control": "no-store"})


class GuessAnswer(BaseModel):
    session: str
    hero: str


@router.post("/guess/answer")
async def guess_answer(body: GuessAnswer, request: Request, tg: CurrentTg, s: Session) -> dict:
    gs = await _session(s, body.session, tg.id, "guess")
    payload = json.loads(gs.payload)
    now = now_ms()
    answer = GUESS.BY_ID[payload["answer"]]
    limit = GUESS.round_params(payload["streak"])["seconds"]
    in_time = now - payload["asked_ms"] <= (limit + 5) * 1000  # +5 s to load the model
    correct = body.hero == answer.id and in_time
    u = await get_or_create(s, tg)
    clicker.sync(u, now)
    reward = 0
    nxt = None
    if correct:
        payload["streak"] += 1
        reward = B.GUESS_COIN_PER_STREAK * payload["streak"]
        clicker.earn(u, reward)
        if payload["streak"] < GUESS.MAX_STREAK:
            _new_round(u, payload)
            nxt = _question(gs, payload)
    if nxt is None:  # wrong answer, time is up or the streak maximum: the streak is over
        gs.finished_ms = now
        d = await _day(s, tg.id, "guess", _today(request, gs.created_ms))
        if payload["streak"] > d.best:
            # rating points only for beating the best streak of the day: can't be farmed by playing more
            await activity.add(s, u, (payload["streak"] - d.best) * B.ACT_GUESS_PER_STREAK, now,
                               request.app.state.settings.timezone)
            d.best = payload["streak"]
    gs.payload = json.dumps(payload)
    await s.commit()
    return {"correct": correct, "timeout": not in_time, "answer": {"id": answer.id, "name": answer.name},
            "reward": reward, "streak": payload["streak"], "next": nxt, "state": state_out(u, now)}
