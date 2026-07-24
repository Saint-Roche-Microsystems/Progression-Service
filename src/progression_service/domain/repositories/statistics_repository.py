"""Interfaz abstracta del repositorio de estadísticas de usuario."""

from abc import ABC, abstractmethod

from progression_service.domain.entities.statistics import UserStatistics


class StatisticsRepository(ABC):
    """Contrato de persistencia para las estadísticas materializadas por usuario."""

    @abstractmethod
    async def upsert(self, stats: UserStatistics) -> None:
        """Crea o reemplaza las estadísticas de un usuario (clave: ``user_id``)."""

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> UserStatistics | None:
        """Devuelve las estadísticas del usuario, o ``None`` si no existen."""

    @abstractmethod
    async def list_ranked(
        self, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[UserStatistics], int]:
        """Devuelve ``(items, total)`` ordenados por ``ranking_score`` descendente."""

    @abstractmethod
    async def get_position(self, user_id: str) -> int | None:
        """Posición (1-indexada) del usuario en el ranking, o ``None`` si no existe.

        Se define como ``1 + nº de usuarios con mayor ``ranking_score``.
        """
