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
from progression_service.domain.repositories.user_repository import UserRepository
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


class _NoUsers(UserRepository):
    """El perfil vive en users-service; aquí siempre falta y el cálculo lo tolera."""

    async def create(self, user):  # pragma: no cover - sin llamadores
        raise NotImplementedError

    async def get_by_id(self, user_id: str):
        return None

    async def get_by_email(self, email: str):  # pragma: no cover - sin llamadores
        return None

    async def get_by_username(self, username: str):  # pragma: no cover - sin llamadores
        return None

    async def list(self, *args, **kwargs):  # pragma: no cover - sin llamadores
        return [], 0

    async def set_active(self, user_id: str, active: bool):  # pragma: no cover
        raise NotImplementedError

    async def record_login_failure(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def reset_login_failures(self, user_id: str):  # pragma: no cover
        raise NotImplementedError


async def test_recalculate_does_not_persist_when_bets_are_unreachable():
    stats = _RecordingStats()
    service = StatisticsService(_UnavailableBets(), stats, _NoUsers())

    with pytest.raises(BetSourceUnavailableError):
        await service.recalculate(USER_ID)

    assert stats.upserts == []


async def test_recalculate_persists_when_bets_are_readable():
    """Contraprueba: con la fuente disponible sí se materializa el resultado."""

    stats = _RecordingStats()
    service = StatisticsService(_OneBet(), stats, _NoUsers())

    result = await service.recalculate(USER_ID)

    assert len(stats.upserts) == 1
    assert result.total_bets == 1
    assert result.won == 1
