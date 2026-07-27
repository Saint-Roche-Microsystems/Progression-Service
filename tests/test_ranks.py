"""Tests unitarios de la puntuación y resolución de rangos (sin BD)."""

from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.services.rank_evaluator import rank_progress, resolve_rank
from progression_service.domain.services.rank_scorer import compute_rank_score
from progression_service.domain.services.ranks_config import RANKS


def _full_sample(**overrides) -> UserStatistics:
    # 30 finalizadas -> confianza plena (sin penalización por muestra pequeña).
    base = dict(user_id="u", won=30, win_rate=50.0, roi=0.0, net_profit=0.0, consistency=50.0)
    base.update(overrides)
    return UserStatistics(**base)


def test_ranks_are_ordered_by_threshold():
    thresholds = [r.min_score for r in RANKS]
    assert thresholds == sorted(thresholds)
    assert [r.level for r in RANKS] == list(range(1, len(RANKS) + 1))


def test_score_monotonic_in_win_rate():
    low = compute_rank_score(_full_sample(win_rate=40.0), 100)
    high = compute_rank_score(_full_sample(win_rate=90.0), 100)
    assert high > low


def test_antiquity_increases_score():
    stats = _full_sample(win_rate=60.0)
    assert compute_rank_score(stats, 365) > compute_rank_score(stats, 0)


def test_low_sample_is_penalized():
    few = UserStatistics(user_id="u", won=2, win_rate=100.0, roi=50.0)
    assert compute_rank_score(few, 365) < 20  # confianza 2/30 -> muy bajo


def test_resolve_rank_tiers():
    assert resolve_rank(0.0).name == "Novato"
    assert resolve_rank(25.0).name == "Amateur"  # min_score 20
    assert resolve_rank(100.0).name == "Leyenda"


def test_rank_progress_midway():
    # score 15: entre Principiante (10) y Amateur (20) -> 50%.
    current, nxt, progress = rank_progress(15.0)
    assert current.name == "Principiante"
    assert nxt.name == "Amateur"
    assert progress == 50.0


def test_rank_progress_max_rank():
    current, nxt, progress = rank_progress(100.0)
    assert current.name == "Leyenda"
    assert nxt is None
    assert progress == 100.0
