"""Entidad de dominio ``RankDefinition``. Value object puro."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RankDefinition:
    """Un rango del sistema de progresión.

    ``min_score`` es la puntuación (0..100) mínima para alcanzar el rango; el
    rango efectivo del usuario es el de mayor ``level`` cuyo umbral no supera su
    puntuación de rango.
    """

    level: int
    name: str
    icon: str
    min_score: float
