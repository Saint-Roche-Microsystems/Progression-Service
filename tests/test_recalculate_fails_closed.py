"""El recálculo no debe persistir nada si no pudo leer las apuestas.

Es la razón de que el puerto de apuestas sea fail-closed: ``recalculate`` hace ``upsert``
de lo que calcule, así que tratar un fallo de red como "este usuario no tiene apuestas"
sobrescribiría sus estadísticas reales con ceros — y el dato perdido no se recupera solo,
porque la proyección es la única copia.
"""

import pytest

from progression_service.application.services.statistics_service import StatisticsService
from progression_service.core.exceptions import BetSourceUnavailableError
from progression_service.domain.entities.bet import Bet, BetStatus, BetType
from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.repositories.bet_repository import BetRepository
from progression_service.domain.repositories.statistics_repository import StatisticsRepository
from progression_service.domain.entities.user_profile import UserProfile
from progression_service.domain.repositories.user_profile_provider import UserProfileProvider
from tests.conftest import USER_ID, utc


class _UnavailableBets(BetRepository):
    async def list_all_by_user(self, user_id: str) -> list[Bet]:
        raise BetSourceUnavailableError("bets-service no responde.")

    async def distinct_user_ids(self) -> list[str]:
        raise BetSourceUnavailableError("bets-service no responde.")


class _OneBet(BetRepository):
    async def list_all_by_user(self, user_id: str) -> list[Bet]:
        bet = Bet(
            user_id=user_id,
            sport="Fútbol",
            league="LaLiga",
            event="A vs B",
            bet_type=BetType.SIMPLE,
            market="1X2",
            selection="A",
            odds=2.0,
            stake=10.0,
            bookmaker="Bet365",
            event_datetime=utc(2026, 8, 1),
            status=BetStatus.WON,
        )
        bet.recalculate()
        return [bet]

    async def distinct_user_ids(self) -> list[str]:
        return [USER_ID]


class _RecordingStats(StatisticsRepository):
    def __init__(self) -> None:
        self.upserts: list[UserStatistics] = []

    async def upsert(self, stats: UserStatistics) -> None:
        self.upserts.append(stats)

    async def get_by_user_id(self, user_id: str) -> UserStatistics | None:
        return None

    async def list_ranked(self, *, skip: int = 0, limit: int = 20):
        return [], 0

    async def get_position(self, user_id: str) -> int | None:
        return None


class _KnownUser(UserProfileProvider):
    """El perfil vive en users-service y llega por el contrato TCP `users.profile`."""

    async def get_profile(self, user_id: str) -> UserProfile:
        return UserProfile(id=user_id, username="olivier", created_at=utc(2026, 1, 15))


async def test_recalculate_does_not_persist_when_bets_are_unreachable():
    stats = _RecordingStats()
    service = StatisticsService(_UnavailableBets(), stats, _KnownUser())

    with pytest.raises(BetSourceUnavailableError):
        await service.recalculate(USER_ID)

    assert stats.upserts == []


async def test_recalculate_persists_when_bets_are_readable():
    """Contraprueba: con la fuente disponible sí se materializa el resultado."""

    stats = _RecordingStats()
    service = StatisticsService(_OneBet(), stats, _KnownUser())

    result = await service.recalculate(USER_ID)

    assert len(stats.upserts) == 1
    assert result.total_bets == 1
    assert result.won == 1
