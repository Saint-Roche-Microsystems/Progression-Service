"""Interfaz abstracta del repositorio de progresión (rango y logros)."""

from abc import ABC, abstractmethod

from progression_service.domain.entities.progression import UserProgression


class ProgressionRepository(ABC):
    """Contrato de persistencia para :class:`UserProgression`."""

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> UserProgression | None:
        """Devuelve la progresión del usuario, o ``None`` si no existe."""

    @abstractmethod
    async def upsert(self, progression: UserProgression) -> None:
        """Crea o reemplaza la progresión de un usuario (clave: ``user_id``)."""
