"""Casos de uso del ranking global de usuarios."""

from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.repositories.statistics_repository import StatisticsRepository


class RankingService:
    """Lee las estadísticas materializadas y expone el ranking global."""

    def __init__(self, statistics_repository: StatisticsRepository) -> None:
        self._stats = statistics_repository

    async def get_ranking(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[UserStatistics], int, int]:
        """Devuelve ``(items, total, start_position)`` ordenados por puntuación.

        ``start_position`` es la posición (1-indexada) del primer elemento de la
        página, para numerar el ranking sin recalcular por fila.
        """

        skip = (page - 1) * page_size
        items, total = await self._stats.list_ranked(skip=skip, limit=page_size)
        return items, total, skip + 1

    async def get_top(self, limit: int = 10) -> list[UserStatistics]:
        """Devuelve el Top ``limit`` de usuarios (por defecto 10)."""

        items, _ = await self._stats.list_ranked(skip=0, limit=limit)
        return items

    async def get_user_position(self, user_id: str) -> tuple[int | None, UserStatistics | None]:
        """Devuelve ``(posición, estadísticas)`` del usuario en el ranking."""

        stats = await self._stats.get_by_user_id(user_id)
        if stats is None:
            return None, None
        position = await self._stats.get_position(user_id)
        return position, stats
