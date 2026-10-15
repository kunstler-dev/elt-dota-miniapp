from pathlib import Path

import pytest

from app.game.upgrades import CATALOG

PUBLIC = Path(__file__).resolve().parents[2] / "frontend" / "public"


@pytest.mark.needs_assets
def test_hero_assets_exist():
    missing = []
    for h in CATALOG:
        d = PUBLIC / h.model_dir.strip("/")
        for f in ["body", *h.items]:
            if not (d / f"{f}.glb").exists():
                missing.append(f"{h.id}/{f}.glb")
        if not (PUBLIC / h.portrait.strip("/")).exists():
            missing.append(h.portrait)
    assert not missing


def test_categories_and_unique_ids():
    assert {h.category for h in CATALOG} <= {"str", "agi", "int", "all"}
    assert len({h.id for h in CATALOG}) == len(CATALOG)
