"""Entidad de dominio ``User``. Pura: sin dependencias de Mongo ni Pydantic."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Role(str, Enum):
    """Roles de usuario del sistema."""

    USER = "USER"
    ADMIN = "ADMIN"


@dataclass
class User:
    """Usuario del sistema."""

    username: str
    email: str
    hashed_password: str
    role: Role = Role.USER
    active: bool = True
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
