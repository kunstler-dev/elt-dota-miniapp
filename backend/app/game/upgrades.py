""""Heroes" in Upgrades: each hero level adds passive income per hour.
Each hero has a Dota 2 3D model: frontend/public/models/heroes/<id>/ (body.glb + items)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Upgrade:
    id: str
    category: str  # hero attribute: str | agi | int | all
    name: str
    abbr: str
    profit: int      # +income/h per level
    base_price: int  # level 1 price
    items: tuple[str, ...] = field(default=())  # item files next to body.glb
    growth: float = 1.6

    @property
    def model_dir(self) -> str:
        return f"/models/heroes/{self.id}/"

    @property
    def portrait(self) -> str:
        return f"/media/heroes/{self.id}.png"


# Placeholder numbers, tuned in the "Economy" stage
CATALOG: list[Upgrade] = [
    Upgrade("axe", "str", "Axe", "AXE", 90, 700,
            ("axe_armor", "axe_belt", "axe_hair", "axe_ponytail", "axe_weapon")),
    Upgrade("crystal_maiden", "int", "Crystal Maiden", "CM", 120, 1_000,
            ("crystal_maiden_cape", "crystal_maiden_cuffs", "crystal_maiden_shoulders", "crystal_maiden_staff",
             "head_item")),
    Upgrade("sniper", "agi", "Sniper", "SNP", 150, 1_300, ("bracer", "cape", "headitem", "shoulder", "weapon")),
    Upgrade("lina", "int", "Lina", "LNA", 180, 1_600, ("lina_arms", "lina_belt", "lina_head", "lina_neck")),
    Upgrade("juggernaut", "agi", "Juggernaut", "JUG", 220, 2_000,
            ("jugg_bracers", "jugg_cape", "jugg_mask", "jugg_sword", "juggernaut_pants")),
    Upgrade("drow", "agi", "Drow Ranger", "DRW", 260, 2_500,
            ("drow_armor", "drow_bracer", "drow_cape", "drow_haircowl", "drow_legs", "drow_quiver", "drow_weapon")),
    Upgrade("zeus", "int", "Zeus", "ZUS", 320, 3_200, ("zeus_belt", "zeus_bracers", "zeus_hair", "zeus_vest")),
    Upgrade("legion_commander", "str", "Legion Commander", "LC", 400, 4_000,
            ("legion_commander_arms", "legion_commander_back", "legion_commander_head",
             "legion_commander_shoulders", "legion_commander_weapon")),
    Upgrade("phantom_assassin", "agi", "Phantom Assassin", "PA", 500, 5_200,
            ("phantom_assassin_cape", "phantom_assassin_helmet", "phantom_assassin_shoulders",
             "phantom_assassin_weapon")),
    Upgrade("antimage", "agi", "Anti-Mage", "AM", 650, 7_000,
            ("antimage_arms", "antimage_belt", "antimage_chest", "antimage_head", "antimage_offhand_weapon",
             "antimage_weapon")),
    Upgrade("shadow_fiend", "agi", "Shadow Fiend", "SF", 850, 9_500,
            ("shadow_fiend_arms", "shadow_fiend_head", "shadow_fiend_shoulders", "shadow_fiend_wings")),
    Upgrade("invoker", "all", "Invoker", "INV", 1_100, 13_000,
            ("invoker_bracer", "invoker_cape", "invoker_dress", "invoker_hair", "invoker_head", "invoker_shoulder")),
]
BY_ID = {u.id: u for u in CATALOG}


def price(up: Upgrade, level: int) -> int:
    """Price of level level+1 at the current level."""
    return round(up.base_price * up.growth ** level)
