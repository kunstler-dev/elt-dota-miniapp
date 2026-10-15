"""Chats: world (world) and guild (g:<id>). The client polls for new messages every few seconds.

Anti-spam: at most one message per CHAT_COOLDOWN_MS, up to 300 characters, no links (protects against ads
and scam links). Deletion: admins anywhere, a guild owner in their own guild chat."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..game import clicker
from ..models import ChatBan, ChatMessage, ChatReport, Guild, GuildMember, User
from ..services.users import get_or_create, now_ms
from .deps import AdminTg, CurrentTg, Session
from .routes import require_access

router = APIRouter(prefix="/api/chat")

CHAT_COOLDOWN_MS = 3_000
PAGE = 60
PERMANENT = 2**62               # permanent ban
CHAT_HIDE_REPORTS = 3           # this many reports hide the message until an admin decides
# Profanity: the whole word is replaced with asterisks (word roots with any prefixes and endings)
SWEAR = re.compile(r"\b\w*(ху[йяеёию]|пизд|еб[алнуо]|ёб|бля|сук[аи]\b|муда[кч]|мудил|гандон|пид[оа]?р|залуп|шлюх)\w*", re.I)
LINK = re.compile(r"(https?://|www\.|t\.me/|\b[\w-]+\.(ru|com|net|org|io|me|gg|xyz|ly|cc)\b|@\w{4,})", re.I)


def clean(text: str) -> str:
    return SWEAR.sub(lambda m: "*" * len(m.group(0)), text)


async def _ban(s: Session, uid: int, now: int) -> ChatBan | None:
    b = await s.get(ChatBan, uid)
    return b if b is not None and b.until_ms > now else None


async def _channel(s: Session, channel: str, uid: int) -> int | None:
    """Checks access to a channel. For a guild chat returns the guild id."""
    if channel == "world":
        return None
    m = re.fullmatch(r"g:(\d+)", channel)
    if not m:
        raise HTTPException(404, "channel_not_found")
    gid = int(m.group(1))
    me = await s.get(GuildMember, uid)
    if me is None or me.guild_id != gid:
        raise HTTPException(403, "not_in_guild")
    return gid


def _out(msg: ChatMessage, u: User | None, me: int, tags: dict[int, str]) -> dict:
    return {"id": msg.id, "user_id": msg.user_id, "name": (u.username or u.first_name or f"id{u.id}") if u else "?",
            "photo_url": u.photo_url if u else None, "league": clicker.league(u)["name"] if u else None,
            "guild": tags.get(msg.user_id), "text": msg.text, "created_ms": msg.created_ms, "me": msg.user_id == me}


@router.get("/{channel}")
async def history(channel: str, tg: CurrentTg, s: Session, after: int = 0) -> dict:
    await get_or_create(s, tg)
    await _channel(s, channel, tg.id)
    q = select(ChatMessage, User).join(User, User.id == ChatMessage.user_id).where(
        ChatMessage.channel == channel, ChatMessage.deleted.is_(False), ChatMessage.hidden.is_(False))
    if after:
        q = q.where(ChatMessage.id > after).order_by(ChatMessage.id).limit(PAGE)
        rows = (await s.execute(q)).all()
    else:
        rows = list(reversed((await s.execute(q.order_by(ChatMessage.id.desc()).limit(PAGE))).all()))
    # guild tag next to the nickname, in the world chat
    tags: dict[int, str] = {}
    if channel == "world" and rows:
        ids = {m.user_id for m, _ in rows}
        for uid, name in (await s.execute(select(GuildMember.user_id, Guild.name).join(Guild, Guild.id == GuildMember.guild_id)
                                          .where(GuildMember.user_id.in_(ids)))).all():
            tags[uid] = name
    ban = await _ban(s, tg.id, now_ms())
    await s.commit()
    return {"channel": channel, "messages": [_out(m, u, tg.id, tags) for m, u in rows], "cooldown_ms": CHAT_COOLDOWN_MS,
            "muted_until": ban.until_ms if ban else None, "muted_reason": ban.reason if ban else None}


class SendIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@router.post("/{channel}")
async def send(channel: str, body: SendIn, request: Request, tg: CurrentTg, s: Session) -> dict:
    await require_access(s, tg.id)
    await _channel(s, channel, tg.id)
    text = " ".join(body.text.split())
    if not text:
        raise HTTPException(400, "empty")
    if LINK.search(text):
        raise HTTPException(400, "no_links")
    text = clean(text)
    now = now_ms()
    if await _ban(s, tg.id, now):
        raise HTTPException(403, "muted")
    last = (await s.execute(select(ChatMessage.created_ms).where(ChatMessage.user_id == tg.id)
                            .order_by(ChatMessage.id.desc()).limit(1))).scalar()
    if last and now - last < CHAT_COOLDOWN_MS:
        raise HTTPException(429, "too_fast")
    msg = ChatMessage(channel=channel, user_id=tg.id, text=text, created_ms=now, deleted=False)
    s.add(msg)
    await s.commit()
    u = await s.get(User, tg.id)
    return {"message": _out(msg, u, tg.id, {})}


@router.delete("/msg/{msg_id}")
async def delete(msg_id: int, request: Request, tg: CurrentTg, s: Session) -> dict:
    msg = await s.get(ChatMessage, msg_id)
    if msg is None:
        raise HTTPException(404, "message_not_found")
    admin = tg.id in request.app.state.settings.admin_id_set
    owner = False
    if msg.channel.startswith("g:"):
        me = await s.get(GuildMember, tg.id)
        owner = me is not None and me.role == "owner" and f"g:{me.guild_id}" == msg.channel
    if not (admin or owner or msg.user_id == tg.id):
        raise HTTPException(403, "forbidden")
    msg.deleted = True
    await s.commit()
    return {"ok": True}


@router.post("/msg/{msg_id}/report")
async def report(msg_id: int, tg: CurrentTg, s: Session) -> dict:
    """Report a message: one report per player; after CHAT_HIDE_REPORTS the message is hidden."""
    await require_access(s, tg.id)
    msg = await s.get(ChatMessage, msg_id)
    if msg is None or msg.deleted:
        raise HTTPException(404, "message_not_found")
    if msg.user_id == tg.id:
        raise HTTPException(400, "own_message")
    if await s.get(ChatReport, (msg_id, tg.id)) is None:
        s.add(ChatReport(msg_id=msg_id, reporter_id=tg.id, created_ms=now_ms()))
        await s.flush()
    n = (await s.execute(select(func.count()).select_from(ChatReport).where(ChatReport.msg_id == msg_id))).scalar_one()
    if n >= CHAT_HIDE_REPORTS:
        msg.hidden = True
    await s.commit()
    return {"ok": True, "hidden": msg.hidden}


# ---------------- chat admin ----------------
def _uname(u: User | None, uid: int) -> str:
    return (u.username or u.first_name or str(uid)) if u else str(uid)


@router.get("/admin/state", include_in_schema=False)
async def admin_state(_: AdminTg, s: Session) -> dict:
    now = now_ms()
    bans = (await s.execute(select(ChatBan, User).join(User, User.id == ChatBan.user_id, isouter=True)
                            .where(ChatBan.until_ms > now).order_by(ChatBan.created_ms.desc()))).all()
    cnt = func.count(ChatReport.reporter_id)
    reported = (await s.execute(select(ChatMessage, User, cnt).join(ChatReport, ChatReport.msg_id == ChatMessage.id)
                                .join(User, User.id == ChatMessage.user_id).where(ChatMessage.deleted.is_(False))
                                .group_by(ChatMessage.id, User.id).order_by(cnt.desc(), ChatMessage.id.desc())
                                .limit(100))).all()
    return {
        "bans": [{"user_id": b.user_id, "name": _uname(u, b.user_id), "until_ms": b.until_ms,
                  "permanent": b.until_ms >= PERMANENT, "reason": b.reason} for b, u in bans],
        "reports": [{"id": m.id, "channel": m.channel, "text": m.text, "user_id": u.id, "name": _uname(u, u.id),
                     "reports": n, "hidden": m.hidden, "created_ms": m.created_ms} for m, u, n in reported],
    }


class BanIn(BaseModel):
    user_id: int
    minutes: int = Field(ge=0, le=525_600)   # 0 = permanent
    reason: str = Field(default="", max_length=200)
    purge: bool = False                       # delete all of the player's messages


@router.post("/admin/ban", include_in_schema=False)
async def admin_ban(body: BanIn, tg: AdminTg, s: Session) -> dict:
    now = now_ms()
    until = PERMANENT if body.minutes == 0 else now + body.minutes * 60_000
    b = await s.get(ChatBan, body.user_id)
    if b is None:
        b = ChatBan(user_id=body.user_id, until_ms=until, reason=body.reason, by_id=tg.id, created_ms=now)
        s.add(b)
    else:
        b.until_ms, b.reason, b.by_id, b.created_ms = until, body.reason, tg.id, now
    purged = 0
    if body.purge:
        for m in (await s.execute(select(ChatMessage).where(ChatMessage.user_id == body.user_id,
                                                            ChatMessage.deleted.is_(False)))).scalars():
            m.deleted = True
            purged += 1
    await s.commit()
    return {"ok": True, "until_ms": until, "purged": purged}


@router.delete("/admin/ban/{user_id}", include_in_schema=False)
async def admin_unban(user_id: int, _: AdminTg, s: Session) -> dict:
    b = await s.get(ChatBan, user_id)
    if b is not None:
        await s.delete(b)
        await s.commit()
    return {"ok": True}


@router.post("/admin/msg/{msg_id}/restore", include_in_schema=False)
async def admin_restore(msg_id: int, _: AdminTg, s: Session) -> dict:
    """Reports were not confirmed: restore the message and clear the reports."""
    msg = await s.get(ChatMessage, msg_id)
    if msg is None:
        raise HTTPException(404, "message_not_found")
    msg.hidden = False
    for r in (await s.execute(select(ChatReport).where(ChatReport.msg_id == msg_id))).scalars():
        await s.delete(r)
    await s.commit()
    return {"ok": True}