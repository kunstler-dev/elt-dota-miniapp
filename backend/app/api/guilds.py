"""Guilds: created for ELT COIN, join/leave, weekly points and guild quests (rewarded with souls)."""

from __future__ import annotations

import base64
import binascii
import re

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..game import balance as B
from ..models import Guild, GuildClaim, GuildMember, GuildPoints, SteamAccount, User
from ..services import activity, souls
from ..services.users import get_for_update, get_or_create, now_ms
from .deps import CurrentTg, Session
from .routes import require_access, state_out

router = APIRouter(prefix="/api")

NAME_RE = re.compile(r"^[\w .\-]{3,20}$", re.UNICODE)
MAX_IMG = 300 * 1024
IMG_TYPES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}


def _image(data_url: str) -> bytes:
    """Guild picture from a data URL: jpeg/png/webp only and at most 300 KB (the client resizes to 256x256)."""
    try:
        raw = base64.b64decode(data_url.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(400, "bad_image") from e
    if len(raw) > MAX_IMG or not any(raw.startswith(sig) for sig in IMG_TYPES):
        raise HTTPException(400, "bad_image")
    return raw


def _img_type(raw: bytes) -> str:
    return next(t for sig, t in IMG_TYPES.items() if raw.startswith(sig))


def _uname(u: User) -> str:
    return u.username or u.first_name or f"id{u.id}"


def _week(request: Request, now: int) -> str:
    return activity.week_key(now, request.app.state.settings.timezone)


async def _contrib(s: Session, guild_id: int, period: str) -> dict[int, int]:
    rows = await s.execute(select(GuildPoints.user_id, GuildPoints.points).where(
        GuildPoints.guild_id == guild_id, GuildPoints.period == period))
    return {uid: pts for uid, pts in rows.all()}


def _quests(contrib: dict[int, int], my_id: int | None, claimed: set[tuple[str, int]]) -> list[dict]:
    total = sum(contrib.values())
    active = sum(1 for p in contrib.values() if p >= B.GUILD_MIN_CONTRIB)
    progress = {"points": total, "active": active}
    eligible = my_id is not None and contrib.get(my_id, 0) >= B.GUILD_MIN_CONTRIB
    out = []
    for q in B.GUILD_QUESTS:
        tiers = []
        for i, (goal, reward) in enumerate(q["tiers"]):
            done = progress[q["id"]] >= goal
            tiers.append({"tier": i, "goal": goal, "souls": reward, "done": done,
                          "claimed": (q["id"], i) in claimed, "can_claim": done and eligible and (q["id"], i) not in claimed})
        out.append({"id": q["id"], "title": q["title"], "progress": progress[q["id"]], "tiers": tiers})
    return out


async def _top_guilds(s: Session, period: str, limit: int = 50) -> list[dict]:
    pts = func.coalesce(func.sum(GuildPoints.points), 0)
    rows = (await s.execute(
        select(Guild, pts.label("pts")).join(GuildPoints, (GuildPoints.guild_id == Guild.id) & (GuildPoints.period == period),
                                             isouter=True)
        .group_by(Guild.id).order_by(pts.desc(), Guild.members.desc(), Guild.id).limit(limit))).all()
    return [_guild_short(g, int(p), i + 1) for i, (g, p) in enumerate(rows)]


def _guild_short(g: Guild, points: int, rank: int | None = None) -> dict:
    return {"id": g.id, "name": g.name, "emblem": g.emblem, "about": g.about, "members": g.members,
            "emblem_url": f"/api/guilds/{g.id}/emblem?v={g.emblem_ver}" if g.emblem_ver else None,
            "max_members": B.GUILD_MAX_MEMBERS, "points": points, "rank": rank}


async def _detail(request: Request, s: Session, g: Guild, me_id: int) -> dict:
    now = now_ms()
    period = _week(request, now)
    contrib = await _contrib(s, g.id, period)
    rows = (await s.execute(select(GuildMember, User).join(User, User.id == GuildMember.user_id)
                            .where(GuildMember.guild_id == g.id))).all()
    members = sorted(({"id": u.id, "name": _uname(u), "photo_url": u.photo_url, "role": m.role,
                       "points": contrib.get(u.id, 0), "me": u.id == me_id} for m, u in rows),
                     key=lambda r: (-r["points"], r["role"] != "owner", r["id"]))
    me_member = next((r for r in members if r["me"]), None)
    claimed = set()
    if me_member:
        claimed = {(c.quest, c.tier) for c in (await s.execute(select(GuildClaim).where(
            GuildClaim.user_id == me_id, GuildClaim.period == period))).scalars()}
    total = sum(contrib.values())
    better = (await s.execute(select(func.count()).select_from(
        select(GuildPoints.guild_id).where(GuildPoints.period == period).group_by(GuildPoints.guild_id)
        .having(func.sum(GuildPoints.points) > total).subquery()))).scalar_one()
    return {**_guild_short(g, total, better + 1 if total > 0 else None),
            "owner_id": g.owner_id, "members_list": members,
            "my_role": me_member["role"] if me_member else None,
            "my_points": me_member["points"] if me_member else 0,
            "quests": _quests(contrib, me_id if me_member else None, claimed),
            "ends_ms": activity.period_end_ms(period, request.app.state.settings.timezone)}


def _rules() -> dict:
    return {"create_cost": B.GUILD_CREATE_COST, "max_members": B.GUILD_MAX_MEMBERS,
            "min_contrib": B.GUILD_MIN_CONTRIB, "emblems": B.GUILD_EMBLEMS, "war_prizes": B.GUILD_WAR_PRIZES}


@router.get("/guild")
async def my_guild(request: Request, tg: CurrentTg, s: Session) -> dict:
    """My guild (or null) + this week's top guilds to choose from."""
    me = await get_or_create(s, tg)
    m = await s.get(GuildMember, me.id)
    guild = await _detail(request, s, await s.get(Guild, m.guild_id), me.id) if m else None
    top = await _top_guilds(s, _week(request, now_ms()))
    left = max(0, me.guild_left_ms + B.GUILD_REJOIN_COOLDOWN_MS - now_ms()) if me.guild_left_ms else 0
    await s.commit()
    return {"guild": guild, "top": top, "rules": _rules(), "rejoin_in_ms": left}


@router.get("/guilds/{guild_id}")
async def guild_info(guild_id: int, request: Request, tg: CurrentTg, s: Session) -> dict:
    g = await s.get(Guild, guild_id)
    if g is None:
        raise HTTPException(404, "guild_not_found")
    return await _detail(request, s, g, tg.id)


class CreateIn(BaseModel):
    name: str = Field(min_length=3, max_length=20)
    image: str = Field(min_length=20, max_length=MAX_IMG * 2)  # data URL of a custom guild picture
    about: str = Field(default="", max_length=140)


@router.post("/guilds")
async def create(request: Request, body: CreateIn, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    name = " ".join(body.name.split())
    if not NAME_RE.match(name):
        raise HTTPException(400, "bad_name")
    img = _image(body.image)
    u = await get_for_update(s, tg.id)
    if await s.get(GuildMember, u.id) is not None:
        await s.rollback()
        raise HTTPException(409, "already_in_guild")
    if u.coins < B.GUILD_CREATE_COST:
        await s.rollback()
        raise HTTPException(400, "not_enough_coins")
    now = now_ms()
    u.coins -= B.GUILD_CREATE_COST
    g = Guild(name=name, name_key=name.casefold(), about=body.about.strip(), owner_id=u.id,
              members=1, created_ms=now, emblem_img=img, emblem_ver=1)
    s.add(g)
    try:
        await s.flush()
    except IntegrityError as e:
        await s.rollback()
        raise HTTPException(409, "name_taken") from e
    s.add(GuildMember(user_id=u.id, guild_id=g.id, role="owner", joined_ms=now))
    await s.commit()
    return {"guild": await _detail(request, s, g, u.id), "state": state_out(u, now)}


class ImageIn(BaseModel):
    image: str = Field(min_length=20, max_length=MAX_IMG * 2)


@router.post("/guild/emblem")
async def set_emblem(request: Request, body: ImageIn, tg: CurrentTg, s: Session) -> dict:
    """Change the guild picture (owner only)."""
    me = await s.get(GuildMember, tg.id)
    if me is None or me.role != "owner":
        raise HTTPException(403, "owner_only")
    g = await s.get(Guild, me.guild_id, with_for_update=True)
    g.emblem_img = _image(body.image)
    g.emblem_ver += 1
    await s.commit()
    return {"guild": await _detail(request, s, g, tg.id)}


@router.get("/guilds/{guild_id}/emblem", include_in_schema=False)
async def emblem(guild_id: int, s: Session) -> Response:
    """Guild picture (no auth: it is loaded by an <img> tag; the URL is versioned, cached for a year)."""
    raw = (await s.execute(select(Guild.emblem_img).where(Guild.id == guild_id))).scalar()
    if not raw:
        raise HTTPException(404)
    return Response(raw, media_type=_img_type(raw),
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.post("/guilds/{guild_id}/join")
async def join(guild_id: int, request: Request, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    u = await get_for_update(s, tg.id)
    now = now_ms()
    if await s.get(GuildMember, u.id) is not None:
        await s.rollback()
        raise HTTPException(409, "already_in_guild")
    if u.guild_left_ms and now - u.guild_left_ms < B.GUILD_REJOIN_COOLDOWN_MS:
        await s.rollback()
        raise HTTPException(429, "rejoin_cooldown")
    g = await s.get(Guild, guild_id, with_for_update=True)
    if g is None:
        await s.rollback()
        raise HTTPException(404, "guild_not_found")
    if g.members >= B.GUILD_MAX_MEMBERS:
        await s.rollback()
        raise HTTPException(409, "guild_full")
    g.members += 1
    s.add(GuildMember(user_id=u.id, guild_id=g.id, role="member", joined_ms=now))
    await s.commit()
    return {"guild": await _detail(request, s, g, u.id)}


async def _remove(s: Session, g: Guild, m: GuildMember, now: int) -> None:
    """Remove a member; if the owner leaves, the guild passes to the longest-standing member; when the last one leaves, the guild is deleted."""
    u = await s.get(User, m.user_id)
    u.guild_left_ms = now
    await s.delete(m)
    g.members -= 1
    if g.members <= 0:
        await s.flush()
        await s.delete(g)
        return
    if m.role == "owner":
        heir = (await s.execute(select(GuildMember).where(GuildMember.guild_id == g.id, GuildMember.user_id != m.user_id)
                                .order_by(GuildMember.joined_ms, GuildMember.user_id).limit(1))).scalar_one()
        heir.role = "owner"
        g.owner_id = heir.user_id


@router.post("/guild/leave")
async def leave(tg: CurrentTg, s: Session) -> dict:
    await get_for_update(s, tg.id)
    m = await s.get(GuildMember, tg.id)
    if m is None:
        raise HTTPException(404, "not_in_guild")
    g = await s.get(Guild, m.guild_id, with_for_update=True)
    await _remove(s, g, m, now_ms())
    await s.commit()
    return {"ok": True}


@router.post("/guild/kick/{user_id}")
async def kick(user_id: int, request: Request, tg: CurrentTg, s: Session) -> dict:
    me = await s.get(GuildMember, tg.id)
    if me is None or me.role != "owner":
        raise HTTPException(403, "owner_only")
    m = await s.get(GuildMember, user_id)
    if m is None or m.guild_id != me.guild_id or user_id == tg.id:
        raise HTTPException(404, "member_not_found")
    g = await s.get(Guild, me.guild_id, with_for_update=True)
    await _remove(s, g, m, now_ms())
    await s.commit()
    return {"guild": await _detail(request, s, g, tg.id)}


@router.post("/guild/quests/{quest_id}/{tier}/claim")
async def claim(quest_id: str, tier: int, request: Request, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    acc = await s.get(SteamAccount, tg.id)
    if acc is None or not acc.passed:
        raise HTTPException(403, "steam_not_verified")
    u = await get_for_update(s, tg.id)
    m = await s.get(GuildMember, u.id)
    if m is None:
        await s.rollback()
        raise HTTPException(404, "not_in_guild")
    now = now_ms()
    period = _week(request, now)
    claimed = {(c.quest, c.tier) for c in (await s.execute(select(GuildClaim).where(
        GuildClaim.user_id == u.id, GuildClaim.period == period))).scalars()}
    quests = {q["id"]: q for q in _quests(await _contrib(s, m.guild_id, period), u.id, claimed)}
    q = quests.get(quest_id)
    if q is None or not 0 <= tier < len(q["tiers"]):
        await s.rollback()
        raise HTTPException(404, "quest_not_found")
    t = q["tiers"][tier]
    if not t["can_claim"]:
        await s.rollback()
        raise HTTPException(400, "already_claimed" if t["claimed"] else "not_ready")
    s.add(GuildClaim(user_id=u.id, period=period, quest=quest_id, tier=tier, guild_id=m.guild_id, souls=t["souls"],
                     claimed_ms=now))
    await souls.earn(s, u, t["souls"], "guild", f"{period}:{quest_id}:{tier}", now)
    try:
        await s.flush()
    except IntegrityError as e:          # double click: the reward was already recorded by a parallel request
        await s.rollback()
        raise HTTPException(400, "already_claimed") from e
    await s.commit()
    g = await s.get(Guild, m.guild_id)
    return {"souls": t["souls"], "guild": await _detail(request, s, g, u.id), "state": state_out(u, now)}
