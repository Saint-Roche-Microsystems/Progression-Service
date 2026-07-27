"""Perfil de identidad de un usuario, tal y como lo devuelve users-service.

Entidad de dominio pura: es la forma en que este servicio entiende la respuesta del
patrón TCP ``users.profile``, con independencia de cómo la serialice el transporte.

No es la entidad :class:`~progression_service.domain.entities.user.User` heredada del
monolito: aquélla incluye credenciales y contadores de login porque describía la tabla
propia de un monolito que era dueño de los usuarios. Este servicio ya no lo es, así que
sólo modela lo que necesita para su proyección: el nombre que se pinta en el ranking y la
fecha de alta con la que se calcula la antigüedad de la cuenta.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserProfile:
    """Identidad pública de un usuario, propiedad de users-service."""

    id: str
    username: str
    tier: str = "standard"
    role: str = "USER"
    active: bool = True
    created_at: datetime | None = None
