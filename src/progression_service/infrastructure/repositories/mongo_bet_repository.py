"""Implementación MongoDB del repositorio de apuestas."""

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.database import AsyncDatabase

from progression_service.domain.entities.bet import Bet, BetLeg, BetStatus, BetType
from progression_service.domain.repositories.bet_repository import BetRepository


def _leg_to_entity(doc: dict[str, Any]) -> BetLeg:
    return BetLeg(
        sport=doc["sport"],
        league=doc["league"],
        event=doc["event"],
        market=doc["market"],
        selection=doc["selection"],
        odds=doc["odds"],
    )


def _to_entity(doc: dict[str, Any]) -> Bet:
    return Bet(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        sport=doc["sport"],
        league=doc["league"],
        event=doc["event"],
        bet_type=BetType(doc["bet_type"]),
        market=doc["market"],
        selection=doc["selection"],
        odds=doc["odds"],
        stake=doc["stake"],
        bookmaker=doc["bookmaker"],
        event_datetime=doc["event_datetime"],
        status=BetStatus(doc["status"]),
        notes=doc.get("notes"),
        reference_id=doc.get("reference_id"),
        legs=[_leg_to_entity(leg) for leg in doc.get("legs", [])],
        combined_odds=doc.get("combined_odds", doc["odds"]),
        potential_return=doc["potential_return"],
        potential_profit=doc["potential_profit"],
        implied_probability=doc["implied_probability"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _to_document(bet: Bet) -> dict[str, Any]:
    return {
        "user_id": bet.user_id,
        "sport": bet.sport,
        "league": bet.league,
        "event": bet.event,
        "bet_type": bet.bet_type.value,
        "market": bet.market,
        "selection": bet.selection,
        "odds": bet.odds,
        "stake": bet.stake,
        "bookmaker": bet.bookmaker,
        "event_datetime": bet.event_datetime,
        "status": bet.status.value,
        "notes": bet.notes,
        "reference_id": bet.reference_id,
        "legs": [vars(leg) for leg in bet.legs],
        "combined_odds": bet.combined_odds,
        "potential_return": bet.potential_return,
        "potential_profit": bet.potential_profit,
        "implied_probability": bet.implied_probability,
        "created_at": bet.created_at,
        "updated_at": bet.updated_at,
    }


class MongoBetRepository(BetRepository):
    """Persiste apuestas en la colección ``bets``."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._collection = db["bets"]

    async def create(self, bet: Bet) -> Bet:
        result = await self._collection.insert_one(_to_document(bet))
        bet.id = str(result.inserted_id)
        return bet

    async def get_by_id(self, bet_id: str) -> Bet | None:
        try:
            oid = ObjectId(bet_id)
        except InvalidId, TypeError:
            return None
        doc = await self._collection.find_one({"_id": oid})
        return _to_entity(doc) if doc else None

    async def list_by_user(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 20,
        status: BetStatus | None = None,
        sport: str | None = None,
        bet_type: BetType | None = None,
    ) -> tuple[list[Bet], int]:
        query: dict[str, Any] = {"user_id": user_id}
        if status is not None:
            query["status"] = status.value
        if sport is not None:
            query["sport"] = sport
        if bet_type is not None:
            query["bet_type"] = bet_type.value

        total = await self._collection.count_documents(query)
        cursor = self._collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        items = [_to_entity(doc) async for doc in cursor]
        return items, total

    async def update(self, bet: Bet) -> Bet:
        assert bet.id is not None
        await self._collection.update_one(
            {"_id": ObjectId(bet.id)},
            {"$set": _to_document(bet)},
        )
        return bet

    async def delete(self, bet_id: str) -> bool:
        try:
            oid = ObjectId(bet_id)
        except InvalidId, TypeError:
            return False
        result = await self._collection.delete_one({"_id": oid})
        return result.deleted_count > 0

    async def distinct_user_ids(self) -> list[str]:
        return await self._collection.distinct("user_id")

    async def reference_exists(self, user_id: str, reference_id: str) -> bool:
        doc = await self._collection.find_one(
            {"user_id": user_id, "reference_id": reference_id},
            projection={"_id": 1},
        )
        return doc is not None
