"""Inyección de dependencias: cablea repositorios y servicios.

Las proyecciones (estadísticas, progresión) viven en la Mongo de este servicio; las
apuestas, no: se leen de bets-service por HTTP, así que el repositorio de apuestas se
construye sobre el cliente compartido que crea el lifespan.
"""

import secrets
from typing import Annotated

import httpx
from fastapi import Depends, Header, Request
from pymongo.asynchronous.database import AsyncDatabase

from progression_service.application.services.progression_service import ProgressionService
from progression_service.application.services.ranking_service import RankingService
from progression_service.application.services.statistics_service import StatisticsService
from progression_service.core.config import get_settings
from progression_service.core.exceptions import (
    BetSourceUnavailableError,
    InvalidCredentialsError,
)
from progression_service.domain.repositories.bet_repository import BetRepository
from progression_service.infrastructure.http.http_bet_repository import HttpBetRepository
from progression_service.infrastructure.repositories.mongo_progression_repository import (
    MongoProgressionRepository,
)
from progression_service.infrastructure.repositories.mongo_statistics_repository import (
    MongoStatisticsRepository,
)
from progression_service.infrastructure.repositories.mongo_user_repository import (
    MongoUserRepository,
)


def get_database(request: Request) -> AsyncDatabase:
    """Devuelve la base de datos creada en el lifespan de la app."""

    return request.app.state.db


DbDep = Annotated[AsyncDatabase, Depends(get_database)]


async def require_internal_key(
    x_internal_key: Annotated[str | None, Header()] = None,
) -> None:
    """Exige el secreto de servicio en las rutas ``/internal/*``.

    Las rutas de lectura (``/statistics``, ``/ranking``, …) son proyecciones que sirve el
    gateway a un usuario autenticado; ``/internal/recalculate`` en cambio dispara trabajo y
    solo la debe invocar otro servicio.

    ``compare_digest`` evita filtrar el secreto por el tiempo que tarda la comparación.
    """

    expected = get_settings().internal_api_key
    if x_internal_key is None or not secrets.compare_digest(x_internal_key, expected):
        raise InvalidCredentialsError("Secreto de servicio inválido o ausente.")


def get_bets_client(request: Request) -> httpx.AsyncClient:
    """Cliente HTTP compartido hacia bets-service, creado en el lifespan."""

    client = getattr(request.app.state, "bets_client", None)
    if client is None:
        # Sólo puede pasar si la app se construye sin ejecutar el lifespan. Mejor un error
        # de dominio traducido a 503 que un AttributeError opaco.
        raise BetSourceUnavailableError("El cliente de bets-service no está inicializado.")
    return client


def get_bet_repository(
    client: Annotated[httpx.AsyncClient, Depends(get_bets_client)],
) -> BetRepository:
    return HttpBetRepository(client, page_size=get_settings().bets_page_size)


BetRepoDep = Annotated[BetRepository, Depends(get_bet_repository)]


def get_statistics_service(db: DbDep, bets: BetRepoDep) -> StatisticsService:
    return StatisticsService(
        bets,
        MongoStatisticsRepository(db),
        MongoUserRepository(db),
    )


def get_progression_service(
    db: DbDep,
    bets: BetRepoDep,
    statistics: Annotated[StatisticsService, Depends(get_statistics_service)],
) -> ProgressionService:
    # `statistics` se pide por Depends (en vez de construirlo aquí) para que FastAPI
    # reutilice la misma instancia dentro de la petición: así el repositorio de apuestas
    # se crea una sola vez, no dos.
    return ProgressionService(
        statistics,
        MongoProgressionRepository(db),
        MongoUserRepository(db),
        bets,
    )


def get_ranking_service(db: DbDep) -> RankingService:
    return RankingService(MongoStatisticsRepository(db))


def build_progression_service(
    db: AsyncDatabase, bets_client: httpx.AsyncClient
) -> ProgressionService:
    """Construye el servicio fuera del scope de una petición HTTP.

    El consumer de RabbitMQ (T-026) no pasa por el sistema de ``Depends`` de FastAPI, pero
    necesita exactamente el mismo grafo de objetos que :func:`get_progression_service`. Se
    le pasan la base y el cliente HTTP que crea el lifespan, que son seguros de compartir
    entre tareas concurrentes.
    """

    bets = HttpBetRepository(bets_client, page_size=get_settings().bets_page_size)
    return ProgressionService(
        StatisticsService(bets, MongoStatisticsRepository(db), MongoUserRepository(db)),
        MongoProgressionRepository(db),
        MongoUserRepository(db),
        bets,
    )
