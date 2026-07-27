"""Puerto de lectura del perfil de un usuario.

Separado de :class:`~progression_service.domain.repositories.user_repository.UserRepository`
a propósito (segregación de interfaces): aquél es un repositorio de escritura completo
—``create``, ``set_active``, ``record_login_failure``…— heredado de cuando el monolito era
dueño de los usuarios. Este servicio ya no escribe usuarios: sólo necesita **leer** el
perfil de uno, y el dueño del dato es users-service. Un puerto de un solo método permite
implementarlo con el cliente TCP sin tener que dejar media docena de métodos lanzando
``NotImplementedError``.
"""

from abc import ABC, abstractmethod

from progression_service.domain.entities.user_profile import UserProfile


class UserProfileProvider(ABC):
    """Capacidad de resolver la identidad de un usuario contra su servicio dueño."""

    @abstractmethod
    async def get_profile(self, user_id: str) -> UserProfile:
        """Devuelve el perfil del usuario.

        Lanza :class:`~progression_service.core.exceptions.NotFoundError` si el usuario no
        existe, :class:`~progression_service.core.exceptions.InvalidArgumentError` si el id
        no tiene forma válida y
        :class:`~progression_service.core.exceptions.UserProfileUnavailableError` si el
        servicio dueño no responde. Quien llama no conoce el transporte.
        """
