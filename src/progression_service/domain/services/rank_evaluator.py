"""Servicio de dominio PURO: resolución de rango y progreso al siguiente."""

from progression_service.domain.entities.rank import RankDefinition
from progression_service.domain.services.ranks_config import RANKS


def resolve_rank(score: float) -> RankDefinition:
    """Devuelve el rango correspondiente a una puntuación de rango.

    Es el rango de mayor nivel cuyo ``min_score`` no supera la puntuación.
    """

    current = RANKS[0]
    for rank in RANKS:
        if score >= rank.min_score:
            current = rank
        else:
            break
    return current


def next_rank(current: RankDefinition) -> RankDefinition | None:
    """Devuelve el siguiente rango, o ``None`` si ya es el máximo."""

    idx = current.level  # level es 1-indexado; el siguiente está en RANKS[level]
    return RANKS[idx] if idx < len(RANKS) else None


def rank_progress(score: float) -> tuple[RankDefinition, RankDefinition | None, float]:
    """Devuelve ``(rango_actual, rango_siguiente|None, progreso_%)``.

    El progreso es el avance (0..100) desde el umbral del rango actual hacia el
    del siguiente. En el rango máximo devuelve 100.
    """

    current = resolve_rank(score)
    nxt = next_rank(current)
    if nxt is None:
        return current, None, 100.0

    span = nxt.min_score - current.min_score
    progress = (score - current.min_score) / span * 100 if span > 0 else 100.0
    return current, nxt, round(max(0.0, min(100.0, progress)), 2)
