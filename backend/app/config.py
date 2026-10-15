from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All settings come from environment variables (or backend/.env locally)."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    bot_token: str = ""
    # Public https URL of the Mini App (on Railway, the service domain)
    webapp_url: str = ""
    # off: the bot does not start (local frontend development), polling: locally with a test bot,
    # webhook: production/staging
    bot_mode: Literal["off", "polling", "webhook"] = "off"
    webhook_secret: str = ""
    admin_ids: str = ""

    database_url: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'data' / 'dev.db').as_posix()}"
    # Create tables on startup (local SQLite only; in production use alembic upgrade head)
    auto_create_schema: bool = False

    # The app does not let users in without a subscription to this channel (the bot must be a channel admin)
    required_channel: str = "@ELT_TG"

    # Time zone of the "game day" (daily reward, leaderboard weeks/months)
    timezone: str = "Europe/Moscow"

    # Steam: the Web API key is optional (without it: XML profile + OpenDota). Anti-bot check thresholds
    steam_api_key: str = ""
    steam_min_age_days: int = 180
    steam_min_dota_hours: int = 100
    steam_min_opendota_matches: int = 100

    # Dota match analysis (OpenDota): beta is free for everyone; otherwise N free analyses per week
    # and a 30-day Telegram Stars subscription (an admin changes beta mode and price in the admin panel)
    analysis_beta_free: bool = True
    analysis_price_stars: int = 200
    analysis_free_per_week: int = 1

    # Video contest: YouTube Data API v3 key (Google Cloud Console) for view counts.
    # Without a key an admin enters YouTube views; TikTok is read from the video page
    youtube_api_key: str = ""

    # OpenDota key (opendota.com -> API Key): no daily limit of the free tier and faster draft data loading
    opendota_api_key: str = ""

    # Allow the `Authorization: tma dev:<id>` header without a Telegram signature (LOCAL ONLY)
    dev_auth: bool = False
    init_data_max_age: int = 86400

    @property
    def db_url(self) -> str:
        url = self.database_url
        # Railway provides postgres://… / postgresql://…; an async driver is needed
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix):]
        return url

    @property
    def admin_id_set(self) -> set[int]:
        return {int(x) for x in self.admin_ids.replace(" ", "").split(",") if x}


@lru_cache
def get_settings() -> Settings:
    return Settings()
