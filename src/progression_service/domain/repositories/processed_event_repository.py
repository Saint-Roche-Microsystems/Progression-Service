"""Interfaz abstracta del repositorio de eventos de apuesta ya procesados (idempotencia)."""

from abc import ABC, abstractmethod


class ProcessedEventRepository(ABC):
    """Contrato de persistencia para las claves de eventos ya aplicados."""

    @abstractmethod
    async def is_processed(self, event_key: str) -> bool:
        """Devuelve ``True`` si ``event_key`` ya fue marcado como procesado."""

    @abstractmethod
    async def mark_processed(self, event_key: str) -> None:
        """Registra ``event_key`` como procesado. Marcarla dos veces no debe fallar."""
