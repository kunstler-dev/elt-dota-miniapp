from app.game import balance as B
from app.game import leagues as L
from app.models import User

DAY = 24 * 3600 * 1000


def user(score=0, ms=0):
    u = User(id=1)
    u.league_score, u.league_ms = score, ms
    return u


def test_rating_decays_and_grows():
    u = user()
    L.add(u, 10_000, now_ms=1_000)
    assert L.rating(u, 1_000) == 10_000
    assert L.rating(u, 1_000 + B.LEAGUE_HALF_LIFE_MS) == 5_000          # a week without playing: half
    L.add(u, 1_000, now_ms=1_000 + B.LEAGUE_HALF_LIFE_MS)              # came back: old rating decayed, new earnings added on top
    assert u.league_score == 6_000


def test_percentile_cutoffs_and_minimums():
    try:
        # 1000 players rated 1..1000 x 2000: the top 1% (10 best) starts at 991 x 2000
        cut = L.recompute([i * 2000 for i in range(1, 1001)])
        assert cut[0] == 0 and cut == sorted(cut)
        assert cut[-1] == 1_982_000
        top = user(2_000_000, 1)
        assert L.league(top, 1)["name"] == "Титан"
        mid = user(1_000_000, 1)    # top 50% -> Knight (top 55%), but not Hero (top 35%)
        assert L.league(mid, 1)["name"] == "Рыцарь"
        # few players: minimum thresholds apply, a single player with 5000 doesn't become Titan
        cut = L.recompute([5_000])
        assert L.league(user(5_000, 1), 1)["name"] == "Страж"
        assert cut[-1] == B.LEAGUE_TABLE[-1][2]
        # gone: rating halves every week, league drops
        L.recompute([])
        u = user(30_000, 1)
        assert L.league(u, 1)["name"] == "Герой"
        assert L.league(u, 1 + 3 * B.LEAGUE_HALF_LIFE_MS)["name"] == "Страж"    # 3 weeks without playing: 3750
        assert L.league(u, 1 + 5 * B.LEAGUE_HALF_LIFE_MS)["name"] == "Рекрут"   # 5 weeks: ~940
    finally:
        L.recompute([])
