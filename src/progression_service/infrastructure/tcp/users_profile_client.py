"""Cliente TCP del contrato ``users.profile`` de users-service.

Es el hop síncrono progression-service -> users-service. El framing es el de
``Transport.TCP`` de Nest (``<longitud>#<json>``), el mismo que ya habla bets-service en
``bets-service/src/bets_service/infrastructure/tcp/users_validator.py``: se replica el
transporte, no el contrato, porque cada servicio pregunta por lo suyo.

Todo lo que sale de aquí son excepciones de dominio: quien llama no conoce ``asyncio`` ni
el framing de Nest, sólo sabe que un usuario no existe (404), que el id no vale (400) o
que el servicio dueño no responde (503).
"""

from __future__ import annotations

import asyncio
import codecs
import json
import logging
from datetime import datetime

from progression_service.core.exceptions import (
    InvalidArgumentError,
    NotFoundError,
    UserProfileUnavailableError,
)
from progression_service.core.logging import get_request_id
from progression_service.domain.entities.user_profile import UserProfile
from progression_service.domain.repositories.user_profile_provider import (
    UserProfileProvider,
)

logger = logging.getLogger(__name__)

# Códigos del contrato (los declara users-service en
# `users-service/src/users/users.messages.controller.ts`) y su traducción a dominio.
_ERROR_CODES: dict[str, type] = {
    "NOT_FOUND": NotFoundError,
    "INVALID_ARGUMENT": InvalidArgumentError,
}


class TcpUserProfileClient(UserProfileProvider):
    """Resuelve el perfil de un usuario contra users-service por TCP."""

    PATTERN = "users.profile"

    def __init__(self, host: str, port: int, timeout_seconds: float) -> None:
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds

    async def get_profile(self, user_id: str) -> UserProfile:
        try:
            response = await asyncio.wait_for(
                self._request({"user_id": user_id, "request_id": get_request_id()}),
                timeout=self._timeout_seconds,
            )
        except (asyncio.TimeoutError, OSError, ValueError) as exc:
            # Timeout, socket caído o respuesta ilegible: es indisponibilidad del servicio
            # dueño, no un problema del usuario preguntado (API -> 503).
            raise UserProfileUnavailableError(
                f"No se pudo resolver el perfil contra users-service: {exc}"
            ) from exc

        return UserProfile(
            id=str(response.get("id") or user_id),
            username=str(response.get("username") or ""),
            tier=str(response.get("tier") or "standard"),
            role=str(response.get("role") or "USER"),
            active=bool(response.get("active", True)),
            created_at=_parse_datetime(response.get("created_at")),
        )

    async def _request(self, data: dict[str, object]) -> dict[str, object]:
        """Envía un mensaje al transporte TCP de Nest y devuelve el campo ``response``."""

        reader, writer = await asyncio.open_connection(self._host, self._port)
        try:
            payload = {"pattern": self.PATTERN, "id": "1", "data": data}
            # La petición sólo lleva identificadores ASCII, así que aquí bytes y unidades
            # UTF-16 coinciden; ver _read_frame para el caso contrario.
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            writer.write(f"{len(body)}#".encode("utf-8") + body)
            await writer.drain()

            message = await self._read_frame(reader)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

        if message.get("err") is not None:
            self._raise_from_err(message["err"])

        response = message.get("response")
        if not isinstance(response, dict):
            raise ValueError(f"Respuesta TCP sin objeto 'response': {message!r}")
        return response

    @staticmethod
    def _raise_from_err(err: object) -> None:
        """Traduce el error del contrato a una excepción de dominio.

        Se aceptan las dos formas en que Nest puede serializar un ``RpcException``: la
        carga tal cual (``{"code": ...}``, que es lo que produce el filtro global de
        users-service) y la carga envuelta (``{"error": {"code": ...}}``, la forma que
        salía antes de corregir ese filtro). Un consumidor no puede exigir que todo el
        parque de servicios se despliegue a la vez.
        """

        payload = err
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            payload = payload["error"]

        if isinstance(payload, dict):
            code = str(payload.get("code") or "")
            message = str(payload.get("message") or "users-service devolvió un error.")
        else:
            code, message = "", str(payload)

        exception = _ERROR_CODES.get(code)
        if exception is not None:
            raise exception(message)

        # Error no tipado: es un fallo del servicio dueño, no del argumento recibido.
        raise UserProfileUnavailableError(
            f"users-service devolvió un error no tipado: {message}"
        )

    @staticmethod
    async def _read_frame(reader: asyncio.StreamReader) -> dict[str, object]:
        """Lee un frame ``<longitud>#<json>`` del transporte TCP de Nest.

        Ojo con la longitud: Nest la calcula con ``messageData.length``
        (``@nestjs/microservices/helpers/json-socket.js:61``), que en JavaScript son
        **unidades UTF-16**, no bytes. Con un mensaje ASCII da lo mismo, pero en cuanto el
        contrato devuelve texto acentuado —y los mensajes de error de este repositorio
        están en español— leer esa cifra como bytes corta el JSON a media palabra. Por eso
        se leen bytes hasta completar el número de unidades UTF-16 anunciado.
        """

        length = int((await reader.readuntil(b"#"))[:-1])

        decoder = codecs.getincrementaldecoder("utf-8")()
        text = decoder.decode(await reader.readexactly(length))
        while _utf16_units(text) < length:
            text += decoder.decode(await reader.readexactly(1))

        return json.loads(text)


def _utf16_units(text: str) -> int:
    """Longitud del texto tal y como la cuenta JavaScript (unidades UTF-16)."""

    return sum(2 if ord(char) > 0xFFFF else 1 for char in text)


def _parse_datetime(value: object) -> datetime | None:
    """Convierte el ``created_at`` ISO-8601 del contrato, tolerando el sufijo ``Z``."""

    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("users.profile devolvió un created_at ilegible: %r", value)
        return None
