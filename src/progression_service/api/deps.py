"""Inyección de dependencias: cablea repositorios y servicios sobre la conexión Mongo."""

from typing import Annotated

from fastapi import Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from progression_service.application.services.progression_service import ProgressionService
from progression_service.application.services.ranking_service import RankingService
from progression_service.application.services.statistics_service import StatisticsService
from progression_service.infrastructure.repositories.mongo_bet_repository import (
    MongoBetRepository,
)
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


def get_statistics_service(db: DbDep) -> StatisticsService:
    return StatisticsService(
        MongoBetRepository(db),
        MongoStatisticsRepository(db),
        MongoUserRepository(db),
    )


def get_progression_service(db: DbDep) -> ProgressionService:
    return ProgressionService(
        get_statistics_service(db),
        MongoProgressionRepository(db),
        MongoUserRepository(db),
        MongoBetRepository(db),
    )


def get_ranking_service(db: DbDep) -> RankingService:
    return RankingService(MongoStatisticsRepository(db))
