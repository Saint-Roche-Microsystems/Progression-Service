"""Implementación MongoDB del repositorio de progresión."""

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from progression_service.domain.entities.progression import UserProgression
from progression_service.domain.repositories.progression_repository import ProgressionRepository

_FIELDS = (
    "rank_level",
    "rank_name",
    "rank_icon",
    "rank_score",
    "rank_updated_at",
    "unlocked",
    "updated_at",
)


def _to_entity(doc: dict[str, Any]) -> UserProgression:
    known = {f: doc[f] for f in _FIELDS if f in doc}
    return UserProgression(user_id=doc["user_id"], **known)


def _to_document(progression: UserProgression) -> dict[str, Any]:
    doc = {f: getattr(progression, f) for f in _FIELDS}
    doc["user_id"] = progression.user_id
    return doc


class MongoProgressionRepository(ProgressionRepository):
    """Persiste la progresión en la colección ``user_progression``."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._collection = db["user_progression"]

    async def get_by_user_id(self, user_id: str) -> UserProgression | None:
        doc = await self._collection.find_one({"user_id": user_id})
        return _to_entity(doc) if doc else None

    async def upsert(self, progression: UserProgression) -> None:
        await self._collection.replace_one(
            {"user_id": progression.user_id},
            _to_document(progression),
            upsert=True,
        )
