"""Caso de uso de progresión: rango y logros del usuario.

Encadena el recálculo de estadísticas (reutilizado) con la evaluación de rango y
logros. Implementa el puerto ``StatisticsSynchronizer``, por lo que puede
inyectarse en ``BetService`` para mantener todo sincronizado tras cada apuesta.
"""

from datetime import datetime, timezone

from progression_service.application.services.statistics_service import StatisticsService
from progression_service.domain.entities.progression import UserProgression
from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.repositories.bet_repository import BetRepository
from progression_service.domain.repositories.progression_repository import ProgressionRepository
from progression_service.domain.repositories.user_repository import UserRepository
from progression_service.domain.services import achievement_evaluator, rank_evaluator
from progression_service.domain.services.rank_scorer import compute_rank_score


class ProgressionService:
    """Evalúa y persiste el rango y los logros de cada usuario."""

    def __init__(
        self,
        statistics_service: StatisticsService,
        progression_repository: ProgressionRepository,
        user_repository: UserRepository,
        bet_repository: BetRepository,
    ) -> None:
        self._stats_service = statistics_service
        self._progression = progression_repository
        self._users = user_repository
        self._bets = bet_repository

    async def recalculate(self, user_id: str) -> UserProgression:
        """Recalcula stats y reevalúa rango + logros del usuario (idempotente)."""

        stats = await self._stats_service.recalculate(user_id)
        return await self._evaluate(user_id, stats)

    async def get_or_recalculate(self, user_id: str) -> UserProgression:
        """Devuelve la progresión almacenada; si no existe, la calcula."""

        stored = await self._progression.get_by_user_id(user_id)
        if stored is not None:
            return stored
        stats = await self._stats_service.get_or_recalculate(user_id)
        return await self._evaluate(user_id, stats)

    async def recalculate_all(self) -> int:
        """Recalcula stats + progresión de todos los usuarios con apuestas."""

        user_ids = await self._bets.distinct_user_ids()
        for user_id in user_ids:
            await self.recalculate(user_id)
        return len(user_ids)

    async def _evaluate(self, user_id: str, stats: UserStatistics) -> UserProgression:
        now = datetime.now(timezone.utc)
        user = await self._users.get_by_id(user_id)
        account_age_days = (now - user.created_at).days if user else 0

        progression = await self._progression.get_by_user_id(user_id) or UserProgression(
            user_id=user_id
        )

        # --- Rango ---
        score = compute_rank_score(stats, account_age_days)
        current, _next, _progress = rank_evaluator.rank_progress(score)
        progression.rank_score = score
        if progression.rank_level != current.level:
            progression.rank_updated_at = now
        progression.rank_level = current.level
        progression.rank_name = current.name
        progression.rank_icon = current.icon

        # --- Logros (solo se evalúan los aún bloqueados; no se duplican) ---
        newly = achievement_evaluator.evaluate(stats, now, progression.unlocked.keys())
        for achievement_id in newly:
            progression.unlocked[achievement_id] = now

        progression.updated_at = now
        await self._progression.upsert(progression)
        return progression
