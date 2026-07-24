"""Schemas Pydantic para rangos."""

from datetime import datetime

from pydantic import BaseModel

from progression_service.domain.entities.rank import RankDefinition


class RankResponse(BaseModel):
    """Definición de un rango."""

    level: int
    name: str
    icon: str
    min_score: float

    @classmethod
    def from_definition(cls, rank: RankDefinition) -> "RankResponse":
        return cls(level=rank.level, name=rank.name, icon=rank.icon, min_score=rank.min_score)


class RankMeResponse(BaseModel):
    """Rango actual del usuario y progreso hacia el siguiente."""

    rank_score: float
    current: RankResponse
    next: RankResponse | None
    progress: float  # % hacia el siguiente rango (100 si es el máximo)
    rank_updated_at: datetime | None
