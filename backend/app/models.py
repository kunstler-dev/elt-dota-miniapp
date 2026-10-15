from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str | None] = mapped_column(String(8))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    # When this player was counted as a referral (Steam linked and verified): rewards are paid exactly once
    ref_confirmed_ms: Mapped[int | None] = mapped_column(BigInteger)
    # For the inviter: how many friends were counted (inviter leaderboard) and how many souls the friends brought
    ref_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", index=True)
    ref_souls: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    created_ms: Mapped[int] = mapped_column(BigInteger)
    # Last API request (online users in the admin panel)
    seen_ms: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", index=True)

    # ELT coin balance and lifetime earnings (leagues and rating don't drop when coins are spent)
    coins: Mapped[int] = mapped_column(BigInteger, default=0)
    earned_total: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    # League rating: decaying earnings (half-life balance.LEAGUE_HALF_LIFE_MS), normalized to league_ms
    league_score: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    league_ms: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    # Tapper. Times are Unix ms: works the same in SQLite and Postgres
    energy: Mapped[int] = mapped_column(Integer, default=0)
    energy_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    last_tap_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    tap_level: Mapped[int] = mapped_column(Integer, default=1)  # unused: tap power comes from the Arsenal
    # Arsenal: equipped items {hero: {slot: "<hero>:<set>:<slot>"}}; empty = the default look
    equipped: Mapped[str | None] = mapped_column(Text)
    # The hero the player taps with (everyone has Pudge)
    active_hero: Mapped[str] = mapped_column(String(32), default="pudge", server_default="pudge")
    energy_level: Mapped[int] = mapped_column(Integer, default=1)

    # Passive income: cached total across cards and the time of the last accrual
    profit_per_hour: Mapped[int] = mapped_column(BigInteger, default=0)
    passive_ms: Mapped[int] = mapped_column(BigInteger, default=0)

    # Souls are the second currency (tasks, referrals, weekly top -> shop). Every change is written to the ledger
    souls: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    # Daily reward: day number in the streak (1..N) and the last claim day (YYYY-MM-DD in TIMEZONE)
    daily_streak: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    daily_last: Mapped[str | None] = mapped_column(String(10))

    # Guess the Hero: heroes already shown (comma-separated ids), no repeats until the whole pool is done
    guess_seen: Mapped[str] = mapped_column(Text, default="", server_default="")
    # When the player last left a guild (joining another one is allowed after a day)
    guild_left_ms: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    # Required channel subscription (REQUIRED_CHANNEL): result of the last check and when it ran
    sub_ok: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sub_checked_ms: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

class Ledger(Base):
    """Souls ledger: where souls came from and where they went (souls buy real items, so an audit trail is required)."""

    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(32))  # task | referral | weekly_top | shop | admin …
    ref: Mapped[str | None] = mapped_column(String(64))
    created_ms: Mapped[int] = mapped_column(BigInteger)


class Activity(Base):
    """A player's activity points for a period: week 'w:2026-W42' (within a league) or month 'm:2026-10'.
    Leaderboards rank these, not coins, so upgrades don't count toward rank."""

    __tablename__ = "activity"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    period: Mapped[str] = mapped_column(String(12), primary_key=True)
    points: Mapped[int] = mapped_column(BigInteger, default=0)
    # league at the first activity of the week: the player competes in it all week, even after moving up
    league: Mapped[int] = mapped_column(Integer, default=0)
    updated_ms: Mapped[int] = mapped_column(BigInteger, default=0)


class PeriodPayout(Base):
    """Prizes for the period were paid (never paid again)."""

    __tablename__ = "period_payouts"

    period: Mapped[str] = mapped_column(String(12), primary_key=True)
    paid_ms: Mapped[int] = mapped_column(BigInteger)


class PrizeClaim(Base):
    """A real monthly-top prize (Arcana/Immortal/Dota Plus), handed out by an admin in Steam."""

    __tablename__ = "prize_claims"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(12))
    place: Mapped[int] = mapped_column(Integer)
    prize: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | sent
    created_ms: Mapped[int] = mapped_column(BigInteger)


class UserHero(Base):
    """Purchased heroes (Pudge isn't stored: everyone has him)."""

    __tablename__ = "user_heroes"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    hero_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    bought_ms: Mapped[int] = mapped_column(BigInteger)


class UserItem(Base):
    """Purchased Arsenal items (permanent)."""

    __tablename__ = "user_items"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    bought_ms: Mapped[int] = mapped_column(BigInteger)


class GameSession(Base):
    """One mini-game attempt: issued by the server, the result is accepted once."""

    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    game: Mapped[str] = mapped_column(String(16))
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_ms: Mapped[int] = mapped_column(BigInteger)
    finished_ms: Mapped[int | None] = mapped_column(BigInteger)


class GameDay(Base):
    """A player's attempts and best result in a mini-game for a game day (mini-game leaderboards come from here)."""

    __tablename__ = "game_days"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    game: Mapped[str] = mapped_column(String(16), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    plays: Mapped[int] = mapped_column(Integer, default=0)
    best: Mapped[int] = mapped_column(Integer, default=0)


class UserTask(Base):
    __tablename__ = "user_tasks"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    done_ms: Mapped[int] = mapped_column(BigInteger)
    # Last recheck of the condition (subscription/boost still active); indexed to select "not checked for a while"
    checked_ms: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", index=True)


class SteamAccount(Base):
    """Linked Steam account: strictly 1 Telegram <-> 1 Steam (unique on both sides)."""

    __tablename__ = "steam_accounts"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    steam_id: Mapped[str] = mapped_column(String(20), unique=True)
    persona: Mapped[str | None] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    linked_ms: Mapped[int] = mapped_column(BigInteger)
    # Anti-bot check: whether the account passed the thresholds (age, public profile, Dota) and the raw check data
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_ms: Mapped[int | None] = mapped_column(BigInteger)
    check_json: Mapped[str | None] = mapped_column(Text)


class SteamLinkToken(Base):
    """One-time token: links the browser redirect to Steam sign-in with the Telegram player (lives 10 minutes)."""

    __tablename__ = "steam_link_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    expires_ms: Mapped[int] = mapped_column(BigInteger)


class UserUpgrade(Base):
    __tablename__ = "user_upgrades"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    upgrade_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=0)


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(24))
    name_key: Mapped[str] = mapped_column(String(24), unique=True)   # casefold: the name is unique case-insensitively
    emblem: Mapped[str] = mapped_column(String(16), default="pudge")
    # Custom guild picture (jpeg/png/webp up to 300 KB, 256x256, resized by the client); version busts the cache
    emblem_img: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)  # don't load it in guild lists
    emblem_ver: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    about: Mapped[str] = mapped_column(String(140), default="")
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    members: Mapped[int] = mapped_column(Integer, default=1)
    created_ms: Mapped[int] = mapped_column(BigInteger)


class GuildMember(Base):
    """A player belongs to at most one guild."""

    __tablename__ = "guild_members"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    guild_id: Mapped[int] = mapped_column(Integer, ForeignKey("guilds.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(8), default="member")    # owner | member
    joined_ms: Mapped[int] = mapped_column(BigInteger)


class GuildPoints(Base):
    """A member's contribution to guild points for a week (period = w:YYYY-Www)."""

    __tablename__ = "guild_points"

    guild_id: Mapped[int] = mapped_column(Integer, ForeignKey("guilds.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    period: Mapped[str] = mapped_column(String(12), primary_key=True, index=True)
    points: Mapped[int] = mapped_column(Integer, default=0)


class GuildClaim(Base):
    """A claimed guild quest tier reward (once per player per week)."""

    __tablename__ = "guild_claims"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    period: Mapped[str] = mapped_column(String(12), primary_key=True)
    quest: Mapped[str] = mapped_column(String(16), primary_key=True)
    tier: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(Integer)
    souls: Mapped[int] = mapped_column(Integer)
    claimed_ms: Mapped[int] = mapped_column(BigInteger)


class ContestEntry(Base):
    """A contest video (TikTok / YouTube Shorts / YouTube). Views are refreshed by a background job
    (YouTube Data API, TikTok from the video page); an admin can enter views by hand and reject a video."""

    __tablename__ = "contest_entries"
    __table_args__ = (UniqueConstraint("platform", "video_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contest: Mapped[str] = mapped_column(String(16), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(8))           # youtube | tiktok
    video_id: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(512))
    title: Mapped[str | None] = mapped_column(String(256))
    author: Mapped[str | None] = mapped_column(String(128))
    published_ms: Mapped[int | None] = mapped_column(BigInteger)
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    views_ms: Mapped[int] = mapped_column(BigInteger, default=0)  # when the views were refreshed (0 = never)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)  # views entered by an admin; auto-refresh leaves them alone
    fetch_error: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | approved | rejected
    note: Mapped[str | None] = mapped_column(String(256))        # rejection reason
    created_ms: Mapped[int] = mapped_column(BigInteger)


class ShopItem(Base):
    """Souls shop showcase: real Dota 2 items, handed out by an admin (as a Steam gift)."""

    __tablename__ = "shop_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16))           # arcana | immortal | crimson | golden | other
    about: Mapped[str] = mapped_column(String(280), default="")
    price: Mapped[int] = mapped_column(BigInteger)          # souls = usd_cents/100 x souls-per-dollar rate
    # Item on the Steam Community Market: name and price of the cheapest listing (refreshed from the market)
    market_name: Mapped[str | None] = mapped_column(String(128))
    usd_cents: Mapped[int | None] = mapped_column(Integer)
    usd_ms: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    listings: Mapped[int | None] = mapped_column(Integer)
    stock: Mapped[int | None] = mapped_column(Integer)      # None = unlimited
    need_note: Mapped[bool] = mapped_column(Boolean, default=False)  # "your choice": the player writes what exactly they want
    image: Mapped[str | None] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class ShopOrder(Base):
    """Order: souls are charged immediately; an admin delivers the item (sent) or cancels with a refund (cancelled)."""

    __tablename__ = "shop_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(80))
    price: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(String(280), default="")
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | sent | cancelled
    admin_note: Mapped[str | None] = mapped_column(String(280))
    created_ms: Mapped[int] = mapped_column(BigInteger)
    updated_ms: Mapped[int] = mapped_column(BigInteger)


class DraftMatch(Base):
    """A draft duel match. Side A moves first. b_id = None means the opponent is a bot (rating doesn't change)."""

    __tablename__ = "draft_matches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    a_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    b_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bot_skill: Mapped[float | None] = mapped_column(Float)            # bot strength 0..1 (from the player's ELO)
    ranked: Mapped[bool] = mapped_column(Boolean, default=False)  # human vs human games only
    status: Mapped[str] = mapped_column(String(8), default="draft")  # draft | place | done
    actions: Mapped[str] = mapped_column(Text, default="[]")       # [{kind, side, hero, auto}]
    deadline_ms: Mapped[int] = mapped_column(BigInteger, default=0)  # end of the current turn / placement
    a_order: Mapped[str | None] = mapped_column(Text)              # the side's heroes by position 1..5
    b_order: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)               # outcome breakdown (JSON)
    winner: Mapped[str | None] = mapped_column(String(1))
    a_delta: Mapped[int] = mapped_column(Integer, default=0)
    b_delta: Mapped[int] = mapped_column(Integer, default=0)
    reward: Mapped[int] = mapped_column(BigInteger, default=0)     # ELT for a game against the bot (first 3 per day)
    created_ms: Mapped[int] = mapped_column(BigInteger)
    finished_ms: Mapped[int | None] = mapped_column(BigInteger)


class DraftQueue(Base):
    """Matchmaking: look for a human for 30 s, then a bot."""

    __tablename__ = "draft_queue"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    since_ms: Mapped[int] = mapped_column(BigInteger, index=True)
    match_id: Mapped[str | None] = mapped_column(String(32))


class DraftRating(Base):
    __tablename__ = "draft_ratings"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    elo: Mapped[int] = mapped_column(Integer, default=1000)
    games: Mapped[int] = mapped_column(Integer, default=0)     # rated (against humans)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    bot_games: Mapped[int] = mapped_column(Integer, default=0)


class DraftMonth(Base):
    """Monthly draft ladder: points = sum of ELO changes over the month (human vs human games only)."""

    __tablename__ = "draft_months"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    period: Mapped[str] = mapped_column(String(12), primary_key=True, index=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    games: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    updated_ms: Mapped[int] = mapped_column(BigInteger, default=0)


class ChatMessage(Base):
    """A chat message: channel = world or g:<guild id>."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(24), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(300))
    created_ms: Mapped[int] = mapped_column(BigInteger)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # hidden by reports


class ChatBan(Base):
    """Chat mute: until_ms is when it ends; PERMANENT is a permanent ban. Lifted by an admin."""

    __tablename__ = "chat_bans"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    until_ms: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(200), default="")
    by_id: Mapped[int] = mapped_column(BigInteger)
    created_ms: Mapped[int] = mapped_column(BigInteger)


class ChatReport(Base):
    """A message report (one per player); after CHAT_HIDE_REPORTS reports the message is hidden until an admin decides."""

    __tablename__ = "chat_reports"

    msg_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_messages.id", ondelete="CASCADE"), primary_key=True)
    reporter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_ms: Mapped[int] = mapped_column(BigInteger)


class AppSetting(Base):
    """Settings an admin changes from the Mini App (analysis beta, subscription price, etc.)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class OdCache(Base):
    """OpenDota response cache (free tier limit is ~2000 requests per day for the whole service)."""

    __tablename__ = "od_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[str] = mapped_column(Text, default="")
    fetched_ms: Mapped[int] = mapped_column(BigInteger)
    ttl_ms: Mapped[int] = mapped_column(BigInteger)


class AnalysisUsage(Base):
    """Opened match analyses: the free limit counts these (viewing the same match again is free)."""

    __tablename__ = "analysis_usage"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    match_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts_ms: Mapped[int] = mapped_column(BigInteger, index=True)


class AnalysisSub(Base):
    """Analysis subscription for Telegram Stars (30 days, renewed by Telegram)."""

    __tablename__ = "analysis_subs"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    expires_ms: Mapped[int] = mapped_column(BigInteger)
    charge_id: Mapped[str] = mapped_column(String(128))
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    started_ms: Mapped[int] = mapped_column(BigInteger)
    updated_ms: Mapped[int] = mapped_column(BigInteger)


class StarPayment(Base):
    __tablename__ = "star_payments"

    charge_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    payload: Mapped[str] = mapped_column(String(64))
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_ms: Mapped[int] = mapped_column(BigInteger)
    created_ms: Mapped[int] = mapped_column(BigInteger)
    refunded_ms: Mapped[int | None] = mapped_column(BigInteger)
