import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.main import create_app  # noqa: E402

BOT_TOKEN = "123456:TEST-TOKEN"

# Dota 2 hero models are Valve property and are not part of this repository.
# Tests that need them are marked `needs_assets` and skipped when the folder is absent.
MODELS_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "models"


def pytest_collection_modifyitems(config, items):
    if MODELS_DIR.is_dir():
        return
    skip = pytest.mark.skip(reason="Dota 2 3D models are not included (frontend/public/models)")
    for item in items:
        if "needs_assets" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 't.db'}", dev_auth=True, bot_token=BOT_TOKEN)


@pytest.fixture
async def app(settings):
    a = create_app(settings)
    db = Database(settings.db_url)
    await db.create_schema()
    a.state.db = db
    a.state.bot_username = "elt_test_bot"
    a.state.steam_checker = FakeChecker()
    yield a
    await db.close()


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def auth(uid: int, start_param: str | None = None) -> dict:
    return {"Authorization": f"tma dev:{uid}" + (f":{start_param}" if start_param else "")}


class FakeChecker:
    """No network: every account passes the check."""

    async def check(self, steam_id, th, now=None):
        return {"passed": True, "reasons": [], "persona": f"p{steam_id[-3:]}", "avatar": None}


def steam_id(uid: int) -> str:
    return f"7656119{uid:010d}"


async def player(client, uid: int, start_param: str | None = None) -> dict:
    """A player who signed in and linked Steam (via dev-link)."""
    h = auth(uid, start_param)
    await client.get("/api/me", headers=h)
    r = await client.post("/api/steam/dev-link", json={"steam_id": steam_id(uid)}, headers=h)
    assert r.status_code == 200, r.text
    return h
