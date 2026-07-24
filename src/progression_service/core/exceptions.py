"""Excepciones de dominio, independientes del framework web.

Se traducen a respuestas HTTP mediante handlers registrados en ``main.py``.
"""


class DomainError(Exception):
    """Base para todos los errores de dominio."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """El recurso solicitado no existe (o no pertenece al usuario). -> 404."""


class AlreadyExistsError(DomainError):
    """Conflicto de unicidad (email o username ya en uso). -> 409."""


class InvalidCredentialsError(DomainError):
    """Credenciales de autenticación inválidas. -> 401."""


class ForbiddenError(DomainError):
    """El usuario no tiene permisos para la acción. -> 403."""


class AccountLockedError(DomainError):
    """Cuenta bloqueada temporalmente tras demasiados intentos de login fallidos. -> 429."""

    def __init__(self, message: str, *, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class InvalidImportFileError(DomainError):
    """El archivo de importación es inválido (no es .xlsx o faltan columnas). -> 400."""


class InvalidBetError(DomainError):
    """La apuesta viola una regla de negocio (p. ej. SIMPLE/PARLAY vs legs). -> 400."""
