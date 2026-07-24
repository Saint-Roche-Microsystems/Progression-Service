"""Schemas Pydantic para estadísticas de usuario."""

from datetime import datetime

from pydantic import BaseModel

from progression_service.domain.entities.statistics import UserStatistics


class StatisticsResponse(BaseModel):
    """Estadísticas completas de un usuario."""

    user_id: str
    username: str
    total_bets: int
    won: int
    lost: int
    void: int
    pending: int
    win_rate: float
    total_stake: float
    total_return: float
    net_profit: float
    roi: float
    avg_odds: float
    avg_stake: float
    biggest_win: float
    biggest_loss: float
    current_streak: int
    best_streak: int
    consistency: float
    distinct_sports: int
    distinct_bookmakers: int
    max_consecutive_days: int
    last_activity_at: datetime | None
    last_bet_at: datetime | None
    ranking_score: float
    updated_at: datetime

    @classmethod
    def from_entity(cls, stats: UserStatistics) -> "StatisticsResponse":
        return cls(**vars(stats))
