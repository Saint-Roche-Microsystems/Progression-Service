"""App factory del progression-service.

Servicio FastAPI autónomo dueño de Statistics, Ranks, Achievements y Ranking, sobre su
propia base de datos. El arranque **no** ejecuta ningún recálculo masivo (ver T-029): sólo
abre la conexión y asegura los índices.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from progression_service.core.config import settings
from progression_service.core.logging import setup_logging
from progression_service.infrastructure.database.mongo import (
    create_client,
    ensure_indexes,
    get_database,
)
from progression_service.api.routers import (
    achievements,
    internal,
    ranking,
    ranks,
    statistics,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("DEBUG" if settings.debug else "INFO")
    client = create_client(
        settings.mongo_uri,
        max_pool_size=settings.mongo_max_pool_size,
        server_selection_timeout_ms=settings.mongo_server_selection_timeout_ms,
    )
    db = get_database(client, settings.mongo_db_name)
    await ensure_indexes(db)
    app.state.mongo_client = client
    app.state.db = db
    try:
        yield
    finally:
        await client.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(statistics.router)
    app.include_router(ranks.router)
    app.include_router(achievements.router)
    app.include_router(ranking.router)
    app.include_router(internal.router)
    return app


app = create_app()
