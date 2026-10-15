"""Draft duel: matchmaking (30 s, then a bot), Captains Mode, position placement, result, ELO, monthly ladder.

Match state advances lazily on every request: bot moves and auto-moves when time runs out.
Clients poll the match once per second."""

from __future__ import annotations

import json
import random
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..game import balance as B
from ..game import clicker, daily
from ..game import draft as D
from ..models import DraftMatch, DraftMonth, DraftQueue, DraftRating, GameDay, User
from ..services import activity
from ..services.users import get_for_update, get_or_create, now_ms
from .deps import CurrentTg, Session
from .routes import require_access, state_out

router = APIRouter(prefix="/api/draft")


def _data(request: Request) -> D.Data:
    data = getattr(request.app.state, "draft_data", None)
    if data is None or not data.heroes:
        raise HTTPException(503, "draft_data_loading")
    return data


async def _rating(s: Session, uid: int) -> DraftRating:
    r = await s.get(DraftRating, uid, with_for_update=True)
    if r is None:
        r = DraftRating(user_id=uid, elo=B.DRAFT_ELO_START, games=0, wins=0, bot_games=0)
        s.add(r)
        await s.flush()
    return r


def _name(u: User | None) -> str:
    return (u.username or u.first_name or f"id{u.id}") if u else "Бот"


def _side(m: DraftMatch, uid: int) -> str:
    if m.a_id == uid:
        return "A"
    if m.b_id == uid:
        return "B"
    raise HTTPException(404, "match_not_found")


def _is_bot(m: DraftMatch, side: str) -> bool:
    return side == "B" and m.b_id is None


async def _new_match(s: Session, a: int, b: int | None, skill: float | None, now: int) -> DraftMatch:
    # who moves first is random
    if b is not None and random.random() < 0.5:
        a, b = b, a
    m = DraftMatch(id=secrets.token_urlsafe(16), a_id=a, b_id=b, bot_skill=skill, ranked=b is not None,
                   status="draft", actions="[]", deadline_ms=now + D.TURN_MS, created_ms=now)
    s.add(m)
    await s.flush()
    return m


def _skill(elo: int) -> float:
    """Bot strength grows with the player's ELO: 1000 -> 0.45, 1400 -> 0.85."""
    return max(0.2, min(0.95, 0.45 + (elo - 1000) / 1000))


# ---------------- advancing the match ----------------
async def _advance(request: Request, s: Session, m: DraftMatch, now: int) -> None:
    data = _data(request)
    rng = random.Random(f"{m.id}:{len(json.loads(m.actions))}")
    if m.status == "draft":
        actions = json.loads(m.actions)
        while (t := D.turn(len(actions))) is not None:
            kind, side = t
            bot = _is_bot(m, side)
            if not bot and now < m.deadline_ms:
                break
            hero = D.bot_choice(data, actions, side, m.bot_skill if bot else 0.4, rng)
            actions.append({"kind": kind, "side": side, "hero": hero, "auto": not bot})
            # the next turn starts when the previous one ended (so auto-moves don't eat time back to back)
            m.deadline_ms = max(now, m.deadline_ms if not bot else now) + D.TURN_MS
        m.actions = json.dumps(actions)
        if D.turn(len(actions)) is None:
            m.status, m.deadline_ms = "place", now + D.PLACE_MS
            if m.b_id is None:
                m.b_order = json.dumps(D.best_positions(data, D.picks(actions, "B")))
    if m.status == "place":
        actions = json.loads(m.actions)
        if now >= m.deadline_ms:
            for side in "AB":
                attr = f"{side.lower()}_order"
                if getattr(m, attr) is None:
                    setattr(m, attr, json.dumps(D.best_positions(data, D.picks(actions, side))))
        if m.a_order and m.b_order:
            await _finish(request, s, m, data, now)


def _elo_delta(ra: int, rb: int, a_won: bool) -> int:
    expected = 1 / (1 + 10 ** ((rb - ra) / 400))
    return round(B.DRAFT_K * ((1 if a_won else 0) - expected))


async def _month(s: Session, uid: int, period: str, delta: int, won: bool, now: int) -> None:
    row = await s.get(DraftMonth, (uid, period), with_for_update=True)
    if row is None:
        row = DraftMonth(user_id=uid, period=period, points=0, games=0, wins=0)
        s.add(row)
    row.points += delta
    row.games += 1
    row.wins += int(won)
    row.updated_ms = now


async def _finish(request: Request, s: Session, m: DraftMatch, data: D.Data, now: int) -> None:
    res = D.resolve(data, json.loads(m.a_order), json.loads(m.b_order), seed=m.id)
    m.result, m.winner, m.status, m.finished_ms = json.dumps(res, ensure_ascii=False), res["winner"], "done", now
    tz = request.app.state.settings.timezone
    if m.ranked:
        ra, rb = await _rating(s, m.a_id), await _rating(s, m.b_id)
        a_won = m.winner == "A"
        d = _elo_delta(ra.elo, rb.elo, a_won)
        m.a_delta, m.b_delta = d, -d
        period = activity.month_key(now, tz)
        for r, delta, won in ((ra, d, a_won), (rb, -d, not a_won)):
            r.elo += delta
            r.games += 1
            r.wins += int(won)
            await _month(s, r.user_id, period, delta, won, now)
        return
    # game against the bot: unrated; the first N games per day give ELT COIN
    r = await _rating(s, m.a_id)
    r.bot_games += 1
    day = daily.game_day(now, tz).isoformat()
    gd = await s.get(GameDay, (m.a_id, "draft_bot", day), with_for_update=True)
    if gd is None:
        gd = GameDay(user_id=m.a_id, game="draft_bot", day=day, plays=0, best=0)
        s.add(gd)
    gd.plays += 1
    if gd.plays <= B.DRAFT_BOT_REWARD_GAMES:
        u = await get_for_update(s, m.a_id)
        clicker.sync(u, now)
        m.reward = B.DRAFT_BOT_COINS["win" if m.winner == "A" else "loss"]
        clicker.earn(u, m.reward)


def _match_out(m: DraftMatch, uid: int, data: D.Data, users: dict[int, User]) -> dict:
    me = _side(m, uid)
    actions = json.loads(m.actions)
    t = D.turn(len(actions))
    out = {
        "id": m.id, "status": m.status, "me": me, "ranked": m.ranked, "deadline_ms": m.deadline_ms,
        "turn": {"kind": t[0], "side": t[1], "step": len(actions)} if t and m.status == "draft" else None,
        "sequence": [{"kind": k, "side": sd} for k, sd in D.SEQUENCE],
        "actions": actions,
        "players": {"A": {"id": m.a_id, "name": _name(users.get(m.a_id))},
                    "B": {"id": m.b_id, "name": _name(users.get(m.b_id)) if m.b_id else "Бот"}},
        "orders": {"A": json.loads(m.a_order) if m.a_order and (m.status == "done" or me == "A") else None,
                   "B": json.loads(m.b_order) if m.b_order and (m.status == "done" or me == "B") else None},
    }
    if m.status == "done":
        out.update(result=json.loads(m.result), winner=m.winner,
                   delta={"A": m.a_delta, "B": m.b_delta}, reward=m.reward if me == "A" and not m.ranked else 0)
    return out


async def _load_users(s: Session, m: DraftMatch) -> dict[int, User]:
    ids = [i for i in (m.a_id, m.b_id) if i]
    return {u.id: u for u in (await s.execute(select(User).where(User.id.in_(ids)))).scalars()}


# ---------------- API ----------------
@router.get("/heroes")
async def heroes(request: Request) -> dict:
    data = _data(request)
    return {"heroes": [{"id": h.id, "name": h.name, "roles": sorted(h.roles), "attack": h.attack, "attr": h.attr,
                        "winrate": h.winrate, "img": h.img} for h in sorted(data.heroes.values(), key=lambda x: x.name)],
            "positions": D.POS_NAMES}


@router.get("")
async def lobby(request: Request, tg: CurrentTg, s: Session) -> dict:
    await get_or_create(s, tg)
    now = now_ms()
    tz = request.app.state.settings.timezone
    r = await s.get(DraftRating, tg.id)
    q = await s.get(DraftQueue, tg.id)
    active = (await s.execute(select(DraftMatch.id).where(
        ((DraftMatch.a_id == tg.id) | (DraftMatch.b_id == tg.id)), DraftMatch.status != "done")
        .order_by(DraftMatch.created_ms.desc()).limit(1))).scalar()
    period = activity.month_key(now, tz)
    top = (await s.execute(select(DraftMonth, User).join(User, User.id == DraftMonth.user_id)
                           .where(DraftMonth.period == period, DraftMonth.games >= B.DRAFT_MONTH_MIN_GAMES)
                           .order_by(DraftMonth.points.desc(), DraftMonth.updated_ms).limit(20))).all()
    mine = await s.get(DraftMonth, (tg.id, period))
    day = daily.game_day(now, tz).isoformat()
    gd = await s.get(GameDay, (tg.id, "draft_bot", day))
    await s.commit()
    return {
        "ready": bool(getattr(request.app.state, "draft_data", None)),
        "rating": {"elo": r.elo if r else B.DRAFT_ELO_START, "games": r.games if r else 0, "wins": r.wins if r else 0},
        "queue": {"since_ms": q.since_ms, "wait_ms": B.DRAFT_QUEUE_MS} if q and not q.match_id else None,
        "active": active,
        "bot_rewards_left": max(0, B.DRAFT_BOT_REWARD_GAMES - (gd.plays if gd else 0)),
        "bot_coins": B.DRAFT_BOT_COINS,
        "month": {"period": period, "ends_ms": activity.period_end_ms(period, tz),
                  "points": mine.points if mine else 0, "games": mine.games if mine else 0,
                  "min_games": B.DRAFT_MONTH_MIN_GAMES, "prizes": B.DRAFT_MONTH_PRIZES_SOULS},
        "ladder": [{"rank": i + 1, "id": u.id, "name": _name(u), "photo_url": u.photo_url, "points": mm.points,
                    "games": mm.games, "wins": mm.wins, "me": u.id == tg.id} for i, (mm, u) in enumerate(top)],
    }


@router.post("/queue")
async def queue(request: Request, tg: CurrentTg, s: Session) -> dict:
    """Join matchmaking. If someone is already queued, start a match right away; otherwise wait (poll GET /queue)."""
    _data(request)
    await require_access(s, tg.id)
    now = now_ms()
    busy = (await s.execute(select(DraftMatch.id).where(
        ((DraftMatch.a_id == tg.id) | (DraftMatch.b_id == tg.id)), DraftMatch.status != "done"))).scalar()
    if busy:
        return {"match_id": busy}
    other = (await s.execute(select(DraftQueue).where(
        DraftQueue.user_id != tg.id, DraftQueue.match_id.is_(None), DraftQueue.since_ms > now - B.DRAFT_QUEUE_MS)
        .order_by(DraftQueue.since_ms).limit(1).with_for_update())).scalar()
    mine = await s.get(DraftQueue, tg.id)
    if other is not None:
        m = await _new_match(s, other.user_id, tg.id, None, now)
        other.match_id = m.id
        if mine is not None:
            await s.delete(mine)
        await s.commit()
        return {"match_id": m.id}
    if mine is None:
        s.add(DraftQueue(user_id=tg.id, since_ms=now))
    else:
        mine.since_ms, mine.match_id = now, None
    await s.commit()
    return {"match_id": None, "since_ms": now, "wait_ms": B.DRAFT_QUEUE_MS}


@router.get("/queue")
async def queue_poll(request: Request, tg: CurrentTg, s: Session) -> dict:
    """Matchmaking poll: a human was found -> match; 30 s passed -> match against the bot."""
    _data(request)
    q = await s.get(DraftQueue, tg.id, with_for_update=True)
    if q is None:
        return {"match_id": None, "searching": False}
    if q.match_id:
        mid = q.match_id
        await s.delete(q)
        await s.commit()
        return {"match_id": mid}
    now = now_ms()
    if now - q.since_ms >= B.DRAFT_QUEUE_MS:
        r = await _rating(s, tg.id)
        m = await _new_match(s, tg.id, None, _skill(r.elo), now)
        await s.delete(q)
        await s.commit()
        return {"match_id": m.id, "bot": True}
    return {"match_id": None, "searching": True, "left_ms": B.DRAFT_QUEUE_MS - (now - q.since_ms)}


@router.delete("/queue")
async def queue_leave(tg: CurrentTg, s: Session) -> dict:
    q = await s.get(DraftQueue, tg.id)
    if q is not None and not q.match_id:
        await s.delete(q)
        await s.commit()
    return {"ok": True}


async def _match(request: Request, s: Session, mid: str, uid: int) -> DraftMatch:
    m = await s.get(DraftMatch, mid, with_for_update=True)
    if m is None:
        raise HTTPException(404, "match_not_found")
    _side(m, uid)
    await _advance(request, s, m, now_ms())
    return m


@router.get("/match/{mid}")
async def match(mid: str, request: Request, tg: CurrentTg, s: Session) -> dict:
    m = await _match(request, s, mid, tg.id)
    await s.commit()
    return _match_out(m, tg.id, _data(request), await _load_users(s, m))


class ActIn(BaseModel):
    hero: int


@router.post("/match/{mid}/act")
async def act(mid: str, body: ActIn, request: Request, tg: CurrentTg, s: Session) -> dict:
    m = await _match(request, s, mid, tg.id)
    if m.status != "draft":
        raise HTTPException(409, "not_drafting")
    data = _data(request)
    actions = json.loads(m.actions)
    side = _side(m, tg.id)
    err = D.validate(data, actions, side, body.hero)
    if err:
        await s.rollback()
        raise HTTPException(400, err)
    kind = D.turn(len(actions))[0]
    actions.append({"kind": kind, "side": side, "hero": body.hero, "auto": False})
    m.actions = json.dumps(actions)
    now = now_ms()
    m.deadline_ms = now + D.TURN_MS
    await _advance(request, s, m, now)   # bot moves right after the player's move
    await s.commit()
    return _match_out(m, tg.id, data, await _load_users(s, m))


class PlaceIn(BaseModel):
    order: list[int] = Field(min_length=5, max_length=5)


@router.post("/match/{mid}/place")
async def place(mid: str, body: PlaceIn, request: Request, tg: CurrentTg, s: Session) -> dict:
    m = await _match(request, s, mid, tg.id)
    if m.status != "place":
        raise HTTPException(409, "not_placing")
    side = _side(m, tg.id)
    mine = D.picks(json.loads(m.actions), side)
    if sorted(body.order) != sorted(mine):
        await s.rollback()
        raise HTTPException(400, "bad_order")
    setattr(m, f"{side.lower()}_order", json.dumps(body.order))
    now = now_ms()
    await _advance(request, s, m, now)
    await s.commit()
    return _match_out(m, tg.id, _data(request), await _load_users(s, m))


@router.get("/history")
async def history(request: Request, tg: CurrentTg, s: Session) -> dict:
    rows = (await s.execute(select(DraftMatch).where(
        ((DraftMatch.a_id == tg.id) | (DraftMatch.b_id == tg.id)), DraftMatch.status == "done")
        .order_by(DraftMatch.finished_ms.desc()).limit(20))).scalars().all()
    out = []
    for m in rows:
        side = _side(m, tg.id)
        out.append({"id": m.id, "won": m.winner == side, "ranked": m.ranked, "finished_ms": m.finished_ms,
                    "delta": m.a_delta if side == "A" else m.b_delta})
    return {"matches": out, "total": len(out)}
