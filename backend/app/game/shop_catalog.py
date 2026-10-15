"""Souls shop showcase: real Dota 2 items from the Steam Community Market.

Price in souls = market price (USD, cheapest listing) x the "souls per 1 USD" rate (admin setting).
Prices and images refresh from the market daily and by a button in the admin panel.
usd_cents are the starting prices (market, 2026-10-15) until the first refresh."""

from __future__ import annotations

from .balance import REF_BONUS

# (id, market name (market_hash_name), kind, starting price in cents)
CATALOG: list[tuple[str, str, str, int]] = [
    # Arcanas (standard quality; where the market only lists a bundle, the bundle)
    ("arc_king_kringle", "King Kringle", "arcana", 26197),
    ("arc_fluttering_breeze","Fluttering Breeze", "arcana", 11724),
    ("arc_orbliterator", "Intergalactic Orbliterator", "arcana", 10980),
    ("arc_winter_raven", "Roost of the Winter Raven", "arcana", 4550),
    ("arc_voth_domosh", "Blades of Voth Domosh", "arcana", 4200),
    ("arc_inner_abysm", "Fractal Horns of Inner Abysm", "arcana", 4086),
    ("arc_flockheart", "Flockheart's Gamble", "arcana", 3193),
    ("arc_magus_cypher", "The Magus Cypher", "arcana", 3160),
    ("arc_swine", "Swine of the Sunken Galley", "arcana", 3002),
    ("arc_thundergod", "Tempest Helm of the Thundergod", "arcana", 2611),
    ("arc_bladeform", "Bladeform Legacy", "arcana", 2606),
    ("arc_fiery_soul", "Fiery Soul of the Slayer", "arcana", 2487),
    ("arc_manifold", "Manifold Paradox", "arcana", 2284),
    ("arc_great_sage", "Great Sage's Reckoning", "arcana", 2234),
    ("arc_feast", "Feast of Abscession", "arcana", 2121),
    ("arc_dragonus", "The Devotions of Dragonus - Wings", "arcana", 2051),
    ("arc_demon_eater", "Demon Eater", "arcana", 1848),
    ("arc_shen", "The Resurrection of Shen - Wings", "arcana", 1773),
    ("arc_frost_avalanche", "Frost Avalanche", "arcana", 1750),
    # Expensive immortals, slightly cheaper than arcanas
    ("imm_blade_of_tears", "Blade of Tears", "immortal", 2843),
    ("imm_magus_accord", "Magus Accord", "immortal", 2672),
    ("imm_silent_wake", "Silent Wake", "immortal", 2226),
    ("imm_dark_artistry_hair", "Dark Artistry Hair", "immortal", 2007),
    ("imm_righteous_thunderbolt", "Righteous Thunderbolt", "immortal", 1990),
    # Collectibles: one Crimson and one Golden
    ("crimson_fetters", "Fetters of Omniscience of the Crimson Witness", "crimson", 28351),
    ("golden_shards_of_exile", "Golden Shards of Exile", "golden", 40269),
]

KIND_ORDER = {"crimson": 0, "golden": 1, "arcana": 2, "immortal": 3}

# The souls rate is derived from the cost per subscriber (decision 2026-10-15): 1 referred friend = RUB_PER_SUBSCRIBER RUB.
# A friend brings REF_BONUS souls -> 1 RUB = REF_BONUS / RUB_PER_SUBSCRIBER souls -> 1 USD = that x RUB_PER_USD.
# 500 souls per friend, 5 RUB, 90 RUB/USD -> 9000 souls per 1 USD; a 20 USD arcana = 180,000 souls = 360 friends.
# An admin can change the rate in the admin panel (Shop -> Showcase); the RUB/USD rate is updated by hand.
RUB_PER_SUBSCRIBER = 5
RUB_PER_USD = 90
DEFAULT_SOULS_PER_USD = round(REF_BONUS / RUB_PER_SUBSCRIBER * RUB_PER_USD)

# Item images from the market (in case a price refresh hasn't run yet); refreshed together with prices
CATALOG_IMAGES: dict[str, str] = {
    "crimson_fetters": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_nZzcOqO3KQ7UI6-4r642bhQBH9zMbf9C9W4OC6aahSM_icG2uUxPxl_-5kQSCMkxwrv2_VpYb0LCTVKld8ZdEoGqJW5kX60dX5MrzmsVTa344Wyn77jHhPvCpo4-hXA6Nx-fbXiwHEM709tZVRca6jGQPOBksoMUC-Ww/256fx256f",
    "golden_shards_of_exile": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_nW0MOlPHqZ2lJw55Pm5UDiU1L4k5vv7zZa4825baV9L_6sXyiZzON5ovVoQxakkBw3vDO6y974b3OfOAZyCJsmEeAJtUS7m9G2MOzm7gLc3d5GyXn3jSNLuitt47oKAPc7uvqAFZcoBNY/256fx256f",
    "arc_king_kringle": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIm52k-5XvHr0MmzMH6Z9hlz5ojn_lDxVA6jzsSzwjVQofH5bfBodvPLDWPCmbsv5eNsTirnkU1_5jmDmdj8ci3FbQQlWJR4EOYU8k7vKOsUZN4/256fx256f",
    "arc_fluttering_breeze": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGJazz1j_VPnAwvWoIX6a2lB54ZPg70vuTxrOnITl-DheofT7afJoeKPAWjfCxb8l5OVoFirnkEl2sDyBm4mqcnuWa1IiX5ciF-IU8k7vg_OWswo/256fx256f",
    "arc_orbliterator": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGJazz1j_VPnAwvWoIX6a2l974ILm7VjrQB7ll5Xf8jBZ4_u6bbZsNP-BQGLFlLp0tuVoTnnhwkh_5mXVwt_4dX-VPFVxDJElR7UMsEK6x9KzNb78p1uJfZJqPco/256fx256f",
    "arc_winter_raven": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGJazz1j_VPnAwvWoIX6a2kV25oLx60zsfh78oYXl6WwO7Pb8bvVod6TAVjbDwrcg6LVoGSznzBlwsWWDw4qsIy2SalAkD8Z4W6dU5cRVQHnv/256fx256f",
    "arc_voth_domosh": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_rRxMOuO0SU6lt49Ynw70uoRRj8kZjf7jVU_fbgaqc_dvTAWDHCkLkh5eA_THjnwU8j5jnWntygdnPFaw8gWJByROUPtw74zIPK8DFg5Q/256fx256f",
    "arc_inner_abysm": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGI2zyUS1Q7nAxtizOmmV6Vdx8cj1-FrmTxzOipPy7y1J7f6vbKEjdqWRWDHIk7wv57A7Gy_iwk1_4j6Gwt-ocimWPQF2CMByELIMukO_m8qnab2kEPA3ZA/256fx256f",
    "arc_flockheart": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_nT0c-eOHqQ7Bl685Xx1VTmRhTOn4Tj_CxaoP2peqFSLfGUB1iR0-13vuBWRyyykVMh4WWAyNn4ciqUPVIgXJd4FO8D4UbpldThZbuws1aNgopCxCqs3S9P8G81tCu_JpRn/256fx256f",
    "arc_magus_cypher": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH-TBwcOiPjSW91V0-oa751jgVA7OnY_w9SdJoaWtOfA6c_LDCDfAxbcntbg4TXvglE0j6mXSm42pIH-fO1BzDZR1E7IU8k7vrL5L17I/256fx256f",
    "arc_swine": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH-LRwMKoMGjY519y54_7_hblSBrilpn0sycPvPOoOKVpeKbFWzDHmOonsbg4GnDlxEt0t2WHz938JHmQbFQgCZFuBbldaRfPTHY/256fx256f",
    "arc_thundergod": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH-zR1tnuIX6a9VNm4Lj871XqDgf0i4Xf_DBY7vyvJqE1d6eWWzWUw-outeI-Tn3lk0lz6m3Qn9iteHPDOFUoA8MhEO5f5hCm0oqw1pH0Fe0/256fx256f",
    "arc_bladeform": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_zBxM2kJ3WW8EI69ZX361fmDhfkmZHl7yxa-uaRabZuIf6SMWCCxOt4_rMxGSqwkRh04GmGmIusIn6WbgJ1XJYlEOJZu0K8k4e0MLnm4Q3Wj9hbjXKpF3HkZ_M/256fx256f",
    "arc_fiery_soul": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_rdzcvuOmme4l9757jy5ljqRBXwl4Sv8jBS6Puge5trLPGeC2-RyPw4trE4TnjhxR5-5DvXzo6tc3KVbwIhWZN5RO8L4Bi6ltXnZejq51ffjpUFk3vjgtzp6A/256fx256f",
    "arc_manifold": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH-bcwsS1Onao5EVm9ZTn41eoTBz_l5Dv8SZk__O8aaBiOL-SHGSRz-9JoOAnSirkkx9-5D7Tw4v9cXiUbwAmDZR3TONbs0W4kdOzMezhtFTYjohCnzK-0H1hMCTDUg/256fx256f",
    "arc_great_sage": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_vbzcGkLESc7Fhyu4r75FLiWCL6l5jnwiNJ7POgaZtlJfGXQWqfz-Vzqd5iRie0qhw1sDyLm8GtI3iWbVNyD5t3F7MCsUTukNKxM-rk4QbY2o5BzC39jSIY7Xo55roHT-N7rZPJroiy/256fx256f",
    "arc_feast": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH-bBx82kenqF5ld79cjk_13gRCLwjJXh8yMV6aGoavQ4dKLECmXIxbwjs-RrTnuxzBt-5mmEnIyvJyqeOwN0App0QvlK7EeF6GlxmQ/256fx256f",
    "arc_dragonus": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH-Xf2t2zNG-f2lt084K7-VL-Vg_wip7f_DBY7vyvJ7dmOeeBD3OY_u9ks-BnTha9hR4YtzKRm7DxJDnIAUV7Q9UyFKNS3U3pxYH5NO6x5AfZ2YhFzS3-j3xP7Hs_t7xWWacnrKXQ2wDGNbxs5ZEHIaqiHAPOBks7AayffA/256fx256f",
    "arc_demon_eater": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_jR1c-zOHSF4Blm_Ibw5U7hSBj_mqnk-C9U4c2rabBoMr6SC2KVkLgl5OA-TC21lxx-sGuGwtz6eS2ROw92CcBxRLEIshHrkNDkKaq8sPDxdt5E/256fx256f",
    "arc_shen": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH-DRzc2kM26b9kZ85o7gpU_iTxr0mIPswjFL5uCnfJtsMvOSAGbf1-t4t-RvWiWMhg0uoTSRpY7rIirJP2ljUs01GbNf8FOmm9fmNuLq4gHW3t1Cziz5ii5MuCZutb0HWaUjrKKB3l7JNuY1tcQGdeHnE0rnKWaC3g/256fx256f",
    "arc_frost_avalanche": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGI2zyUS1Q7nX0dOyIXqb2lt0_YPx5BbkUwTiipfswi9a5varZptsMvOSAGavw-91u7MnSn_gzE5352yDyIuqdX2fOlNyX8NxTLQJ4xm_wNexNezm51GM2NkXyTK-0H0eWTfeGA/256fx256f",
    "imm_blade_of_tears": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_vb0dqpOXKZ4hlw4I_x-FzmTSLzkpfk-G1e-_qreqFsLM-RAmaUxKAv5OI8SnG3lxgh5GTdntqpcXOVagd1CcQmRbVcska6wIDuYejg5QPclcsbmmENjJio/256fx256f",
    "imm_magus_accord": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH__a1cWqMGnY7Ft4-5Xg61XYQA_8jan09HUU5v-jZ7Z5IfysD3Wd0tFiubYnGyjrlhxz5W3Szt6teXiSblRyDpYhRudctBiwxt3mY-i0swDX3ooXzjK-0H3PsGwypQ/256fx256f",
    "imm_silent_wake": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH_LGzN3uIXLB2l94-Yjm_ljrfh7wjpOv8CdI572qeqt6H-SaWFiZzON5ovVoQxawlA0i_W2Ey9yvdnqePVBzW5slQuEO40G_xNSzZO3jswyK2thNmS2s3yhKuC91o7FVYJUPrfE/256fx256f",
    "imm_dark_artistry_hair": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH__a1cWqMGnY4Vdn_7j1-E3uUgnjh9nk_DBQ0PO8fK1-NOKKMW-RyPxJve5tSiX9xBwjtm2Aw9r8dCmTPQEiW8F2E7ResBm7lNTkZOzm7wHbid0Wyy-qjDQJsHhDhOR44Q/256fx256f",
    "imm_righteous_thunderbolt": "https://community.cloudflare.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttydbPaERSR0Wqmu7LAocGIyi3kajH-zR1tnuOXKQ7UJ7_Ynz1U7iQA3-kNnt-DFToOirfbdSLPmUBnOeyOBxj_ZsTjm8myIqvDmAlsH4cC7BbQAiWZQhE-5ct0Xploe1Y-3g4QOMi4hDyyn_3XlN5no-5bsLT-N7rWsPhYD1/256fx256f",
}
