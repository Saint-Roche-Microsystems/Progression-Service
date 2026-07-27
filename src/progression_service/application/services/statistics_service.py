"""Casos de uso de estadísticas: cálculo, materialización y sincronización."""

import logging

from progression_service.core.exceptions import NotFoundError
from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.repositories.bet_repository import BetRepository
from progression_service.domain.repositories.statistics_repository import StatisticsRepository
from progression_service.domain.repositories.user_profile_provider import UserProfileProvider
from progression_service.domain.services.ranking_scorer import compute_ranking_score
from progression_service.domain.services.statistics_calculator import compute_statistics

logger = logging.getLogger(__name__)


class StatisticsService:
    """Orquesta el cálculo y almacenamiento de las estadísticas de un usuario.

    Implementa el puerto ``StatisticsSynchronizer`` (método :meth:`recalculate`).
    """

    def __init__(
        self,
        bet_repository: BetRepository,
        statistics_repository: StatisticsRepository,
        user_profiles: UserProfileProvider,
    ) -> None:
        self._bets = bet_repository
        self._stats = statistics_repository
        self._users = user_profiles

    async def recalculate(self, user_id: str) -> UserStatistics:
        """Recalcula las estadísticas del usuario desde sus apuestas y las persiste.

        Las apuestas se leen de bets-service (su dueño). Si esa lectura falla, el puerto
        lanza ``BetSourceUnavailableError`` y el ``upsert`` de abajo no llega a ejecutarse:
        es intencionado, porque persistir el resultado de un historial vacío borraría las
        estadísticas buenas del usuario.

        El perfil se resuelve contra users-service (contrato TCP ``users.profile``), que es
        su dueño. Si el usuario no existe, el error sube: recalcular la proyección de un
        usuario que no existe sólo puede crear una fila fantasma en el ranking.
        """

        profile = await self._users.get_profile(user_id)
        username = profile.username

        bets = await self._bets.list_all_by_user(user_id)
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

        Un usuario del historial de apuestas que ya no existe en users-service (cuenta
        borrada) se salta con un log en vez de abortar el backfill entero: aquí no hay
        nadie a quien devolverle un 404, y el resto de usuarios sí se puede recalcular.
        """

        user_ids = await self._bets.distinct_user_ids()
        processed = 0
        for user_id in user_ids:
            try:
                await self.recalculate(user_id)
            except NotFoundError:
                logger.warning(
                    "Backfill: usuario sin perfil en users-service, se omite.",
                    extra={"user_id": user_id},
                )
                continue
            processed += 1
        return processed
