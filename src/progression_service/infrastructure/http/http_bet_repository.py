"""Implementación del puerto de apuestas contra la API interna de bets-service.

Sustituye a la lectura directa de Mongo: las apuestas viven en la base de bets-service, no
en la de este servicio, así que la única forma correcta de leerlas es por su contrato HTTP
(``GET /internal/bets``), autenticado con el secreto de servicio ``X-Internal-Key``.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from progression_service.core.exceptions import BetSourceUnavailableError
from progression_service.core.logging import get_request_id
from progression_service.domain.entities.bet import Bet, BetLeg, BetStatus, BetType
from progression_service.domain.repositories.bet_repository import BetRepository

logger = logging.getLogger(__name__)

_BETS_PATH = "/internal/bets"
_USER_IDS_PATH = "/internal/bets/user-ids"


def _parse_datetime(value: str) -> datetime:
    """ISO-8601 -> ``datetime`` **aware**.

    Mongo los devolvía siempre con zona (``tz_aware=True``) y el resto del dominio cuenta
    con ello: el cálculo de rachas ordena por fecha y la evaluación de rangos hace
    ``now - created_at``. Un ``datetime`` naive colado por aquí reventaría esas
    comparaciones con ``TypeError``, así que se asume UTC cuando no viene offset.
    """

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _leg_to_entity(doc: dict[str, Any]) -> BetLeg:
    return BetLeg(
        sport=doc["sport"],
        league=doc["league"],
        event=doc["event"],
        market=doc["market"],
        selection=doc["selection"],
        odds=doc["odds"],
    )


def _to_entity(doc: dict[str, Any], user_id: str) -> Bet:
    """Convierte un ``BetResponse`` de bets-service en la entidad local.

    ``user_id`` no viaja en la respuesta (el schema público no lo expone) pero se conoce:
    es por quien se preguntó.
    """

    return Bet(
        id=doc["id"],
        user_id=user_id,
        sport=doc["sport"],
        league=doc["league"],
        event=doc["event"],
        bet_type=BetType(doc["bet_type"]),
        market=doc["market"],
        selection=doc["selection"],
        odds=doc["odds"],
        stake=doc["stake"],
        bookmaker=doc["bookmaker"],
        event_datetime=_parse_datetime(doc["event_datetime"]),
        status=BetStatus(doc["status"]),
        notes=doc.get("notes"),
        reference_id=doc.get("reference_id"),
        legs=[_leg_to_entity(leg) for leg in doc.get("legs", [])],
        # Igual que en el mapeo Mongo: una apuesta simple puede no traer la combinada.
        combined_odds=doc.get("combined_odds") or doc["odds"],
        potential_return=doc["potential_return"],
        potential_profit=doc["potential_profit"],
        implied_probability=doc["implied_probability"],
        created_at=_parse_datetime(doc["created_at"]),
        updated_at=_parse_datetime(doc["updated_at"]),
    )


class HttpBetRepository(BetRepository):
    """Lee las apuestas de bets-service, su dueño, en lugar de una base local."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        page_size: int = 200,
        max_pages: int = 500,
    ) -> None:
        self._client = client
        self._page_size = page_size
        # Cota de seguridad: sin ella, un servidor que devolviera siempre la misma página
        # llena dejaría este bucle girando para siempre dentro de una petición.
        self._max_pages = max_pages

    async def list_all_by_user(self, user_id: str) -> list[Bet]:
        """Recorre las páginas de ``/internal/bets`` hasta juntar el historial completo."""

        collected: dict[str, Bet] = {}
        page = 1

        while page <= self._max_pages:
            payload = await self._get(
                _BETS_PATH,
                params={"user_id": user_id, "page": page, "page_size": self._page_size},
            )
            items = payload.get("items", [])
            total = int(payload.get("total", 0))

            for index, doc in enumerate(items):
                bet = _to_entity(doc, user_id)
                # bets-service ordena por fecha de creación descendente: una apuesta creada
                # mientras se pagina desplaza la ventana y puede repetir un documento entre
                # páginas. Un duplicado falsearía el conteo, el beneficio y las rachas.
                collected[bet.id or f"sin-id-{page}-{index}"] = bet

            if len(items) < self._page_size or len(collected) >= total:
                break
            page += 1
        else:
            logger.warning(
                "Se alcanzó el tope de páginas leyendo las apuestas del usuario.",
                extra={"user_id": user_id, "max_pages": self._max_pages},
            )

        return list(collected.values())

    async def distinct_user_ids(self) -> list[str]:
        payload = await self._get(_USER_IDS_PATH)
        return list(payload.get("user_ids", []))

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET contra bets-service; cualquier fallo se traduce a un error de dominio.

        Se propaga el ``X-Request-Id`` de la petición en curso para poder seguir una misma
        operación de negocio a través de los dos procesos.
        """

        headers = {}
        request_id = get_request_id()
        if request_id:
            headers["X-Request-Id"] = request_id

        try:
            response = await self._client.get(path, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            # Un 401 aquí significa secretos desalineados entre servicios, no un servicio
            # caído: sin el código en el mensaje ese diagnóstico se pierde.
            logger.warning(
                "bets-service respondió con un código de error.",
                extra={"path": path, "status_code": exc.response.status_code},
            )
            raise BetSourceUnavailableError(
                f"bets-service respondió {exc.response.status_code} al leer las apuestas."
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError cubre una respuesta que no es JSON válido.
            raise BetSourceUnavailableError(
                f"No se pudieron leer las apuestas desde bets-service: {exc}"
            ) from exc
