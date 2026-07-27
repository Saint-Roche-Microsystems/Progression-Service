"""Implementación de :class:`UserProfileProvider` sobre la Mongo local.

Es el modo de desarrollo, equivalente al ``AlwaysValidUserValidator`` de bets-service:
sirve para levantar el servicio sin users-service delante. **No debe desplegarse así**,
porque la colección ``users`` de la base de este servicio es un resto del monolito y en el
despliegue real está vacía: por eso el ranking mostraba nombres en blanco.

Se apoya en el :class:`MongoUserRepository` que ya existía en lugar de volver a consultar
la colección, para que siga habiendo un único sitio que sepa cómo se lee un usuario de esa
base.
"""

from progression_service.core.exceptions import NotFoundError
from progression_service.domain.entities.user_profile import UserProfile
from progression_service.domain.repositories.user_profile_provider import (
    UserProfileProvider,
)
from progression_service.domain.repositories.user_repository import UserRepository


class MongoUserProfileProvider(UserProfileProvider):
    """Adapta el repositorio de usuarios heredado al puerto de perfil."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def get_profile(self, user_id: str) -> UserProfile:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.")
        return UserProfile(
            id=str(user.id),
            username=user.username,
            role=user.role.value,
            active=user.active,
            created_at=user.created_at,
        )
