"""Prices and images of Dota 2 items from the Steam Community Market, souls-to-dollar rate, showcase sync."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..game.shop_catalog import CATALOG, CATALOG_IMAGES, DEFAULT_SOULS_PER_USD, KIND_ORDER
from ..models import AppSetting, ShopItem

log = logging.getLogger("elt.market")

# by listing count: the regular item (hundreds of listings) comes before its bundles and Autographed versions with the same name
SEARCH = ("https://steamcommunity.com/market/search/render/?appid=570&norender=1&count=10&currency=1"
          "&sort_column=quantity&sort_dir=desc&query=")
IMAGE = "https://community.cloudflare.steamstatic.com/economy/image/{}/256fx256f"
REFRESH_EVERY_MS = 24 * 3600 * 1000
RATE_KEY = "shop_souls_per_usd"
PAUSE_S = 3.5          # the market quickly answers 429 without a login, so go slowly

Fetch = Callable[[str], Awaitable[httpx.Response]]


async def _get(url: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "Mozilla/5.0 ELT"}) as c:
        return await c.get(url)


async def rate(s: AsyncSession) -> int:
    row = await s.get(AppSetting, RATE_KEY)
    return int(row.value) if row and row.value.isdigit() else DEFAULT_SOULS_PER_USD


def souls_for(usd_cents: int, per_usd: int) -> int:
    return max(1, math.ceil(usd_cents * per_usd / 100))


async def set_rate(s: AsyncSession, per_usd: int) -> None:
    row = await s.get(AppSetting, RATE_KEY)
    if row is None:
        s.add(AppSetting(key=RATE_KEY, value=str(per_usd)))
    else:
        row.value = str(per_usd)
    await reprice(s, per_usd)


async def reprice(s: AsyncSession, per_usd: int | None = None) -> None:
    per_usd = per_usd or await rate(s)
    for it in (await s.execute(select(ShopItem).where(ShopItem.usd_cents.is_not(None)))).scalars():
        it.price = souls_for(it.usd_cents, per_usd)


async def sync_catalog(s: AsyncSession) -> None:
    """Showcase = the catalog from code: missing items are added, extra ones (old "your choice") are removed.
    Prices, stock and visibility set by an admin on existing items are left alone."""
    per_usd = await rate(s)
    have = {i.id: i for i in (await s.execute(select(ShopItem))).scalars()}
    ids = {c[0] for c in CATALOG}
    for iid, item in have.items():
        if iid not in ids:
            await s.delete(item)
        else:
            if item.usd_cents is not None:
                item.price = souls_for(item.usd_cents, per_usd)   # the rate may have changed (in code or in the admin panel)
            if not item.image:
                item.image = CATALOG_IMAGES.get(iid)
    for n, (iid, name, kind, cents) in enumerate(CATALOG):
        if iid in have:
            continue
        s.add(ShopItem(id=iid, title=name, kind=kind, about="", market_name=name, usd_cents=cents, usd_ms=0,
                       price=souls_for(cents, per_usd), stock=None, need_note=False, image=CATALOG_IMAGES.get(iid), active=True,
                       sort=KIND_ORDER.get(kind, 9) * 100 + n))
    await s.flush()


async def lookup(name: str, fetch: Fetch = _get) -> dict | None:
    """Cheapest listing and item image by exact market name."""
    r = await fetch(SEARCH + quote(name))
    if r.status_code != 200:
        raise RuntimeError(f"market {r.status_code}")
    for x in r.json().get("results") or []:
        if x.get("hash_name") == name:
            icon = (x.get("asset_description") or {}).get("icon_url")
            return {"usd_cents": int(x.get("sell_price") or 0), "listings": int(x.get("sell_listings") or 0),
                    "image": IMAGE.format(icon) if icon else None}
    return None


async def refresh_prices(db, now: int, force: bool = False, fetch: Fetch = _get, pause: float = PAUSE_S) -> dict:
    """Refreshes showcase prices from the market (at most once a day per item, unless force)."""
    stats = {"updated": 0, "missing": 0, "failed": 0}
    async with db.sessions() as s:
        q = select(ShopItem).where(ShopItem.market_name.is_not(None))
        if not force:
            q = q.where(ShopItem.usd_ms < now - REFRESH_EVERY_MS)
        todo = [(i.id, i.market_name) for i in (await s.execute(q)).scalars()]
    for n, (iid, name) in enumerate(todo):
        if n:
            await asyncio.sleep(pause)
        try:
            d = await lookup(name, fetch)
        except Exception as e:  # noqa: BLE001
            log.warning("market %s: %s", name, e)
            stats["failed"] += 1
            if "429" in str(e):
                break
            continue
        async with db.sessions() as s:
            it = await s.get(ShopItem, iid)
            if it is None:
                continue
            it.usd_ms = now
            if d is None or not d["usd_cents"]:
                it.listings = 0          # no listings: keep the old price; the showcase shows "not on the market"
                stats["missing"] += 1
            else:
                it.usd_cents, it.listings = d["usd_cents"], d["listings"]
                it.price = souls_for(d["usd_cents"], await rate(s))
                if d["image"]:
                    it.image = d["image"]
                stats["updated"] += 1
            await s.commit()
    return stats
