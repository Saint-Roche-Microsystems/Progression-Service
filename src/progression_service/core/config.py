"""Configuración por variables de entorno del progression-service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes del servicio, cargados de variables de entorno / ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Fijazo Progression Service"
    app_description: str = (
        "Progresión de fijazoo: estadísticas, rangos, logros y ranking del usuario."
    )
    app_version: str = "0.1.0"
    debug: bool = False
    max_request_body_bytes: int = 256 * 1024

    # Base de datos propia de este servicio (independiente del monolito).
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "progression_service"
    mongo_max_pool_size: int = 10
    mongo_server_selection_timeout_ms: int = 10_000

    # CORS: orígenes autorizados del frontend, separados por comas.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Secreto de servicio a servicio. Protege todas las rutas internas; sin valor, el
    # servicio se niega a arrancar (mismo criterio que auth-service/bets-service).
    internal_api_key: str = ""

    # Logging: nivel raíz de la app (DEBUG/INFO/WARNING/ERROR). Los logs se emiten en JSON
    # (ver core/logging.py), un registro por petición REST más uno por excepción.
    log_level: str = "INFO"

    # Sentry (error tracking, sin performance tracing). DSN vacío = SDK deshabilitado, no
    # rompe el arranque local.
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.0


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de :class:`Settings`."""

    return Settings()
