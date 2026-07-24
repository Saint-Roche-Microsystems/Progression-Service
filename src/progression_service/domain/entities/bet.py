"""Entidad de dominio ``Bet`` y sus enums. Pura, sin dependencias externas."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class BetType(str, Enum):
    """Tipo de apuesta."""

    SIMPLE = "SIMPLE"
    PARLAY = "PARLAY"


class BetStatus(str, Enum):
    """Estado de la apuesta."""

    PENDING = "PENDING"
    WON = "WON"
    LOST = "LOST"
    VOID = "VOID"


@dataclass
class BetLeg:
    """Una selección de un parlay (además de la selección principal de la apuesta)."""

    sport: str
    league: str
    event: str
    market: str
    selection: str
    odds: float


@dataclass
class Bet:
    """Una apuesta deportiva perteneciente a un usuario.

    Los campos principales (``sport``, ``odds``, …) representan la **selección
    principal**. Un parlay añade selecciones extra en ``legs``; un simple lo deja
    vacío. Los campos calculados se derivan de ``stake`` y de la **cuota
    combinada** (producto de las cuotas) en :meth:`recalculate`.
    """

    # Propiedad
    user_id: str

    # Datos de la apuesta (selección principal)
    sport: str
    league: str
    event: str
    bet_type: BetType
    market: str
    selection: str
    odds: float
    stake: float
    bookmaker: str
    event_datetime: datetime
    status: BetStatus = BetStatus.PENDING
    notes: str | None = None
    reference_id: str | None = None

    # Selecciones adicionales del parlay (vacío en apuestas simples)
    legs: list[BetLeg] = field(default_factory=list)

    # Campos calculados
    combined_odds: float = 0.0
    potential_return: float = 0.0
    potential_profit: float = 0.0
    implied_probability: float = 0.0

    # Metadatos
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def recalculate(self) -> None:
        """Recalcula los campos derivados a partir de ``stake`` y la cuota combinada."""

        combined = self.odds
        for leg in self.legs:
            combined *= leg.odds

        self.combined_odds = round(combined, 4)
        self.potential_return = round(self.stake * combined, 4)
        self.potential_profit = round(self.stake * (combined - 1), 4)
        # Probabilidad implícita como fracción entre 0 y 1.
        self.implied_probability = round(1 / combined, 6)
