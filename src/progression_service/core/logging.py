"""Logging estructurado (JSON) para los activos más sensibles de la API:
peticiones REST y excepciones.

Estándar de campos (uno por línea, en cada log):
    timestamp, level, logger, message, request_id y, cuando aplica,
    method, path, status_code, duration_ms, client_ip, user_id, exc_type.

Un único ``JsonFormatter`` se usa tanto para los logs de aplicación (``logger.info(...)``)
como para el middleware de peticiones y los handlers de excepción, de forma que todo el
log de la API queda en el mismo formato parseable (p. ej. por un agregador tipo
CloudWatch/ELK).
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

_REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("request_id", default=None)

# Atributos estándar de LogRecord: cualquier otro atributo se considera "extra" y se
# vuelca dentro del JSON de salida.
_STANDARD_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)


def get_request_id() -> str | None:
    """Devuelve el request_id de la petición HTTP en curso, si existe."""

    return _REQUEST_ID_CTX.get()


def set_request_id(request_id: str) -> None:
    _REQUEST_ID_CTX.set(request_id)


def new_request_id() -> str:
    return uuid.uuid4().hex


class JsonFormatter(logging.Formatter):
    """Formatea cada LogRecord como una línea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS and key != "message":
                payload[key] = value

        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """Configura el logging raíz de la aplicación en formato JSON.

    Silencia el access log por defecto de uvicorn: las peticiones REST ya quedan
    registradas (con más contexto) por ``RequestLoggingMiddleware``, y dejar ambos
    activos duplicaría cada línea.
    """

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").disabled = True


class Timer:
    """Cronómetro simple para medir la duración de una petición, en milisegundos."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)
