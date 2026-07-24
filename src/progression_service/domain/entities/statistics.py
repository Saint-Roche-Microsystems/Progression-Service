"""Entidad de dominio ``UserStatistics``. Value object puro, sin I/O.

Todas sus métricas se derivan del historial de apuestas mediante
:mod:`progression_service.domain.services.statistics_calculator`; nunca se editan a mano.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class UserStatistics:
    """Estadísticas agregadas de un usuario calculadas a partir de sus apuestas."""

    user_id: str
    username: str = ""

    # Conteos
    total_bets: int = 0
    won: int = 0
    lost: int = 0
    void: int = 0
    pending: int = 0

    # Rendimiento
    win_rate: float = 0.0  # %
    total_stake: float = 0.0
    total_return: float = 0.0
    net_profit: float = 0.0
    roi: float = 0.0  # %
    avg_odds: float = 0.0
    avg_stake: float = 0.0
    biggest_win: float = 0.0
    biggest_loss: float = 0.0

    # Rachas y estabilidad
    current_streak: int = 0  # >0 victorias seguidas, <0 derrotas seguidas
    best_streak: int = 0  # mayor racha de victorias consecutivas
    consistency: float = 0.0  # 0..100

    # Variedad y actividad (para gamificación)
    distinct_sports: int = 0
    distinct_bookmakers: int = 0
    max_consecutive_days: int = 0  # mayor racha de días naturales consecutivos apostando
    last_activity_at: datetime | None = None  # última fecha de registro (created_at)

    # Metadatos
    last_bet_at: datetime | None = None
    ranking_score: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
