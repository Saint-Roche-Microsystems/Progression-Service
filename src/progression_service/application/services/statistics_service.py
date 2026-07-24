"""Casos de uso de estadísticas: cálculo, materialización y sincronización."""

from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.repositories.bet_repository import BetRepository
from progression_service.domain.repositories.statistics_repository import StatisticsRepository
from progression_service.domain.repositories.user_repository import UserRepository
from progression_service.domain.services.ranking_scorer import compute_ranking_score
from progression_service.domain.services.statistics_calculator import compute_statistics


class StatisticsService:
    """Orquesta el cálculo y almacenamiento de las estadísticas de un usuario.

    Implementa el puerto ``StatisticsSynchronizer`` (método :meth:`recalculate`).
    """

    def __init__(
        self,
        bet_repository: BetRepository,
        statistics_repository: StatisticsRepository,
        user_repository: UserRepository,
    ) -> None:
        self._bets = bet_repository
        self._stats = statistics_repository
        self._users = user_repository

    async def recalculate(self, user_id: str) -> UserStatistics:
        """Recalcula las estadísticas del usuario desde sus apuestas y las persiste."""

        user = await self._users.get_by_id(user_id)
        username = user.username if user else ""

        bets, _ = await self._bets.list_by_user(user_id, skip=0, limit=1_000_000)
        stats = compute_statistics(user_id, bets, username=username)
        stats.ranking_score = compute_ranking_score(stats)

        await self._stats.upsert(stats)
        return stats

    async def get_or_recalculate(self, user_id: str) -> UserStatistics:
        """Devuelve las estadísticas almacenadas; si no existen, las calcula."""

        stored = await self._stats.get_by_user_id(user_id)
        if stored is not None:
            return stored
        return await self.recalculate(user_id)

    async def recalculate_all(self) -> int:
        """Recalcula las estadísticas de todos los usuarios con apuestas (backfill).

        Devuelve el número de usuarios procesados. Es idempotente.
        """

        user_ids = await self._bets.distinct_user_ids()
        for user_id in user_ids:
            await self.recalculate(user_id)
        return len(user_ids)
