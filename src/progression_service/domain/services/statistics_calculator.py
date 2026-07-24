"""Servicio de dominio PURO: calcula ``UserStatistics`` desde una lista de apuestas.

Sin dependencias de infraestructura ni de FastAPI, por lo que es directamente
testeable con listas de :class:`Bet` en memoria.

Convenciones de resultado realizado por apuesta (según su estado):

* ``WON``  -> beneficio = stake·(odds−1),  retorno = stake·odds
* ``LOST`` -> beneficio = −stake,          retorno = 0
* ``VOID`` -> beneficio = 0,               retorno = stake (se devuelve, es *push*)
* ``PENDING`` -> excluida de los cálculos financieros

Conjuntos usados:

* **finalizadas** = WON + LOST + VOID  (base de stake/retorno/medias)
* **decididas**   = WON + LOST         (base de win rate, rachas y consistencia;
  VOID se excluye por ser un empate/devolución)
"""

import statistics as _stats

from progression_service.domain.entities.bet import Bet, BetStatus
from progression_service.domain.entities.statistics import UserStatistics


def realized_profit(bet: Bet) -> float:
    """Beneficio realizado de una apuesta finalizada (0 para pendientes/void).

    Usa la cuota **combinada** (para parlays es el producto de las cuotas).
    """

    if bet.status == BetStatus.WON:
        return round(bet.stake * (bet.combined_odds - 1), 4)
    if bet.status == BetStatus.LOST:
        return round(-bet.stake, 4)
    return 0.0  # VOID (push) o PENDING


def realized_return(bet: Bet) -> float:
    """Retorno realizado de una apuesta finalizada."""

    if bet.status == BetStatus.WON:
        return round(bet.stake * bet.combined_odds, 4)
    if bet.status == BetStatus.VOID:
        return round(bet.stake, 4)
    return 0.0  # LOST o PENDING


def _current_streak(decided: list[Bet]) -> int:
    """Racha final: >0 victorias seguidas, <0 derrotas seguidas, 0 si no hay."""

    if not decided:
        return 0
    last_won = decided[-1].status == BetStatus.WON
    streak = 0
    for bet in reversed(decided):
        if (bet.status == BetStatus.WON) == last_won:
            streak += 1
        else:
            break
    return streak if last_won else -streak


def _best_win_streak(decided: list[Bet]) -> int:
    """Mayor número de victorias consecutivas del historial."""

    best = current = 0
    for bet in decided:
        if bet.status == BetStatus.WON:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _consistency(decided: list[Bet]) -> float:
    """Estabilidad del rendimiento (0..100).

    Se mide como ``100 / (1 + stddev(roi_i))`` donde ``roi_i`` es el beneficio
    realizado de cada apuesta decidida dividido por su stake. Menor variación de
    resultados -> mayor consistencia. Requiere al menos 2 apuestas decididas.
    """

    if len(decided) < 2:
        return 0.0
    per_bet_roi = [realized_profit(b) / b.stake for b in decided if b.stake > 0]
    if len(per_bet_roi) < 2:
        return 0.0
    stddev = _stats.pstdev(per_bet_roi)
    return round(100.0 / (1.0 + stddev), 4)


def _max_consecutive_days(bets: list[Bet]) -> int:
    """Mayor racha de días naturales consecutivos con al menos una apuesta.

    Se basa en ``created_at`` (fecha de registro de la apuesta = actividad real).
    """

    days = sorted({b.created_at.date() for b in bets})
    if not days:
        return 0
    best = run = 1
    for prev, curr in zip(days, days[1:]):
        run = run + 1 if (curr - prev).days == 1 else 1
        best = max(best, run)
    return best


def compute_statistics(user_id: str, bets: list[Bet], *, username: str = "") -> UserStatistics:
    """Calcula las estadísticas agregadas de un usuario a partir de sus apuestas."""

    stats = UserStatistics(user_id=user_id, username=username)
    stats.total_bets = len(bets)
    if not bets:
        return stats

    finalized = [b for b in bets if b.status in (BetStatus.WON, BetStatus.LOST, BetStatus.VOID)]
    # Decididas ordenadas cronológicamente para el cálculo de rachas.
    decided = sorted(
        (b for b in bets if b.status in (BetStatus.WON, BetStatus.LOST)),
        key=lambda b: b.event_datetime,
    )

    stats.won = sum(1 for b in bets if b.status == BetStatus.WON)
    stats.lost = sum(1 for b in bets if b.status == BetStatus.LOST)
    stats.void = sum(1 for b in bets if b.status == BetStatus.VOID)
    stats.pending = sum(1 for b in bets if b.status == BetStatus.PENDING)

    decided_count = stats.won + stats.lost
    stats.win_rate = round(stats.won / decided_count * 100, 2) if decided_count else 0.0

    if finalized:
        profits = [realized_profit(b) for b in finalized]
        stats.total_stake = round(sum(b.stake for b in finalized), 4)
        stats.total_return = round(sum(realized_return(b) for b in finalized), 4)
        stats.net_profit = round(sum(profits), 4)
        stats.roi = (
            round(stats.net_profit / stats.total_stake * 100, 2) if stats.total_stake else 0.0
        )
        stats.avg_odds = round(_stats.fmean(b.combined_odds for b in finalized), 4)
        stats.avg_stake = round(_stats.fmean(b.stake for b in finalized), 4)
        stats.biggest_win = round(max(profits + [0.0]), 4)
        stats.biggest_loss = round(min(profits + [0.0]), 4)

    stats.current_streak = _current_streak(decided)
    stats.best_streak = _best_win_streak(decided)
    stats.consistency = _consistency(decided)
    stats.last_bet_at = max(b.event_datetime for b in bets)

    # Variedad y actividad (para gamificación). Los deportes incluyen la
    # selección principal y todas las selecciones de los parlays.
    sports = {b.sport for b in bets} | {leg.sport for b in bets for leg in b.legs}
    stats.distinct_sports = len(sports)
    stats.distinct_bookmakers = len({b.bookmaker for b in bets})
    stats.max_consecutive_days = _max_consecutive_days(bets)
    stats.last_activity_at = max(b.created_at for b in bets)

    return stats
