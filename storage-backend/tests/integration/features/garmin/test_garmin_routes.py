from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient

from fastapi import status
from core.utils.env import is_production
from features.garmin.service import DatasetResult
from main import app

from features.garmin.dependencies import (
    get_garmin_provider_service,
    get_garmin_service,
    get_garmin_session,
)

pytestmark = [
    pytest.mark.requires_docker,
    pytest.mark.skipif(
        not is_production(),
        reason="Garmin router is only loaded in production configuration",
    ),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class StubGarminService:
    payload: dict[str, object]

    async def fetch_analysis(self, session, query, customer_id, datasets=None, include_optimized=True):
        return dict(self.payload)

    def default_analysis_datasets(self):
        return ("sleep", "summary")


class StubProviderService:
    def __init__(self) -> None:
        self.metadata = {
            "display_name": "tester",
            "full_name": "Test User",
            "unit_system": "metric",
            "session_path": "/tmp/garmin_session.json",
            "domain": "connect.garmin.com",
            "save_to_db_default": False,
            "available_datasets": ["sleep", "summary"],
        }
        self.results: dict[str, DatasetResult] = {
            "sleep": DatasetResult(
                dataset="sleep",
                items=[{"calendar_date": "2024-07-01T00:00:00", "sleep_time_seconds": 25200}],
                raw=[{"mock": "sleep"}],
                ingested=[],
                saved=False,
            ),
            "summary": DatasetResult(
                dataset="summary",
                items=[{"calendar_date": "2024-07-01T00:00:00", "total_steps": 1000}],
                raw=[{"mock": "summary"}],
                ingested=[],
                saved=False,
            ),
        }

    def status(self) -> dict[str, object]:
        return dict(self.metadata)

    async def fetch_dataset(self, dataset, query, *, customer_id, save_to_db=None, session=None):
        return self.results[dataset]


@asynccontextmanager
async def _disabled_session():
    yield None


@asynccontextmanager
async def _session_override():
    yield object()


@pytest.mark.anyio
async def test_status_endpoint_returns_metadata() -> None:
    stub_provider = StubProviderService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        app.dependency_overrides[get_garmin_provider_service] = lambda: stub_provider
        response = await client.get("/api/v1/garmin/status")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["display_name"] == "tester"


@pytest.mark.anyio
async def test_sleep_endpoint_returns_items() -> None:
    stub_provider = StubProviderService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        app.dependency_overrides[get_garmin_provider_service] = lambda: stub_provider
        app.dependency_overrides[get_garmin_session] = _session_override
        response = await client.get(
            "/api/v1/garmin/sleep",
            params={"customer_id": 1, "start_date": "2024-07-01", "end_date": "2024-07-01"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["sleep_time_seconds"] == 25200


@pytest.mark.anyio
async def test_summary_endpoint_returns_items() -> None:
    stub_provider = StubProviderService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        app.dependency_overrides[get_garmin_provider_service] = lambda: stub_provider
        app.dependency_overrides[get_garmin_session] = _session_override
        response = await client.get(
            "/api/v1/garmin/summary",
            params={"customer_id": 2, "start_date": "2024-07-01"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["items"][0]["total_steps"] == 1000


@pytest.mark.anyio
async def test_sleep_endpoint_returns_disabled_error() -> None:
    stub_provider = StubProviderService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        app.dependency_overrides[get_garmin_provider_service] = lambda: stub_provider
        app.dependency_overrides[get_garmin_session] = _disabled_session
        response = await client.get(
            "/api/v1/garmin/sleep",
            params={"customer_id": 3, "start_date": "2024-07-01"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    payload = response.json()
    assert payload["code"] == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Garmin features are disabled" in payload["message"]


@pytest.mark.anyio
async def test_analysis_endpoint_uses_garmin_service() -> None:
    stub_provider = StubProviderService()
    stub_garmin_service = StubGarminService(payload={"datasets": {"sleep": []}})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        app.dependency_overrides[get_garmin_provider_service] = lambda: stub_provider
        app.dependency_overrides[get_garmin_service] = lambda: stub_garmin_service

        app.dependency_overrides[get_garmin_session] = _session_override

        response = await client.get(
            "/api/v1/garmin/analysis/overview",
            params={"customer_id": 1},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "datasets" in payload["data"]
