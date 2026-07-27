"""App factory del progression-service.

Servicio FastAPI autónomo dueño de Statistics, Ranks, Achievements y Ranking, sobre su
propia base de datos. El arranque **no** ejecuta ningún recálculo masivo (ver T-029): abre
la conexión, asegura los índices y levanta el consumer de RabbitMQ (T-026), que recalcula
por usuario a medida que llegan los eventos de apuesta.
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import aio_pika
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from progression_service.api.deps import build_progression_service
from progression_service.api.routers import (
    achievements,
    internal,
    ranking,
    ranks,
    statistics,
)
from progression_service.core.config import get_settings
from progression_service.core.exceptions import (
    AlreadyExistsError,
    BetSourceUnavailableError,
    DomainError,
    ForbiddenError,
    InvalidArgumentError,
    InvalidCredentialsError,
    NotFoundError,
    UserProfileUnavailableError,
)
from progression_service.core.logging import (
    Timer,
    get_request_id,
    new_request_id,
    set_request_id,
    setup_logging,
)
from progression_service.core.observability import capture_error, init_sentry
from progression_service.infrastructure.database.mongo import (
    create_client,
    ensure_indexes,
    get_database,
)
from progression_service.infrastructure.events.rabbitmq_consumer import (
    ProgressionRecalcConsumer,
)

logger = logging.getLogger(__name__)

_SERVICE_NAME = "progression-service"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = create_client(
        settings.mongo_uri,
        max_pool_size=settings.mongo_max_pool_size,
        server_selection_timeout_ms=settings.mongo_server_selection_timeout_ms,
    )
    db = get_database(client, settings.mongo_db_name)
    await ensure_indexes(db)
    app.state.mongo_client = client
    app.state.db = db

    # Cliente compartido hacia bets-service, dueño de las apuestas. Construirlo no abre
    # ninguna conexión, así que este servicio arranca aunque bets-service esté caído: el
    # fallo aparece por petición como 503, no en el arranque.
    app.state.bets_client = httpx.AsyncClient(
        base_url=settings.bets_service_url,
        timeout=httpx.Timeout(settings.bets_service_timeout_seconds),
        headers={"X-Internal-Key": settings.internal_api_key},
    )

    # Consumer de `progression.recalc` (T-026): cierra el circuito asíncrono que abre
    # bets-service al publicar en `bets.events`. Sin URL configurada el servicio arranca
    # sin consumer y el recálculo sigue siendo manual por `POST /internal/recalculate`.
    rabbit_connection = None
    consumer_task = None
    if settings.rabbitmq_url:
        rabbit_connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await rabbit_connection.channel()
        await channel.set_qos(prefetch_count=settings.rabbitmq_prefetch_count)
        # get_queue, no declare_queue: la topología es de la infraestructura (T-025).
        queue = await channel.get_queue(settings.progression_recalc_queue)
        consumer = ProgressionRecalcConsumer(
            queue,
            lambda: build_progression_service(db, app.state.bets_client),
            cooldown_seconds=settings.rabbitmq_retry_cooldown_seconds,
        )
        consumer_task = asyncio.create_task(
            consumer.run(), name="progression-recalc-consumer"
        )

    try:
        yield
    finally:
        # El consumer usa la base y el cliente HTTP: se para antes de cerrarlos.
        if consumer_task is not None:
            consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer_task
        if rabbit_connection is not None:
            await rabbit_connection.close()
        await app.state.bets_client.aclose()
        await client.close()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log estructurado (JSON) de cada petición REST: método, ruta, status y duración.

    Es el punto único de log de peticiones: el access log por defecto de uvicorn se
    desactiva en :func:`setup_logging` para no duplicar cada línea. También propaga un
    ``request_id`` (nuevo o heredado de ``X-Request-ID``) que aparece en todos los logs
    generados durante la petición.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        set_request_id(request_id)
        timer = Timer()

        try:
            response = await call_next(request)
        except Exception as exc:
            capture_error(
                exc,
                service=_SERVICE_NAME,
                transport="http",
                failure_mode="fail-closed",
                request_id=request_id,
            )
            logger.exception(
                "Excepción no controlada procesando petición",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else None,
                    "duration_ms": timer.elapsed_ms(),
                },
            )
            raise

        logger.info(
            "Petición procesada",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": timer.elapsed_ms(),
                "client_ip": request.client.host if request.client else None,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rechaza con 413 peticiones cuyo ``Content-Length`` supere el límite configurado."""

    def __init__(self, app, max_body_bytes: int) -> None:
        super().__init__(app)
        self._max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Cuerpo de la petición demasiado grande."},
                    )
            except ValueError:
                pass
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Añade cabeceras de hardening y quita ``Server`` (revela uvicorn/versión)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Server"] = "api"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def _register_exception_handlers(app: FastAPI) -> None:
    """Traduce las excepciones de dominio a respuestas HTTP uniformes y las loguea."""

    status_map: dict[type[DomainError], int] = {
        NotFoundError: 404,
        AlreadyExistsError: 409,
        ForbiddenError: 403,
        InvalidCredentialsError: 401,
        BetSourceUnavailableError: 503,
        UserProfileUnavailableError: 503,
        InvalidArgumentError: 400,
    }

    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        status_code = status_map.get(type(exc), 400)

        # 5xx (errores no anticipados o dependencias caídas) se loguean como error; los 4xx
        # (validación, permisos) son parte del flujo normal y son warning.
        if status_code >= 500:
            capture_error(
                exc,
                service=_SERVICE_NAME,
                transport="http",
                failure_mode="fail-closed",
                request_id=get_request_id(),
                exc_type=type(exc).__name__,
            )
        log_level = logging.ERROR if status_code >= 500 else logging.WARNING
        logger.log(
            log_level,
            "Excepción de dominio: %s",
            exc.message,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "exc_type": type(exc).__name__,
            },
        )

        return JSONResponse(status_code=status_code, content={"detail": exc.message})

    app.add_exception_handler(DomainError, domain_error_handler)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    init_sentry(settings)

    # Fallar aquí es preferible a arrancar aceptando cualquier X-User-Id: sin el secreto de
    # servicio, la identidad que llega por cabecera no está respaldada por nada.
    if not settings.internal_api_key:
        raise RuntimeError(
            "INTERNAL_API_KEY no está configurada: cualquiera podría operar en nombre de "
            "otro usuario. Genera un valor con `openssl rand -hex 32`."
        )

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_exception_handlers(app)

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
