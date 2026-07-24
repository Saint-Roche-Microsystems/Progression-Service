"""Implementación MongoDB del repositorio de usuarios."""

from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.database import AsyncDatabase

from progression_service.core.exceptions import AlreadyExistsError
from progression_service.domain.entities.user import Role, User
from progression_service.domain.repositories.user_repository import UserRepository
from pymongo.errors import DuplicateKeyError


def _to_entity(doc: dict[str, Any]) -> User:
    return User(
        id=str(doc["_id"]),
        username=doc["username"],
        email=doc["email"],
        hashed_password=doc["hashed_password"],
        role=Role(doc["role"]),
        active=doc.get("active", True),
        created_at=doc["created_at"],
        failed_login_attempts=doc.get("failed_login_attempts", 0),
        locked_until=doc.get("locked_until"),
    )


class MongoUserRepository(UserRepository):
    """Persiste usuarios en la colección ``users``."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._collection = db["users"]

    async def create(self, user: User) -> User:
        doc = {
            "username": user.username,
            "email": user.email,
            "hashed_password": user.hashed_password,
            "role": user.role.value,
            "active": user.active,
            "created_at": user.created_at,
            "failed_login_attempts": user.failed_login_attempts,
            "locked_until": user.locked_until,
        }
        try:
            result = await self._collection.insert_one(doc)
        except DuplicateKeyError as exc:  # respaldo si falla el índice único
            raise AlreadyExistsError("El correo o el nombre de usuario ya existe.") from exc
        user.id = str(result.inserted_id)
        return user

    async def get_by_id(self, user_id: str) -> User | None:
        try:
            oid = ObjectId(user_id)
        except InvalidId, TypeError:
            return None
        doc = await self._collection.find_one({"_id": oid})
        return _to_entity(doc) if doc else None

    async def get_by_email(self, email: str) -> User | None:
        doc = await self._collection.find_one({"email": email})
        return _to_entity(doc) if doc else None

    async def get_by_username(self, username: str) -> User | None:
        doc = await self._collection.find_one({"username": username})
        return _to_entity(doc) if doc else None

    async def list(self, *, skip: int = 0, limit: int = 20) -> tuple[list[User], int]:
        total = await self._collection.count_documents({})
        cursor = self._collection.find({}).sort("created_at", 1).skip(skip).limit(limit)
        items = [_to_entity(doc) async for doc in cursor]
        return items, total

    async def set_active(self, user_id: str, active: bool) -> bool:
        try:
            oid = ObjectId(user_id)
        except InvalidId, TypeError:
            return False
        result = await self._collection.update_one({"_id": oid}, {"$set": {"active": active}})
        return result.matched_count > 0

    async def record_login_failure(
        self, user_id: str, attempts: int, locked_until: datetime | None
    ) -> None:
        try:
            oid = ObjectId(user_id)
        except InvalidId, TypeError:
            return
        await self._collection.update_one(
            {"_id": oid},
            {"$set": {"failed_login_attempts": attempts, "locked_until": locked_until}},
        )

    async def reset_login_failures(self, user_id: str) -> None:
        try:
            oid = ObjectId(user_id)
        except InvalidId, TypeError:
            return
        await self._collection.update_one(
            {"_id": oid},
            {"$set": {"failed_login_attempts": 0, "locked_until": None}},
        )
