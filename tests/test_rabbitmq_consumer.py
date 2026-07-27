"""Tests del consumer de `progression.recalc` (T-026).

No necesitan broker ni Mongo: la cola, los mensajes y el servicio de progresión se
sustituyen por dobles que registran lo que se les pide, igual que
`bets-service/tests/test_rabbitmq_publisher.py` hace con el exchange.

Lo que se fija aquí es la política de confirmación, que es donde está el riesgo: ackear un
mensaje que falló porque bets-service no respondía dejaría la proyección obsoleta para
siempre, y devolverlo a la cola sin pausa convertiría el reintento en un bucle cerrado.
"""

import asyncio
import json

from progression_service.core.exceptions import BetSourceUnavailableError
from progression_service.core.logging import get_request_id
from progression_service.infrastructure.events.rabbitmq_consumer import (
    ProgressionRecalcConsumer,
)
from tests.conftest import USER_ID


class FakeMessage:
    """Mensaje entrante: registra si se confirmó, se devolvió a la cola o se descartó."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked = False
        self.nacked_requeue: bool | None = None

    async def ack(self) -> None:
        self.acked = True

    async def nack(self, requeue: bool = True) -> None:
        self.nacked_requeue = requeue


def message_for(event_type: str = "bet.created", **overrides) -> FakeMessage:
    payload = {
        "event_type": event_type,
        "user_id": USER_ID,
        "bet_id": "6a617db47729546dc1a36341",
        "request_id": None,
        "occurred_at": "2026-07-20T10:00:00+00:00",
    }
    payload.update(overrides)
    return FakeMessage(json.dumps(payload).encode("utf-8"))


class FakeProcessedEventRepository:
    """Doble en memoria de ``ProcessedEventRepository``: un set de claves ya vistas."""

    def __init__(self) -> None:
        self.seen: set[str] = set()

    async def is_processed(self, event_key: str) -> bool:
        return event_key in self.seen

    async def mark_processed(self, event_key: str) -> None:
        self.seen.add(event_key)


class RecordingService:
    """Servicio de progresión que anota a quién se le pidió recalcular."""

    def __init__(self, raises: Exception | None = None) -> None:
        self.recalculated: list[str] = []
        self.request_ids: list[str | None] = []
        self._raises = raises

    async def recalculate(self, user_id: str):
        self.recalculated.append(user_id)
        # Se captura aquí dentro para comprobar que el ContextVar ya está puesto cuando
        # corre el trabajo real, que es lo que lo propaga a bets-service.
        self.request_ids.append(get_request_id())
        if self._raises is not None:
            raise self._raises
        return None


def consumer_for(
    service: RecordingService,
    cooldown: float = 0.0,
    processed_events: FakeProcessedEventRepository | None = None,
):
    return ProgressionRecalcConsumer(
        queue=None,
        service_factory=lambda: service,
        processed_events=processed_events or FakeProcessedEventRepository(),
        cooldown_seconds=cooldown,
    )


async def test_recalculates_and_acks_on_bet_created():
    service = RecordingService()
    message = message_for("bet.created")

    await consumer_for(service).handle(message)

    assert service.recalculated == [USER_ID]
    assert message.acked
    assert message.nacked_requeue is None


async def test_handles_updated_and_deleted_too():
    for event_type in ("bet.updated", "bet.deleted"):
        service = RecordingService()

        await consumer_for(service).handle(message_for(event_type))

        assert service.recalculated == [USER_ID], event_type


async def test_malformed_body_is_acked_and_never_recalculates():
    service = RecordingService()
    message = FakeMessage(b"esto no es json")

    await consumer_for(service).handle(message)

    assert service.recalculated == []
    # Se confirma a propósito: reintentarlo no puede funcionar y sin dead-letter queue
    # dejarlo pendiente bloquearía el resto de la cola.
    assert message.acked


async def test_message_without_user_id_is_acked():
    service = RecordingService()
    message = message_for(user_id="")

    await consumer_for(service).handle(message)

    assert service.recalculated == []
    assert message.acked


async def test_unknown_event_type_is_ignored_and_acked():
    service = RecordingService()
    message = message_for("bet.archived")

    await consumer_for(service).handle(message)

    assert service.recalculated == []
    assert message.acked


async def test_bets_source_unavailable_requeues_instead_of_dropping():
    service = RecordingService(raises=BetSourceUnavailableError("bets-service caído"))
    message = message_for()

    await consumer_for(service).handle(message)

    # Fail-closed: el mensaje vuelve a la cola. Ackearlo dejaría al usuario con las
    # estadísticas viejas hasta su siguiente apuesta.
    assert message.nacked_requeue is True
    assert not message.acked


async def test_requeue_waits_the_cooldown_before_returning():
    service = RecordingService(raises=BetSourceUnavailableError("bets-service caído"))
    consumer = consumer_for(service, cooldown=0.05)

    started = asyncio.get_running_loop().time()
    await consumer.handle(message_for())
    elapsed = asyncio.get_running_loop().time() - started

    # Sin la pausa, el requeue reentrega al instante y el reintento se vuelve un bucle
    # cerrado mientras bets-service siga sin responder.
    assert elapsed >= 0.05


async def test_unexpected_error_is_discarded_without_requeue():
    service = RecordingService(raises=RuntimeError("fallo inesperado"))
    message = message_for()

    await consumer_for(service).handle(message)

    assert message.nacked_requeue is False
    assert not message.acked


async def test_a_failing_message_does_not_stop_the_next_one():
    broken = RecordingService(raises=RuntimeError("fallo inesperado"))
    consumer_broken = consumer_for(broken)
    await consumer_broken.handle(message_for())

    healthy = RecordingService()
    await consumer_for(healthy).handle(message_for())

    assert healthy.recalculated == [USER_ID]


async def test_request_id_from_the_event_reaches_the_recalculation():
    service = RecordingService()

    await consumer_for(service).handle(message_for(request_id="trace-me-123"))

    assert service.request_ids == ["trace-me-123"]


async def test_event_without_request_id_still_gets_one():
    service = RecordingService()

    await consumer_for(service).handle(message_for(request_id=None))

    assert service.request_ids[0]


async def test_duplicate_event_recalculates_only_once():
    """Caso mínimo viable de la Actividad C: dos entregas del mismo evento, un solo efecto."""

    service = RecordingService()
    processed_events = FakeProcessedEventRepository()
    consumer = consumer_for(service, processed_events=processed_events)

    await consumer.handle(message_for())
    second = message_for()
    await consumer.handle(second)

    assert service.recalculated == [USER_ID]
    assert second.acked
    assert second.nacked_requeue is None


async def test_two_distinct_events_recalculate_twice():
    service = RecordingService()
    consumer = consumer_for(service, processed_events=FakeProcessedEventRepository())

    await consumer.handle(message_for(bet_id="bet-1"))
    await consumer.handle(message_for(bet_id="bet-2"))

    assert service.recalculated == [USER_ID, USER_ID]


async def test_message_without_bet_id_is_acked_and_never_recalculates():
    service = RecordingService()
    message = message_for(bet_id="")

    await consumer_for(service).handle(message)

    assert service.recalculated == []
    assert message.acked


async def test_message_without_occurred_at_is_acked_and_never_recalculates():
    service = RecordingService()
    message = message_for(occurred_at=None)

    await consumer_for(service).handle(message)

    assert service.recalculated == []
    assert message.acked
