"""Interfaz abstracta del repositorio de apuestas."""

from abc import ABC, abstractmethod

from progression_service.domain.entities.bet import Bet, BetStatus, BetType


class BetRepository(ABC):
    """Contrato de persistencia para :class:`Bet`."""

    @abstractmethod
    async def create(self, bet: Bet) -> Bet:
        """Persiste una nueva apuesta y devuelve la entidad con su ``id``."""

    @abstractmethod
    async def get_by_id(self, bet_id: str) -> Bet | None:
        """Devuelve la apuesta con el id dado, o ``None``."""

    @abstractmethod
    async def list_by_user(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 20,
        status: BetStatus | None = None,
        sport: str | None = None,
        bet_type: BetType | None = None,
    ) -> tuple[list[Bet], int]:
        """Lista las apuestas de un usuario con filtros y paginación.

        Devuelve una tupla ``(items, total)`` donde ``total`` es el número de
        documentos que cumplen el filtro (sin paginar).
        """

    @abstractmethod
    async def update(self, bet: Bet) -> Bet:
        """Actualiza una apuesta existente y devuelve la entidad actualizada."""

    @abstractmethod
    async def delete(self, bet_id: str) -> bool:
        """Elimina la apuesta. Devuelve ``True`` si se eliminó algún documento."""

    @abstractmethod
    async def distinct_user_ids(self) -> list[str]:
        """Devuelve los ``user_id`` distintos que tienen al menos una apuesta.

        Se usa para el backfill de estadísticas al arrancar.
        """

    @abstractmethod
    async def reference_exists(self, user_id: str, reference_id: str) -> bool:
        """Indica si el usuario ya tiene una apuesta con ese ``reference_id``."""
