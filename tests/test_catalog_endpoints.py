"""Tests de los endpoints de catálogo (no requieren base de datos)."""

import httpx
from httpx import ASGITransport

from progression_service.main import create_app
from progression_service.domain.services.ranks_config import RANKS
from progression_service.domain.services.achievements_catalog import CATALOG


async def _client() -> httpx.AsyncClient:
    app = create_app()
    return httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    )


async def test_health():
    async with await _client() as c:
        r = await c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


async def test_ranks_catalog():
    async with await _client() as c:
        r = await c.get("/ranks")
        assert r.status_code == 200
        assert len(r.json()) == len(RANKS)


async def test_achievements_catalog():
    async with await _client() as c:
        r = await c.get("/achievements")
        assert r.status_code == 200
        assert len(r.json()) == len(CATALOG)


async def test_internal_recalculate_requires_the_service_secret():
    """Dispara trabajo de recálculo: no puede quedar abierta a quien alcance el puerto."""

    async with await _client() as c:
        sin_clave = await c.post("/internal/recalculate/u1")
        clave_mala = await c.post(
            "/internal/recalculate/u1", headers={"X-Internal-Key": "clave-incorrecta"}
        )

    assert sin_clave.status_code == 401
    assert clave_mala.status_code == 401
