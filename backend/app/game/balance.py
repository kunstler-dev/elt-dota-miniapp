"""All economy numbers in one place. Values are placeholders, tuned in the "Economy" stage."""

ENERGY_BASE = 1000
ENERGY_PER_LEVEL = 500
ENERGY_REGEN_PER_SEC = 3

# Anti-autoclicker: no more than MAX_TAPS_PER_SEC on average, plus a TAP_BURST allowance per batch
MAX_TAPS_PER_SEC = 15
TAP_BURST = 30
TAP_WINDOW_CAP_SEC = 10

# Passive income accrues for at most this many seconds offline: coming back often beats going AFK
OFFLINE_CAP_SEC = 2 * 3600

# Daily login reward (ELT COIN) by streak day; a missed day restarts the streak, after the last day it loops
DAILY_REWARDS = [500, 1_000, 2_500, 5_000, 10_000, 15_000, 25_000, 50_000, 75_000, 100_000]

# SOULS ECONOMY (decision 2026-10-15). Souls are the only prize currency. Cost per subscriber is 5 RUB:
# 500 souls per friend = 5 RUB, hence the shop rate of 9000 souls per 1 USD (see game/shop_catalog.py). The main path to prizes is
# referrals: an arcana is about 360 friends. Playing without friends earns souls slowly:
# guild quests ~700/month, leaderboard wins a few thousand per month, and only for the best.
# Referrals (all in souls). A friend counts once they link Steam and pass the anti-bot check
REF_BONUS = 500            # to the inviter per friend
REF_BONUS_PREMIUM = 750    # … per friend with Telegram Premium (7.5 RUB: a real person who can boost the channel)
REF_WELCOME = 0            # to the invited friend for joining via a link: removed (decision 2026-10-15)
REF_SHARE_L1 = 0.10        # share of the souls the friend earns
REF_SHARE_L2 = 0.02        # share of the souls earned by friends of friends

# Mini-games (ELT COIN): attempts per day and rewards
HOOK_PLAYS_PER_DAY = 5
HOOK_DURATION_SEC = 30
HOOK_COOLDOWN_MS = 800
HOOK_COIN_PER_HIT = 250        # per point: enemy 1, golden mega creep 3, own creep -1; combo up to x3
HOOK_MAX_POINTS_PER_THROW = 9  # 3 points x combo multiplier 3: the ceiling used to validate a result
GUESS_PLAYS_PER_DAY = 3        # streaks per day (a streak lasts until the first mistake)
GUESS_COIN_PER_STREAK = 400    # per correct answer: 400 x position in the streak (1st = 400, 5th = 2000…)

# Activity points (leaderboards): what earns them and how many
ACT_TAP = 1               # per accepted tap (taps are limited by energy)
ACT_HOOK_HIT = 15         # per hook hit in the mini-game
ACT_GUESS_PER_STREAK = 25 # Guess the Hero: per length of the best streak of the day
ACT_DAILY = 50            # claimed the daily reward
ACT_TASK = 30             # completed a task

# Prizes. Weekly: souls, places 1..N within each league; monthly: real items (handed out by an admin)
WEEK_PRIZES_SOULS = [600, 350, 200, 100, 100, 80, 60, 50, 40, 30]
MONTH_PRIZES = ["arcana", "immortal", "immortal"] + ["dota_plus"] * 7
TOP_SIZE = 50

# Guilds: weekly guild points = activity points members earned while in this guild
# (switching guilds does not carry points over). Guild quests are weekly, rewarded with souls to every member
# who contributed at least GUILD_MIN_CONTRIB points.
GUILD_CREATE_COST = 50_000           # ELT COIN
GUILD_MAX_MEMBERS = 30
GUILD_MIN_CONTRIB = 300
GUILD_REJOIN_COOLDOWN_MS = 24 * 3600 * 1000
GUILD_QUESTS: list[dict] = [
    {"id": "points", "title": "Очки гильдии за неделю", "tiers": [(20_000, 10), (100_000, 25), (300_000, 60)]},
    {"id": "active", "title": f"Участники с {GUILD_MIN_CONTRIB}+ очков за неделю", "tiers": [(5, 10), (12, 20), (25, 40)]},
]
GUILD_EMBLEMS = ["pudge", "axe", "drow", "antimage", "invoker", "shadow_fiend"]
# Guild wars: weekly result, top 3 guilds by points; souls to every member who contributed at least GUILD_MIN_CONTRIB
GUILD_WAR_PRIZES = [300, 200, 100]

# Draft duel: ELO rating (human vs human only), a bot after 30 s of matchmaking
DRAFT_ELO_START = 1000
DRAFT_K = 32
DRAFT_QUEUE_MS = 30_000
DRAFT_BOT_REWARD_GAMES = 3               # rewarded games against the bot per day; after that, no rewards
DRAFT_BOT_COINS = {"win": 3_000, "loss": 1_000}
DRAFT_MONTH_MIN_GAMES = 5                # monthly ladder requires at least 5 rated games
DRAFT_MONTH_PRIZES_SOULS = [2_500, 1_500, 1_000, 700, 500, 400, 300, 250, 200, 150]

# Leagues are dynamic, like MMR (decision 2026-10-15). League rating = ELT earned, with decay:
# every LEAGUE_HALF_LIFE_MS the weight of older earnings halves: play often and you rise, stop and you fall.
# League by rank among players with rating > 0: (name, top share, minimum rating).
# The minimum keeps anyone from becoming "Titan" while there are few players.
LEAGUE_HALF_LIFE_MS = 7 * 24 * 3600 * 1000
LEAGUE_TABLE: list[tuple[str, float, int]] = [
    ("Рекрут", 1.0, 0),
    ("Страж", 0.75, 2_000),
    ("Рыцарь", 0.55, 8_000),
    ("Герой", 0.35, 25_000),
    ("Легенда", 0.20, 70_000),
    ("Властелин", 0.10, 180_000),
    ("Божество", 0.05, 450_000),
    ("Титан", 0.01, 1_200_000),
]
LEAGUES: list[tuple[str, int]] = [(n, m) for n, _, m in LEAGUE_TABLE]
