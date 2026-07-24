"""Implementación MongoDB del repositorio de estadísticas de usuario."""

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from progression_service.domain.entities.statistics import UserStatistics
from progression_service.domain.repositories.statistics_repository import StatisticsRepository

_FIELDS = (
    "username",
    "total_bets",
    "won",
    "lost",
    "void",
    "pending",
    "win_rate",
    "total_stake",
    "total_return",
    "net_profit",
    "roi",
    "avg_odds",
    "avg_stake",
    "biggest_win",
    "biggest_loss",
    "current_streak",
    "best_streak",
    "consistency",
    "distinct_sports",
    "distinct_bookmakers",
    "max_consecutive_days",
    "last_activity_at",
    "last_bet_at",
    "ranking_score",
    "updated_at",
)


def _to_entity(doc: dict[str, Any]) -> UserStatistics:
    # ``.get`` tolera documentos escritos antes de añadir campos nuevos; el
    # backfill de arranque los reescribe con los valores calculados.
    known = {f: doc[f] for f in _FIELDS if f in doc}
    return UserStatistics(user_id=doc["user_id"], **known)


def _to_document(stats: UserStatistics) -> dict[str, Any]:
    doc = {f: getattr(stats, f) for f in _FIELDS}
    doc["user_id"] = stats.user_id
    return doc


class MongoStatisticsRepository(StatisticsRepository):
    """Persiste estadísticas materializadas en la colección ``user_statistics``."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._collection = db["user_statistics"]

    async def upsert(self, stats: UserStatistics) -> None:
        await self._collection.replace_one(
            {"user_id": stats.user_id},
            _to_document(stats),
            upsert=True,
        )

    async def get_by_user_id(self, user_id: str) -> UserStatistics | None:
        doc = await self._collection.find_one({"user_id": user_id})
        return _to_entity(doc) if doc else None

    async def list_ranked(
        self, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[UserStatistics], int]:
        total = await self._collection.count_documents({})
        cursor = (
            self._collection.find({})
            .sort([("ranking_score", -1), ("net_profit", -1)])
            .skip(skip)
            .limit(limit)
        )
        items = [_to_entity(doc) async for doc in cursor]
        return items, total

    async def get_position(self, user_id: str) -> int | None:
        doc = await self._collection.find_one({"user_id": user_id})
        if doc is None:
            return None
        higher = await self._collection.count_documents(
            {"ranking_score": {"$gt": doc["ranking_score"]}}
        )
        return higher + 1
