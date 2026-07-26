"""Fixtures compartidas de los tests del progression-service.

Ninguno necesita Mongo ni bets-service levantados: los endpoints de catálogo se sirven sin
base de datos y el repositorio HTTP se prueba contra un transporte simulado de httpx.
"""

import os

# ``create_app`` aborta sin secreto de servicio, y hay tests que la invocan: hay que fijarlo
# antes de que se importe la configuración.
INTERNAL_API_KEY = "test-internal-key"
os.environ.setdefault("INTERNAL_API_KEY", INTERNAL_API_KEY)

from datetime import datetime, timezone  # noqa: E402

USER_ID = "6a60c83b2a0af5b4ab9745cf"


def bet_payload(**overrides) -> dict:
    """Un ``BetResponse`` tal y como lo devuelve ``GET /internal/bets`` de bets-service.

    Copiado de la forma real del schema para que un cambio de contrato salte aquí y no en
    producción.
    """

    payload = {
        "id": "6a617db47729546dc1a36341",
        "sport": "Fútbol",
        "league": "LaLiga",
        "event": "Real Madrid vs Barcelona",
        "bet_type": "SIMPLE",
        "market": "1X2",
        "selection": "Real Madrid",
        "odds": 2.0,
        "stake": 10.0,
        "bookmaker": "Bet365",
        "event_datetime": "2026-08-01T20:00:00+00:00",
        "status": "WON",
        "notes": None,
        "reference_id": None,
        "legs": [],
        "combined_odds": 2.0,
        "potential_return": 20.0,
        "potential_profit": 10.0,
        "implied_probability": 0.5,
        "created_at": "2026-07-20T10:00:00+00:00",
        "updated_at": "2026-07-20T10:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)
