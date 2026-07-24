"""Schemas Pydantic para logros."""

from datetime import datetime

from pydantic import BaseModel

from progression_service.domain.entities.achievement import (
    AchievementCategory,
    AchievementDefinition,
)


class AchievementResponse(BaseModel):
    """Definición de un logro del catálogo."""

    id: str
    name: str
    description: str
    category: AchievementCategory
    icon: str

    @classmethod
    def from_definition(cls, a: AchievementDefinition) -> "AchievementResponse":
        return cls(
            id=a.id,
            name=a.name,
            description=a.description,
            category=a.category,
            icon=a.icon,
        )


class UserAchievementResponse(AchievementResponse):
    """Logro con el estado de desbloqueo del usuario."""

    unlocked: bool
    obtained_at: datetime | None

    @classmethod
    def from_definition_state(
        cls, a: AchievementDefinition, obtained_at: datetime | None
    ) -> "UserAchievementResponse":
        return cls(
            id=a.id,
            name=a.name,
            description=a.description,
            category=a.category,
            icon=a.icon,
            unlocked=obtained_at is not None,
            obtained_at=obtained_at,
        )


class AchievementsMeResponse(BaseModel):
    """Logros del usuario: desbloqueados y pendientes."""

    unlocked_count: int
    total: int
    achievements: list[UserAchievementResponse]
