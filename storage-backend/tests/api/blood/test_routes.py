from __future__ import annotations

from datetime import date
from typing import Any, AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from core.exceptions import DatabaseError
from features.db.blood.dependencies import get_blood_service, get_blood_session
from features.db.blood.schemas import (
    BloodTestFilterParams,
    BloodTestItem,
    BloodTestListResponse,
)
from main import app


@pytest.fixture(autouse=True)
def reset_dependency_overrides() -> Iterator[None]:
    """Ensure dependency overrides do not leak between tests."""

    try:
        yield
    finally:
        app.dependency_overrides.clear()


async def _fake_session_dependency() -> AsyncIterator[Any]:
    yield object()


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio event loop for pytest-anyio tests."""

    return "asyncio"


@pytest.mark.anyio
async def test_list_blood_tests_returns_envelope() -> None:
    class StubService:
        def __init__(self) -> None:
            self.received_filters: BloodTestFilterParams | None = None

        async def list_tests(
            self,
            session: Any,
            filters: BloodTestFilterParams | None = None,
        ) -> BloodTestListResponse:
            self.received_filters = filters
            item = BloodTestItem(
                id=1,
                test_definition_id=10,
                test_date=date(2024, 5, 1),
                result_value="5.6",
                result_unit="mmol/L",
                reference_range="4.0-6.0",
                category="Metabolic",
                test_name="Glucose",
                short_explanation="Fasting glucose",
                long_explanation=None,
            )
            return BloodTestListResponse(
                items=[item],
                total_count=1,
                latest_test_date=date(2024, 5, 1),
                filters=filters,
            )

    service = StubService()
    app.dependency_overrides[get_blood_service] = lambda: service
    app.dependency_overrides[get_blood_session] = _fake_session_dependency

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/blood/tests",
            params={
                "start_date": "2024-04-01",
                "end_date": "2024-06-01",
                "category": "Metabolic",
                "limit": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["success"] is True
    assert payload["data"]["items"][0]["test_date"] == "2024-05-01"
    assert payload["meta"]["total_count"] == 1
    assert payload["meta"]["filters"]["limit"] == 5
    assert service.received_filters is not None
    assert service.received_filters.limit == 5
    assert service.received_filters.start_date.isoformat() == "2024-04-01"


@pytest.mark.anyio
async def test_list_blood_tests_handles_database_error() -> None:
    class FailingService:
        async def list_tests(self, session: Any, filters: Any = None) -> None:
            raise DatabaseError("boom", operation="blood.tests.list")

    app.dependency_overrides[get_blood_service] = lambda: FailingService()
    app.dependency_overrides[get_blood_session] = _fake_session_dependency

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/blood/tests")

    assert response.status_code == 500
    payload = response.json()
    assert payload["code"] == 500
    assert payload["success"] is False
    assert payload["message"].lower().startswith("database error")


@pytest.mark.anyio
async def test_legacy_endpoint_returns_legacy_contract() -> None:
    class LegacyService:
        async def list_tests(
            self, session: Any, filters: BloodTestFilterParams | None = None
        ) -> BloodTestListResponse:
            item = BloodTestItem(
                id=7,
                test_definition_id=21,
                test_date=date(2023, 12, 31),
                result_value="12.2",
                result_unit="g/dL",
                reference_range="12-17",
                category="Haematology",
                test_name="Haemoglobin",
                short_explanation="Red blood cell concentration",
                long_explanation=None,
            )
            return BloodTestListResponse(
                items=[item],
                total_count=1,
                latest_test_date=date(2023, 12, 31),
                filters=None,
            )

    app.dependency_overrides[get_blood_service] = lambda: LegacyService()
    app.dependency_overrides[get_blood_session] = _fake_session_dependency

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/blood/legacy",
            json={"action": "get_all_blood_tests", "customer_id": 3},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["success"] is True
    assert payload["message"]["status"] == "completed"
    legacy_item = payload["message"]["result"][0]
    assert legacy_item["test_date"] == "2023-12-31"
    assert "test_definition_id" not in legacy_item


@pytest.mark.anyio
async def test_legacy_endpoint_rejects_unknown_action() -> None:
    app.dependency_overrides[get_blood_session] = _fake_session_dependency

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/blood/legacy",
            json={"action": "unsupported_action"},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert payload["success"] is False
    assert payload["message"]["status"] == "fail"
