"""Entidades de dominio para logros (achievements). Value objects puros."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from progression_service.domain.entities.statistics import UserStatistics

#: Predicado de desbloqueo: recibe las estadísticas del usuario y el instante
#: actual, y devuelve ``True`` si el logro se cumple.
UnlockCondition = Callable[[UserStatistics, datetime], bool]


class AchievementCategory(str, Enum):
    """Categorías de logros."""

    STREAKS = "STREAKS"
    EXPERIENCE = "EXPERIENCE"
    PROFITABILITY = "PROFITABILITY"
    PRECISION = "PRECISION"
    ACTIVITY = "ACTIVITY"
    BOOKMAKERS = "BOOKMAKERS"
    SPORTS = "SPORTS"


@dataclass(frozen=True)
class AchievementDefinition:
    """Definición de un logro del catálogo.

    Añadir un logro nuevo es tan simple como registrar otra instancia en el
    catálogo; el evaluador no necesita cambios.
    """

    id: str
    name: str
    description: str
    category: AchievementCategory
    icon: str
    condition: UnlockCondition
