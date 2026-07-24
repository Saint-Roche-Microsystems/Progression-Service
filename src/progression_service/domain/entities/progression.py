"""Entidad de dominio ``UserProgression``. Estado de gamificación por usuario."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class UserProgression:
    """Rango y logros desbloqueados de un usuario (materializado)."""

    user_id: str

    # Rango actual
    rank_level: int = 0
    rank_name: str = ""
    rank_icon: str = ""
    rank_score: float = 0.0
    rank_updated_at: datetime | None = None

    # Logros desbloqueados: id -> fecha de obtención (nunca se duplican).
    unlocked: dict[str, datetime] = field(default_factory=dict)

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
