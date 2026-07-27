"""Tests del cliente TCP del contrato ``users.profile``.

Se ejercita contra un servidor asyncio mínimo que reproduce el framing del transporte
``Transport.TCP`` de Nest (``<longitud>#<json>``), sin necesitar el users-service real —
misma técnica que ``bets-service/tests/test_tcp_user_validator.py``, que prueba el otro
hop TCP del sistema. La verificación contra el Nest real se hace en integración.

Lo que se fija aquí es la traducción: **todo** lo que sale del cliente es una excepción de
dominio de este servicio, nunca un error de socket ni un código del transporte.
"""

import asyncio
import json

import pytest

from progression_service.core.exceptions import (
    InvalidArgumentError,
    NotFoundError,
    UserProfileUnavailableError,
)
from progression_service.infrastructure.tcp.users_profile_client import (
    TcpUserProfileClient,
)

USER_ID = "6a60c83b2a0af5b4ab9745cf"


def _encode(payload: dict) -> bytes:
    body = json.dumps(payload, separators=(",", ":")).encode()
    return f"{len(body)}#".encode() + body


async def _read_frame(reader: asyncio.StreamReader) -> dict:
    length = int((await reader.readuntil(b"#"))[:-1])
    body = await reader.readexactly(length)
    return json.loads(body.decode())


async def _serve(handler):
    """Levanta un servidor Nest-like en un puerto libre y devuelve (server, port)."""

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


def _responder(frame: dict, *, capture: list | None = None):
    """Handler que contesta ``frame`` (con el id de la petición) y cierra."""

    async def handler(reader, writer):
        request = await _read_frame(reader)
        if capture is not None:
            capture.append(request)
        writer.write(_encode({"id": request["id"], **frame, "isDisposed": True}))
        await writer.drain()
        writer.close()

    return handler


async def test_parses_profile_response():
    requests: list[dict] = []
    handler = _responder(
        {
            "response": {
                "id": USER_ID,
                "username": "olivier",
                "tier": "gold",
                "role": "USER",
                "active": True,
                "created_at": "2026-01-15T10:30:00.000Z",
            }
        },
        capture=requests,
    )

    server, port = await _serve(handler)
    async with server:
        client = TcpUserProfileClient("127.0.0.1", port, timeout_seconds=5.0)
        profile = await client.get_profile(USER_ID)

    assert requests[0]["pattern"] == "users.profile"
    # El request_id viaja con la consulta para correlacionar este hop con la petición HTTP
    # que lo originó; fuera de una request en curso es None.
    assert requests[0]["data"] == {"user_id": USER_ID, "request_id": None}
    assert profile.username == "olivier"
    assert profile.tier == "gold"
    assert profile.created_at is not None
    assert profile.created_at.year == 2026


async def test_not_found_becomes_a_domain_not_found():
    """El usuario inexistente llega tipado y se traduce a 404, no a 500 ni a fila vacía."""

    server, port = await _serve(
        _responder({"err": {"code": "NOT_FOUND", "message": "Usuario no encontrado."}})
    )
    async with server:
        client = TcpUserProfileClient("127.0.0.1", port, timeout_seconds=5.0)
        with pytest.raises(NotFoundError):
            await client.get_profile(USER_ID)


async def test_invalid_argument_becomes_a_domain_invalid_argument():
    server, port = await _serve(
        _responder(
            {"err": {"code": "INVALID_ARGUMENT", "message": "user_id inválido."}}
        )
    )
    async with server:
        client = TcpUserProfileClient("127.0.0.1", port, timeout_seconds=5.0)
        with pytest.raises(InvalidArgumentError):
            await client.get_profile("no-es-un-objectid")


async def test_accepts_the_wrapped_error_shape():
    """Compatibilidad: un users-service anterior envolvía la carga del RpcException.

    Sin esto, un despliegue escalonado (users-service viejo, este servicio nuevo) degrada
    todos los 404 a 503.
    """

    server, port = await _serve(
        _responder({"err": {"error": {"code": "NOT_FOUND", "message": "no está"}}})
    )
    async with server:
        client = TcpUserProfileClient("127.0.0.1", port, timeout_seconds=5.0)
        with pytest.raises(NotFoundError):
            await client.get_profile(USER_ID)


async def test_untyped_error_becomes_unavailable():
    """Un error sin código no es culpa del argumento: se trata como indisponibilidad."""

    server, port = await _serve(_responder({"err": "boom"}))
    async with server:
        client = TcpUserProfileClient("127.0.0.1", port, timeout_seconds=5.0)
        with pytest.raises(UserProfileUnavailableError):
            await client.get_profile(USER_ID)


async def test_connection_refused_becomes_unavailable():
    # Puerto sin nadie escuchando: el consumidor no puede quedarse colgado ni reventar.
    client = TcpUserProfileClient("127.0.0.1", 1, timeout_seconds=2.0)
    with pytest.raises(UserProfileUnavailableError):
        await client.get_profile(USER_ID)


async def test_timeout_becomes_unavailable():
    async def handler(reader, writer):
        await _read_frame(reader)
        await asyncio.sleep(1.0)  # más lento que el timeout
        writer.close()

    server, port = await _serve(handler)
    async with server:
        client = TcpUserProfileClient("127.0.0.1", port, timeout_seconds=0.2)
        with pytest.raises(UserProfileUnavailableError):
            await client.get_profile(USER_ID)
