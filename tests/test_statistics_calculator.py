"""Tests del cálculo de estadísticas (dominio puro), migrado del monolito.

Anclan la equivalencia funcional: mismas apuestas -> mismas métricas que producía el
monolito, sin necesitar Mongo ni FastAPI.
"""

from datetime import datetime, timezone

from progression_service.domain.entities.bet import Bet, BetStatus, BetType
from progression_service.domain.services.statistics_calculator import compute_statistics


def _bet(odds: float, stake: float, status: BetStatus) -> Bet:
    b = Bet(
        user_id="u1",
        sport="Football",
        league="EPL",
        event="A vs B",
        bet_type=BetType.SIMPLE,
        market="1X2",
        selection="A",
        odds=odds,
        stake=stake,
        bookmaker="bk",
        event_datetime=datetime.now(timezone.utc),
        status=status,
    )
    b.recalculate()
    return b


def test_counts_and_win_rate():
    bets = [
        _bet(2.0, 10, BetStatus.WON),
        _bet(1.5, 20, BetStatus.LOST),
        _bet(3.0, 5, BetStatus.WON),
        _bet(2.5, 10, BetStatus.PENDING),
    ]
    stats = compute_statistics("u1", bets, username="ana")

    assert stats.total_bets == 4
    assert stats.won == 2
    assert stats.lost == 1
    assert stats.pending == 1
    # win rate sobre decididas (WON+LOST) = 2/3
    assert round(stats.win_rate, 2) == 66.67


def test_financials_exclude_pending():
    bets = [
        _bet(2.0, 10, BetStatus.WON),   # profit +10, return 20
        _bet(1.5, 20, BetStatus.LOST),  # profit -20, return 0
        _bet(2.5, 10, BetStatus.PENDING),
    ]
    stats = compute_statistics("u1", bets, username="ana")

    # stake sobre finalizadas = 10 + 20 = 30
    assert stats.total_stake == 30
    # net profit = +10 - 20 = -10
    assert stats.net_profit == -10
    assert stats.total_return == 20


def test_empty_history_is_zeroed():
    stats = compute_statistics("u1", [], username="ana")
    assert stats.total_bets == 0
    assert stats.win_rate == 0.0
    assert stats.net_profit == 0.0
