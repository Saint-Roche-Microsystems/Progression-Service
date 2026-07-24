"""Configuración por variables de entorno del progression-service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes del servicio, cargados de variables de entorno / ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Fijazo Progression Service"
    debug: bool = False

    # Base de datos propia de este servicio (independiente del monolito).
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "progression_service"
    mongo_max_pool_size: int = 10
    mongo_server_selection_timeout_ms: int = 10_000

    # CORS: orígenes autorizados del frontend, separados por comas.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
