from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from core.exceptions import DatabaseError, ValidationError
from features.db.ufc.dependencies import get_ufc_service, get_ufc_session
from features.db.ufc.schemas import (
    FighterList,
    FighterSubscriptionParams,
    FighterSummary,
)
from main import app


@pytest.fixture(autouse=True)
def reset_dependency_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


async def _fake_session_dependency() -> AsyncIterator[SimpleNamespace]:
    yield SimpleNamespace()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_list_fighters_endpoint_returns_subscription_payload() -> None:
    fighter = FighterSummary(
        id=7,
        name="Test Fighter",
        subscription_status="1",
    )
    service_result = FighterList(
        items=[fighter],
        total=1,
        page=1,
        page_size=10,
        has_more=False,
        search=None,
        subscriptions_enabled=True,
    )

    class StubService:
        def __init__(self) -> None:
            self.received_params: FighterSubscriptionParams | None = None

        async def list_fighters_with_subscriptions(
            self, session: Any, params: FighterSubscriptionParams
        ) -> FighterList:
            self.received_params = params
            return service_result

    service = StubService()
    app.dependency_overrides[get_ufc_service] = lambda: service
    app.dependency_overrides[get_ufc_session] = _fake_session_dependency

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/ufc/fighters",
            params={"user_id": 1, "page": 1, "page_size": 10},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["success"] is True
    assert payload["data"]["fighters"][0]["subscription_status"] == "1"
    assert payload["meta"]["total"] == 1
    assert payload["meta"]["pageSize"] == 10
    assert service.received_params is not None
    assert service.received_params.user_id == 1
    assert service.received_params.page_size == 10


@pytest.mark.anyio
async def test_list_fighters_validation_error_returns_400() -> None:
    class StubService:
        async def list_fighters_with_subscriptions(self, session: Any, params: Any) -> FighterList:
            raise ValidationError("page exceeds available fighter data", field="page")

    app.dependency_overrides[get_ufc_service] = lambda: StubService()
    app.dependency_overrides[get_ufc_session] = _fake_session_dependency

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/ufc/fighters",
            params={"user_id": 1, "page": 10, "page_size": 10},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert payload["success"] is False
    assert payload["data"]["errors"][0]["field"] == "page"


@pytest.mark.anyio
async def test_list_fighters_database_error_returns_500() -> None:
    class StubService:
        async def list_fighters_with_subscriptions(self, session: Any, params: Any) -> FighterList:
            raise DatabaseError("Failed to query fighters", operation="list_fighters")

    app.dependency_overrides[get_ufc_service] = lambda: StubService()
    app.dependency_overrides[get_ufc_session] = _fake_session_dependency

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/ufc/fighters",
            params={"user_id": 1, "page": 1, "page_size": 10},
        )

    assert response.status_code == 500
    payload = response.json()
    assert payload["code"] == 500
    assert payload["success"] is False
    assert payload["data"]["errors"][0]["field"] == "list_fighters"
