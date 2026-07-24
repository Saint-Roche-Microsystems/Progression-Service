"""Servicio de dominio PURO: calcula el ``ranking_score`` de un usuario.

La puntuación combina varias métricas normalizadas a una escala 0..100 y aplica
una **penalización por pocas apuestas** para que un usuario con muy pocos
registros no escale a los primeros puestos.

Todas las constantes están agrupadas aquí para poder ajustar el ranking (o
incorporar nuevas métricas) sin tocar los casos de uso.
"""

import math

from progression_service.domain.entities.statistics import UserStatistics

# --- Parámetros ajustables -------------------------------------------------

#: A partir de cuántas apuestas finalizadas se considera "muestra suficiente".
MIN_BETS_THRESHOLD = 30

#: Escala del beneficio neto para el componente acotado con tanh.
PROFIT_SCALE = 100.0

#: Cuánto mueve cada unidad de racha al componente de racha.
STREAK_STEP = 5.0

#: Pesos de cada componente (deben sumar 1.0).
WEIGHTS = {
    "win_rate": 0.30,
    "roi": 0.25,
    "profit": 0.15,
    "consistency": 0.15,
    "streak": 0.05,
    "volume": 0.10,
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _finalized_count(stats: UserStatistics) -> int:
    return stats.won + stats.lost + stats.void


def compute_ranking_score(stats: UserStatistics) -> float:
    """Devuelve el ``ranking_score`` (0..100) de unas estadísticas dadas."""

    win_rate_c = _clamp(stats.win_rate)
    roi_c = _clamp(50.0 + stats.roi / 2.0)
    profit_c = 50.0 + 50.0 * math.tanh(stats.net_profit / PROFIT_SCALE)
    consistency_c = _clamp(stats.consistency)
    streak_c = _clamp(50.0 + stats.current_streak * STREAK_STEP)

    finalized = _finalized_count(stats)
    volume_c = _clamp(finalized / MIN_BETS_THRESHOLD * 100.0)

    base = (
        WEIGHTS["win_rate"] * win_rate_c
        + WEIGHTS["roi"] * roi_c
        + WEIGHTS["profit"] * profit_c
        + WEIGHTS["consistency"] * consistency_c
        + WEIGHTS["streak"] * streak_c
        + WEIGHTS["volume"] * volume_c
    )

    # Penalización por muestra pequeña: acerca a 0 la puntuación de quien tiene
    # pocas apuestas finalizadas.
    confidence = min(1.0, finalized / MIN_BETS_THRESHOLD)

    return round(base * confidence, 2)
