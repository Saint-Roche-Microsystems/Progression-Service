"""Schemas Pydantic para el ranking global."""

from pydantic import BaseModel

from progression_service.domain.entities.statistics import UserStatistics


class RankingEntry(BaseModel):
    """Una fila del ranking."""

    position: int
    username: str
    ranking_score: float
    win_rate: float
    roi: float
    net_profit: float
    total_bets: int
    current_streak: int

    @classmethod
    def from_entity(cls, stats: UserStatistics, position: int) -> "RankingEntry":
        return cls(
            position=position,
            username=stats.username,
            ranking_score=stats.ranking_score,
            win_rate=stats.win_rate,
            roi=stats.roi,
            net_profit=stats.net_profit,
            total_bets=stats.total_bets,
            current_streak=stats.current_streak,
        )


class RankingPage(BaseModel):
    """Página del ranking global."""

    items: list[RankingEntry]
    total: int
    page: int
    page_size: int


class RankingPosition(BaseModel):
    """Posición del usuario autenticado dentro del ranking."""

    position: int | None
    entry: RankingEntry | None
