"""Tests del repositorio de apuestas contra la API interna de bets-service.

Se usa ``httpx.MockTransport``: se ejercita el cliente real (cabeceras, query params,
paginación, traducción de errores) sin levantar bets-service ni Mongo.
"""

import httpx
import pytest

from progression_service.core.exceptions import BetSourceUnavailableError
from progression_service.domain.entities.bet import BetStatus, BetType
from progression_service.infrastructure.http.http_bet_repository import HttpBetRepository
from tests.conftest import INTERNAL_API_KEY, USER_ID, bet_payload


def _repo(handler, **kwargs) -> HttpBetRepository:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://bets-service:8002",
        headers={"X-Internal-Key": INTERNAL_API_KEY},
    )
    return HttpBetRepository(client, **kwargs)


def _page(items: list[dict], total: int, page: int, page_size: int) -> httpx.Response:
    return httpx.Response(
        200, json={"items": items, "total": total, "page": page, "page_size": page_size}
    )


async def test_parses_a_single_page():
    def handler(request: httpx.Request) -> httpx.Response:
        return _page([bet_payload()], total=1, page=1, page_size=200)

    bets = await _repo(handler).list_all_by_user(USER_ID)

    assert len(bets) == 1
    bet = bets[0]
    # user_id no viaja en la respuesta: lo aporta quien preguntó.
    assert bet.user_id == USER_ID
    assert bet.id == "6a617db47729546dc1a36341"
    assert bet.status == BetStatus.WON
    assert bet.bet_type == BetType.SIMPLE
    assert bet.stake == 10.0
    assert bet.combined_odds == 2.0


async def test_parses_legs_of_a_parlay():
    leg = {
        "sport": "Tenis",
        "league": "ATP",
        "event": "A vs B",
        "market": "Ganador",
        "selection": "A",
        "odds": 1.5,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = bet_payload(bet_type="PARLAY", legs=[leg], combined_odds=3.0)
        return _page([payload], total=1, page=1, page_size=200)

    bets = await _repo(handler).list_all_by_user(USER_ID)

    assert bets[0].bet_type == BetType.PARLAY
    assert [leg.sport for leg in bets[0].legs] == ["Tenis"]


async def test_datetimes_are_timezone_aware():
    """Un datetime naive rompería las comparaciones de rachas y edad de la cuenta."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _page([bet_payload()], total=1, page=1, page_size=200)

    bet = (await _repo(handler).list_all_by_user(USER_ID))[0]

    assert bet.created_at.tzinfo is not None
    assert bet.updated_at.tzinfo is not None
    assert bet.event_datetime.tzinfo is not None


async def test_datetime_without_offset_is_assumed_utc():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = bet_payload(created_at="2026-07-20T10:00:00")
        return _page([payload], total=1, page=1, page_size=200)

    bet = (await _repo(handler).list_all_by_user(USER_ID))[0]

    assert bet.created_at.utcoffset().total_seconds() == 0


async def test_combined_odds_falls_back_to_odds():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = bet_payload(odds=1.8)
        payload.pop("combined_odds")
        return _page([payload], total=1, page=1, page_size=200)

    bet = (await _repo(handler).list_all_by_user(USER_ID))[0]

    assert bet.combined_odds == 1.8


async def test_paginates_until_total():
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        page = int(request.url.params["page"])
        items = [bet_payload(id=f"bet-{page}-{i}") for i in range(2 if page < 3 else 1)]
        return _page(items, total=5, page=page, page_size=2)

    bets = await _repo(handler, page_size=2).list_all_by_user(USER_ID)

    assert len(bets) == 5
    assert [p["page"] for p in seen] == ["1", "2", "3"]
    assert {p["user_id"] for p in seen} == {USER_ID}
    assert {p["page_size"] for p in seen} == {"2"}


async def test_stops_on_short_page_even_if_total_lies():
    """Una página más corta que el tamaño pedido es fin de datos, diga lo que diga total."""

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _page([bet_payload()], total=99, page=1, page_size=10)

    bets = await _repo(handler, page_size=10).list_all_by_user(USER_ID)

    assert calls == 1
    assert len(bets) == 1


async def test_deduplicates_bets_repeated_across_pages():
    """Una apuesta creada mientras se pagina desplaza la ventana y puede repetirse."""

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        if page == 1:
            items = [bet_payload(id="a"), bet_payload(id="b")]
        else:
            items = [bet_payload(id="b"), bet_payload(id="c")]
        return _page(items, total=4, page=page, page_size=2)

    bets = await _repo(handler, page_size=2, max_pages=2).list_all_by_user(USER_ID)

    assert sorted(bet.id for bet in bets) == ["a", "b", "c"]


async def test_respects_max_pages():
    """Un servidor que devuelve siempre una página llena no puede colgar la petición."""

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        page = int(request.url.params["page"])
        items = [bet_payload(id=f"bet-{page}-{i}") for i in range(2)]
        return _page(items, total=1_000, page=page, page_size=2)

    bets = await _repo(handler, page_size=2, max_pages=3).list_all_by_user(USER_ID)

    assert calls == 3
    assert len(bets) == 6


async def test_sends_internal_key_and_request_id():
    from progression_service.core.logging import set_request_id

    set_request_id("trace-123")
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return _page([], total=0, page=1, page_size=200)

    await _repo(handler).list_all_by_user(USER_ID)

    assert captured["x-internal-key"] == INTERNAL_API_KEY
    assert captured["x-request-id"] == "trace-123"


async def test_transport_error_raises_instead_of_returning_empty():
    """El caso que justifica el diseño: un fallo de red no puede parecer "sin apuestas"."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(BetSourceUnavailableError):
        await _repo(handler).list_all_by_user(USER_ID)


@pytest.mark.parametrize("status_code", [401, 404, 500])
async def test_error_status_codes_raise_with_the_code_in_the_message(status_code: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "nope"})

    with pytest.raises(BetSourceUnavailableError) as excinfo:
        await _repo(handler).list_all_by_user(USER_ID)

    # Un 401 es secretos desalineados, no un servicio caído: hay que poder distinguirlo.
    assert str(status_code) in excinfo.value.message


async def test_invalid_json_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="esto no es json")

    with pytest.raises(BetSourceUnavailableError):
        await _repo(handler).list_all_by_user(USER_ID)


async def test_distinct_user_ids_parses_the_wrapper():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/bets/user-ids"
        return httpx.Response(200, json={"user_ids": ["u1", "u2"]})

    assert await _repo(handler).distinct_user_ids() == ["u1", "u2"]


async def test_distinct_user_ids_raises_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "caído"})

    with pytest.raises(BetSourceUnavailableError):
        await _repo(handler).distinct_user_ids()
