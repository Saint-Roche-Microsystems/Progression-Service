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
