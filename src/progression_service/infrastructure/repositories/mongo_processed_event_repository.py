"""Implementación MongoDB del repositorio de eventos procesados."""

from datetime import datetime, timezone

from pymongo.asynchronous.database import AsyncDatabase

from progression_service.domain.repositories.processed_event_repository import (
    ProcessedEventRepository,
)


class MongoProcessedEventRepository(ProcessedEventRepository):
    """Persiste las claves en ``processed_bet_events``, con ``event_key`` como ``_id``."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._collection = db["processed_bet_events"]

    async def is_processed(self, event_key: str) -> bool:
        doc = await self._collection.find_one({"_id": event_key})
        return doc is not None

    async def mark_processed(self, event_key: str) -> None:
        # upsert + $setOnInsert: marcar la misma clave dos veces (carrera entre entregas
        # concurrentes) no debe fallar, sólo confirmar que ya estaba.
        await self._collection.update_one(
            {"_id": event_key},
            {"$setOnInsert": {"processed_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
