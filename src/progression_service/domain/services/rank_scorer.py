"""Servicio de dominio PURO: puntuación de rango (0..100).

Fórmula **modular** y fácilmente ajustable: combina las mismas componentes que el
``ranking_scorer`` (rendimiento, consistencia, racha, volumen) y añade la
**antigüedad** en la plataforma. Reutiliza sus helpers/constantes para no
duplicar lógica.
"""

import math

from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.services.ranking_scorer import (
    MIN_BETS_THRESHOLD,
    PROFIT_SCALE,
    STREAK_STEP,
    _clamp,
    _finalized_count,
)

# --- Parámetros ajustables -------------------------------------------------

#: Días de antigüedad para alcanzar el componente máximo de antigüedad.
AGE_TARGET_DAYS = 365

#: Pesos de cada componente (deben sumar 1.0).
WEIGHTS = {
    "win_rate": 0.22,
    "roi": 0.20,
    "profit": 0.13,
    "consistency": 0.13,
    "streak": 0.05,
    "volume": 0.12,
    "antiquity": 0.15,
}


def compute_rank_score(stats: UserStatistics, account_age_days: int) -> float:
    """Devuelve la puntuación de rango (0..100)."""

    win_rate_c = _clamp(stats.win_rate)
    roi_c = _clamp(50.0 + stats.roi / 2.0)
    profit_c = 50.0 + 50.0 * math.tanh(stats.net_profit / PROFIT_SCALE)
    consistency_c = _clamp(stats.consistency)
    streak_c = _clamp(50.0 + stats.current_streak * STREAK_STEP)

    finalized = _finalized_count(stats)
    volume_c = _clamp(finalized / MIN_BETS_THRESHOLD * 100.0)
    antiquity_c = _clamp(max(account_age_days, 0) / AGE_TARGET_DAYS * 100.0)

    base = (
        WEIGHTS["win_rate"] * win_rate_c
        + WEIGHTS["roi"] * roi_c
        + WEIGHTS["profit"] * profit_c
        + WEIGHTS["consistency"] * consistency_c
        + WEIGHTS["streak"] * streak_c
        + WEIGHTS["volume"] * volume_c
        + WEIGHTS["antiquity"] * antiquity_c
    )

    # Penalización por muestra pequeña (igual que en el ranking): un usuario con
    # muy pocas apuestas no escala de rango.
    confidence = min(1.0, finalized / MIN_BETS_THRESHOLD)

    return round(base * confidence, 2)
