"""Interfaz abstracta del repositorio de usuarios."""

from abc import ABC, abstractmethod
from datetime import datetime

from progression_service.domain.entities.user import User


class UserRepository(ABC):
    """Contrato de persistencia para :class:`User`.

    La capa de aplicación depende de esta abstracción, no de la implementación
    concreta de MongoDB.
    """

    @abstractmethod
    async def create(self, user: User) -> User:
        """Persiste un nuevo usuario y devuelve la entidad con su ``id``."""

    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None:
        """Devuelve el usuario con el id dado, o ``None``."""

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Devuelve el usuario con el email dado, o ``None``."""

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None:
        """Devuelve el usuario con el username dado, o ``None``."""

    @abstractmethod
    async def list(self, *, skip: int = 0, limit: int = 20) -> tuple[list[User], int]:
        """Lista usuarios paginados. Devuelve ``(items, total)``."""

    @abstractmethod
    async def set_active(self, user_id: str, active: bool) -> bool:
        """Activa/desactiva un usuario. Devuelve ``True`` si se actualizó."""

    @abstractmethod
    async def record_login_failure(
        self, user_id: str, attempts: int, locked_until: datetime | None
    ) -> None:
        """Guarda el nuevo contador de intentos fallidos y, si aplica, el bloqueo."""

    @abstractmethod
    async def reset_login_failures(self, user_id: str) -> None:
        """Limpia el contador de intentos fallidos y el bloqueo tras un login exitoso."""
