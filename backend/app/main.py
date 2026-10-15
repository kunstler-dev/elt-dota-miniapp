from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from .api.admin import router as admin_router
from .api.analysis import router as analysis_router
from .api.arsenal import router as arsenal_router
from .api.chat import router as chat_router
from .api.contest import router as contest_router
from .api.draft import router as draft_router
from .api.friends import router as friends_router
from .api.games import router as games_router
from .api.guilds import router as guilds_router
from .api.profile import router as profile_router
from .api.shop import router as shop_router
from .api.top import router as top_router
from .api.routes import router as api_router
from .api.steam import router as steam_router
from .api.tasks import router as tasks_router
from . import jobs
from .config import Settings, get_settings
from .db import Database

log = logging.getLogger("elt")

# Built frontend: in Docker it goes to /app/static, locally it is frontend/dist
STATIC_CANDIDATES = [Path(__file__).resolve().parent.parent / "static",
                     Path(__file__).resolve().parents[2] / "frontend" / "dist"]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.db_url)
        if settings.auto_create_schema:
            await db.create_schema()
        app.state.db = db
        app.state.bot_username = None
        app.state.bot = app.state.dp = None
        polling = None
        bot = None
        if settings.bot_token and settings.bot_mode != "off":
            from .bot import create_bot, create_dispatcher, setup_menu
            bot = create_bot(settings)
            dp = create_dispatcher(settings, db)
            app.state.bot_username = (await bot.get_me()).username
            app.state.bot = bot  # the API needs it (subscription checks) in both modes
            await setup_menu(bot, settings)
            if settings.bot_mode == "webhook":
                app.state.dp = dp
                url = settings.webapp_url.rstrip("/") + "/bot/webhook"
                await bot.set_webhook(url, secret_token=settings.webhook_secret or None,
                                      allowed_updates=dp.resolve_used_update_types())
            else:
                await bot.delete_webhook()
                polling = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
            log.info("bot @%s started (%s)", app.state.bot_username, settings.bot_mode)
        # period prizes always run; task rechecks only with the bot (Telegram can't be asked without it)
        background = [asyncio.create_task(jobs.loop(app, with_bot=bot is not None)),
                      asyncio.create_task(jobs.draft_loader(app))]
        try:
            yield
        finally:
            for t in [polling, *background]:
                if t:
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await t
            if bot:
                await bot.session.close()
            await db.close()

    app = FastAPI(title="ELT", lifespan=lifespan, docs_url="/api/docs" if settings.dev_auth else None,
                  redoc_url=None, openapi_url="/api/openapi.json" if settings.dev_auth else None)
    app.state.settings = settings
    app.include_router(api_router)
    app.include_router(steam_router)
    app.include_router(tasks_router)
    app.include_router(friends_router)
    app.include_router(arsenal_router)
    app.include_router(games_router)
    app.include_router(top_router)
    app.include_router(profile_router)
    app.include_router(analysis_router)
    app.include_router(guilds_router)
    app.include_router(admin_router)
    app.include_router(contest_router)
    app.include_router(shop_router)
    app.include_router(draft_router)
    app.include_router(chat_router)

    @app.post("/bot/webhook", include_in_schema=False)
    async def webhook(request: Request) -> dict:
        bot, dp = request.app.state.bot, request.app.state.dp
        if dp is None:
            raise HTTPException(404)
        if settings.webhook_secret and request.headers.get(
                "x-telegram-bot-api-secret-token") != settings.webhook_secret:
            raise HTTPException(403)
        from aiogram.types import Update
        await dp.feed_update(bot, Update.model_validate(await request.json(), context={"bot": bot}))
        return {"ok": True}

    static = next((p for p in STATIC_CANDIDATES if (p / "index.html").exists()), None)
    app.state.static_dir = static
    if static is not None:
        index = static / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str) -> FileResponse:
            # build files are served as is, everything else gets index.html (client-side routing)
            if path.startswith("api/"):
                raise HTTPException(404)
            f = (static / path).resolve()
            if path and f.is_file() and static.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs the full URL of every request, which can contain API keys (OpenDota, YouTube): keep it out of the logs
logging.getLogger("httpx").setLevel(logging.WARNING)
app = create_app()
