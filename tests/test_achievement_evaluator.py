"""Tests unitarios del evaluador de logros (sin BD)."""

from datetime import datetime, timezone

from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.services.achievement_evaluator import evaluate

NOW = datetime(2026, 7, 11, tzinfo=timezone.utc)


def _unlocked_ids(stats: UserStatistics, already=()) -> set[str]:
    return set(evaluate(stats, NOW, already))


def test_streaks_by_best_streak():
    ids = _unlocked_ids(UserStatistics(user_id="u", best_streak=5))
    assert "streak_3" in ids and "streak_5" in ids
    assert "streak_10" not in ids and "streak_20" not in ids


def test_experience_thresholds():
    ids = _unlocked_ids(UserStatistics(user_id="u", total_bets=10))
    assert {"exp_first", "exp_10"} <= ids
    assert "exp_50" not in ids


def test_profitability():
    ids = _unlocked_ids(UserStatistics(user_id="u", net_profit=50.0, roi=25.0))
    assert {"profit_first", "roi_positive", "roi_20"} <= ids
    assert "profit_target" not in ids  # requiere 500


def test_precision_requires_minimum_decided():
    # Win rate altísimo pero solo 5 decididas -> no cuenta (evita sesgo).
    biased = UserStatistics(user_id="u", won=5, lost=0, win_rate=100.0)
    assert _unlocked_ids(biased) & {"winrate_60", "winrate_70", "winrate_80"} == set()

    # 20 decididas con 85% -> desbloquea los tres.
    solid = UserStatistics(user_id="u", won=17, lost=3, win_rate=85.0)
    assert {"winrate_60", "winrate_70", "winrate_80"} <= _unlocked_ids(solid)


def test_activity_streak_and_monthly():
    stats = UserStatistics(user_id="u", max_consecutive_days=7, last_activity_at=NOW)
    ids = _unlocked_ids(stats)
    assert "activity_7" in ids and "activity_monthly" in ids
    assert "activity_30" not in ids


def test_variety_bookmakers_and_sports():
    stats = UserStatistics(user_id="u", distinct_bookmakers=3, distinct_sports=5)
    ids = _unlocked_ids(stats)
    assert "bookmakers_3" in ids and "bookmakers_5" not in ids
    assert "sports_3" in ids and "sports_5" in ids


def test_monotonic_skips_already_unlocked():
    stats = UserStatistics(user_id="u", total_bets=10)
    # exp_first ya obtenido -> no debe reaparecer en los "nuevos".
    ids = evaluate(stats, NOW, ("exp_first",))
    assert "exp_first" not in ids
    assert "exp_10" in ids
