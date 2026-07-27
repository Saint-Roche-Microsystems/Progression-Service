"""Consumer de la cola ``progression.recalc`` (T-026).

Cierra el circuito asíncrono que abre bets-service: cada mutación de apuesta se publica en
el exchange ``bets.events`` y llega aquí por el binding ``bet.#``. El evento sólo **avisa**
de qué usuario cambió; el historial se relee de bets-service por HTTP, así que reprocesar
un mensaje repetido o antiguo da el mismo resultado.

La topología (exchange, cola, binding) la declara la infraestructura en
``rabbitmq/definitions.json``: este servicio la busca, nunca la declara.

Política de confirmación, por caso:

- Mensaje ilegible o tipo desconocido -> ``ack``. Reintentarlo nunca funcionaría, y sin
  dead-letter queue dejarlo en la cola bloquearía el resto.
- ``BetSourceUnavailableError`` (bets-service no responde) -> ``nack`` con requeue y una
  pausa. Es un fallo transitorio y el recálculo es fail-closed: descartar el mensaje
  dejaría la proyección obsoleta para siempre.
- Cualquier otro error -> ``nack`` sin requeue, es decir se descarta. Queda en Sentry y en
  el log; el siguiente evento del usuario (o el backfill) repara la proyección, mientras
  que un requeue infinito sin DLQ quemaría CPU indefinidamente.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable

from progression_service.application.services.progression_service import ProgressionService
from progression_service.core.exceptions import BetSourceUnavailableError
from progression_service.core.logging import new_request_id, set_request_id

logger = logging.getLogger(__name__)

_SERVICE_NAME = "progression-service"
_TRANSPORT = "rabbitmq"

# Los tres tipos que publica bets-service y que obligan a recalcular. El contrato del
# mensaje vive en bets_service.domain.entities.bet_event.BetEvent.as_message().
RECALC_EVENT_TYPES = frozenset({"bet.created", "bet.updated", "bet.deleted"})


class ProgressionRecalcConsumer:
    """Consume eventos de apuesta y dispara el recálculo de progresión del usuario."""

    def __init__(
        self,
        queue,
        service_factory: Callable[[], ProgressionService],
        *,
        cooldown_seconds: float = 5.0,
    ) -> None:
        self._queue = queue
        self._service_factory = service_factory
        self._cooldown_seconds = cooldown_seconds

    async def run(self) -> None:
        """Bucle de consumo. Sólo termina cuando se cancela la tarea que lo ejecuta."""

        while True:
            try:
                async with self._queue.iterator() as messages:
                    async for message in messages:
                        await self.handle(message)
            except asyncio.CancelledError:
                # Apagado ordenado desde el lifespan: no es un error, debe propagarse.
                raise
            except Exception:
                logger.exception(
                    "El bucle de consumo de '%s' falló; reintentando en %.1fs.",
                    getattr(self._queue, "name", "progression.recalc"),
                    self._cooldown_seconds,
                )
            # También tras una salida limpia del iterador (canal cerrado por el broker):
            # evita reabrirlo en bucle cerrado.
            await asyncio.sleep(self._cooldown_seconds)

    async def handle(self, message) -> None:
        """Procesa un mensaje. Nunca propaga: un mensaje malo no puede matar el bucle."""

        event = self._parse(message)
        if event is None:
            await message.ack()
            return

        event_type, user_id, request_id = event

        # ContextVar: a partir de aquí todos los logs del mensaje llevan el request_id, y
        # HttpBetRepository lo reenvía como X-Request-Id a bets-service. Así un recálculo
        # se puede rastrear hasta el POST /bets que lo originó.
        set_request_id(request_id or new_request_id())

        if event_type not in RECALC_EVENT_TYPES:
            logger.warning(
                "Evento '%s' ignorado: no obliga a recalcular.",
                event_type,
                extra={"event_type": event_type, "user_id": user_id},
            )
            await message.ack()
            return

        try:
            await self._service_factory().recalculate(user_id)
        except BetSourceUnavailableError as exc:
            self._report(exc, "fail-closed", event_type, user_id, request_id)
            logger.warning(
                "bets-service no responde; el evento '%s' de %s vuelve a la cola.",
                event_type,
                user_id,
            )
            await message.nack(requeue=True)
            # Sin esta pausa el mensaje se reentrega al instante y el reintento se vuelve
            # un bucle cerrado mientras bets-service siga caído.
            await asyncio.sleep(self._cooldown_seconds)
            return
        except Exception as exc:
            self._report(exc, "fail-open", event_type, user_id, request_id)
            logger.exception(
                "Error recalculando la progresión de %s por el evento '%s'; se descarta.",
                user_id,
                event_type,
            )
            await message.nack(requeue=False)
            return

        await message.ack()
        logger.info(
            "Progresión recalculada por evento.",
            extra={"event_type": event_type, "user_id": user_id},
        )

    def _parse(self, message) -> tuple[str, str, str | None] | None:
        """Extrae ``(event_type, user_id, request_id)``; ``None`` si el mensaje es basura."""

        try:
            payload = json.loads(message.body)
            event_type = payload["event_type"]
            user_id = payload["user_id"]
            request_id = payload.get("request_id")
        except (ValueError, TypeError, KeyError, AttributeError):
            logger.warning(
                "Mensaje descartado por ilegible en la cola de recálculo.",
                extra={"body": _preview(message)},
            )
            return None

        if not isinstance(user_id, str) or not user_id:
            logger.warning(
                "Mensaje descartado: 'user_id' ausente o vacío.",
                extra={"event_type": event_type},
            )
            return None

        return event_type, user_id, request_id if isinstance(request_id, str) else None

    def _report(
        self,
        exc: Exception,
        failure_mode: str,
        event_type: str,
        user_id: str,
        request_id: str | None,
    ) -> None:
        # Import local: mantiene el módulo importable en tests sin inicializar Sentry.
        from progression_service.core.observability import capture_error

        capture_error(
            exc,
            service=_SERVICE_NAME,
            transport=_TRANSPORT,
            failure_mode=failure_mode,
            request_id=request_id,
            event_type=event_type,
            user_id=user_id,
        )


def _preview(message, limit: int = 200) -> str:
    """Primeros bytes del cuerpo, para poder identificar el mensaje roto en el log."""

    try:
        return message.body[:limit].decode("utf-8", errors="replace")
    except AttributeError:
        return "<sin cuerpo>"
