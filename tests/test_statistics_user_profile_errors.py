"""Del error del contrato TCP al código HTTP que ve el cliente del gateway.

El cliente TCP traduce el contrato a excepciones de dominio (ver
``test_tcp_user_profile_client.py``); aquí se comprueba el otro extremo de la cadena: que
esas excepciones salen por la API con el código correcto y **sin propagar una excepción no
controlada**. El gateway hace proxy conservando el status
(``api-gateway/src/proxy/proxy.controller.ts:99``), así que este es el código que recibe el
frontend.

Antes de este cambio, ``GET /statistics/{user_id}`` respondía 200 para cualquier id —
incluso uno inexistente— con el ``username`` vacío, porque el perfil se buscaba en la
colección ``users`` de la Mongo de este servicio, que en el despliegue real no existe.
"""

import httpx
from httpx import ASGITransport

from progression_service.api.deps import get_statistics_service
from progression_service.application.services.statistics_service import StatisticsService
from progression_service.core.exceptions import (
    InvalidArgumentError,
    NotFoundError,
    UserProfileUnavailableError,
)
from progression_service.domain.entities.bet import Bet, BetStatus, BetType
from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.entities.user_profile import UserProfile
from progression_service.domain.repositories.bet_repository import BetRepository
from progression_service.domain.repositories.statistics_repository import StatisticsRepository
from progression_service.domain.repositories.user_profile_provider import UserProfileProvider
from progression_service.main import create_app
from tests.conftest import USER_ID, utc


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


class _InMemoryStats(StatisticsRepository):
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


class _FailingProfiles(UserProfileProvider):
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def get_profile(self, user_id: str) -> UserProfile:
        raise self._error


class _OkProfiles(UserProfileProvider):
    async def get_profile(self, user_id: str) -> UserProfile:
        return UserProfile(id=user_id, username="olivier", created_at=utc(2026, 1, 15))


def _client(profiles: UserProfileProvider, stats: _InMemoryStats) -> httpx.AsyncClient:
    app = create_app()
    app.dependency_overrides[get_statistics_service] = lambda: StatisticsService(
        _OneBet(), stats, profiles
    )
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_existing_user_gets_the_username_from_the_contract():
    stats = _InMemoryStats()
    async with _client(_OkProfiles(), stats) as c:
        r = await c.get(f"/statistics/{USER_ID}")

    assert r.status_code == 200
    assert r.json()["username"] == "olivier"


async def test_unknown_user_is_404_not_an_empty_row():
    stats = _InMemoryStats()
    async with _client(_FailingProfiles(NotFoundError("Usuario no encontrado.")), stats) as c:
        r = await c.get(f"/statistics/{USER_ID}")

    assert r.status_code == 404
    # Y no se materializa una fila fantasma en el ranking.
    assert stats.upserts == []


async def test_malformed_user_id_is_400():
    stats = _InMemoryStats()
    async with _client(_FailingProfiles(InvalidArgumentError("user_id inválido.")), stats) as c:
        r = await c.get("/statistics/no-es-un-objectid")

    assert r.status_code == 400


async def test_users_service_down_is_503_not_500():
    stats = _InMemoryStats()
    error = UserProfileUnavailableError("users-service no responde.")
    async with _client(_FailingProfiles(error), stats) as c:
        r = await c.get(f"/statistics/{USER_ID}")

    assert r.status_code == 503
    assert stats.upserts == []
