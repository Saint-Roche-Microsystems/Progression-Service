"""Integración con Sentry (error tracking, sin performance tracing).

``init_sentry`` es no-op si no hay DSN configurado: el servicio arranca igual en
desarrollo local sin depender de una cuenta de Sentry. ``capture_error`` es el punto
único usado por los handlers/middlewares y publishers para reportar un error ya
manejado (fail-open) o a punto de propagarse (fail-closed), con la misma convención de
tags en los 5 microservicios: ``service``, ``transport``, ``failure_mode``, ``request_id``.
"""

from __future__ import annotations

import sentry_sdk

from progression_service.core.config import Settings


def init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        release=settings.app_version,
        send_default_pii=False,
    )


def capture_error(
    exc: Exception,
    *,
    service: str,
    transport: str,
    failure_mode: str,
    request_id: str | None,
    **extra_context: object,
) -> None:
    """Reporta ``exc`` a Sentry sin relanzar: el llamador decide el comportamiento de
    negocio (fail-open/fail-closed), esta función solo añade visibilidad."""

    with sentry_sdk.new_scope() as scope:
        scope.set_tag("service", service)
        scope.set_tag("transport", transport)
        scope.set_tag("failure_mode", failure_mode)
        if request_id:
            scope.set_tag("request_id", request_id)
        for key, value in extra_context.items():
            scope.set_context(key, value if isinstance(value, dict) else {"value": value})
        sentry_sdk.capture_exception(exc)
