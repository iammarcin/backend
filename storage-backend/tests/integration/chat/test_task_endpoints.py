"""Integration tests for task-related REST endpoints (Phase 2, Step 4)."""

from __future__ import annotations

import sys
import types
from typing import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from core.config import settings as app_settings
from dataclasses import replace

from features.chat.dependencies import get_chat_history_service, get_chat_session
from features.chat.schemas.responses import (
    ChatSessionPayload,
    SessionDetailResult,
    SessionListResult,
)
from features.chat.services.history import semantic_indexing as semantic_indexing_module
from features.semantic_search import dependencies as deps_module
from features.semantic_search import service as service_module

if "itisai_brain" not in sys.modules:
    brain_module = types.ModuleType("itisai_brain")
    text_module = types.ModuleType("itisai_brain.text")

    def _stub_prompt_template(*args, **kwargs):  # pragma: no cover - simple stub
        return ""

    text_module.getTextPromptTemplate = _stub_prompt_template  # type: ignore[attr-defined]
    brain_module.text = text_module
    sys.modules["itisai_brain"] = brain_module
    sys.modules["itisai_brain.text"] = text_module

from main import app


def _patch_settings(monkeypatch, **overrides):
    """Patch settings in relevant modules."""
    patched = replace(app_settings, **overrides)
    monkeypatch.setattr(deps_module, "settings", patched)
    monkeypatch.setattr(service_module, "settings", patched)
    monkeypatch.setattr(semantic_indexing_module, "settings", patched)


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def disable_semantic_search(monkeypatch) -> None:
    """Disable semantic search for integration tests."""
    _patch_settings(monkeypatch, semantic_search_enabled=False)
    monkeypatch.setattr(service_module, "_service_instance", None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def auth_token_customer_1(auth_token_factory):
    return auth_token_factory(customer_id=1)


# ---------------------------------------------------------------------------
# Create task endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_task_endpoint_returns_session_with_task_fields(
    auth_token_customer_1: str,
) -> None:
    """Verify create-task endpoint returns a session with task metadata."""

    class StubService:
        async def create_task(self, request):
            return SessionDetailResult(
                session=ChatSessionPayload(
                    session_id="task-001",
                    customer_id=1,
                    session_name=request.task_description,
                    ai_character_name=request.ai_character_name,
                    task_status="active",
                    task_priority=request.task_priority,
                    task_description=request.task_description,
                )
            )

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        response = await client.post(
            "/api/v1/chat/sessions/create-task",
            json={
                "customer_id": 1,
                "ai_character_name": "sherlock",
                "task_description": "Investigate the anomaly",
                "task_priority": "high",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["session_id"] == "task-001"
    assert data["task_status"] == "active"
    assert data["task_priority"] == "high"
    assert data["task_description"] == "Investigate the anomaly"
    assert data["ai_character_name"] == "sherlock"


@pytest.mark.anyio
async def test_create_task_endpoint_default_priority(
    auth_token_customer_1: str,
) -> None:
    """Verify create-task uses default priority 'medium' when not specified."""

    captured_requests = []

    class CapturingService:
        async def create_task(self, request):
            captured_requests.append(request)
            return SessionDetailResult(
                session=ChatSessionPayload(
                    session_id="task-002",
                    customer_id=1,
                    session_name="Test task",
                    ai_character_name="sherlock",
                    task_status="active",
                    task_priority="medium",
                    task_description="Test task",
                )
            )

    app.dependency_overrides[get_chat_history_service] = lambda: CapturingService()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        await client.post(
            "/api/v1/chat/sessions/create-task",
            json={
                "customer_id": 1,
                "ai_character_name": "sherlock",
                "task_description": "Test task",
            },
        )

    assert len(captured_requests) == 1
    assert captured_requests[0].task_priority == "medium"


@pytest.mark.anyio
async def test_create_task_endpoint_rejects_mismatched_customer(
    auth_token_customer_1: str,
) -> None:
    """Verify 403 when customer_id doesn't match the auth token."""

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        response = await client.post(
            "/api/v1/chat/sessions/create-task",
            json={
                "customer_id": 999,
                "ai_character_name": "sherlock",
                "task_description": "Task",
            },
        )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Session list with task_status filter tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_sessions_task_status_filter_passes_to_service(
    auth_token_customer_1: str,
) -> None:
    """Verify that task_status filter is passed through to the service."""

    captured_requests = []

    class CapturingService:
        async def list_sessions(self, request):
            captured_requests.append(request)
            return SessionListResult(sessions=[], count=0)

    app.dependency_overrides[get_chat_history_service] = lambda: CapturingService()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        # Test 'any' filter
        await client.post(
            "/api/v1/chat/sessions/list",
            json={"customer_id": 1, "task_status": "any"},
        )

        # Test 'none' filter
        await client.post(
            "/api/v1/chat/sessions/list",
            json={"customer_id": 1, "task_status": "none"},
        )

        # Test exact status filter
        await client.post(
            "/api/v1/chat/sessions/list",
            json={"customer_id": 1, "task_status": "active"},
        )

    assert len(captured_requests) == 3
    assert captured_requests[0].task_status == "any"
    assert captured_requests[1].task_status == "none"
    assert captured_requests[2].task_status == "active"


@pytest.mark.anyio
async def test_list_sessions_invalid_task_status_rejected(
    auth_token_customer_1: str,
) -> None:
    """Verify that invalid task_status values are rejected by validation."""

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        response = await client.post(
            "/api/v1/chat/sessions/list",
            json={"customer_id": 1, "task_status": "invalid"},
        )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH session with task fields tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_patch_session_with_task_fields(
    auth_token_customer_1: str,
) -> None:
    """Verify PATCH passes task fields through to the service."""

    captured_requests = []

    class CapturingService:
        async def update_session(self, request):
            captured_requests.append(request)
            return SessionDetailResult(
                session=ChatSessionPayload(
                    session_id="sess-1",
                    customer_id=1,
                    task_status=request.task_status,
                    task_priority=request.task_priority,
                    task_description=request.task_description,
                )
            )

    app.dependency_overrides[get_chat_history_service] = lambda: CapturingService()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        response = await client.patch(
            "/api/v1/chat/sessions",
            json={
                "customer_id": 1,
                "session_id": "sess-1",
                "task_status": "waiting",
                "task_priority": "low",
                "task_description": "Updated description",
            },
        )

    assert response.status_code == 200
    assert len(captured_requests) == 1
    assert captured_requests[0].task_status == "waiting"
    assert captured_requests[0].task_priority == "low"
    assert captured_requests[0].task_description == "Updated description"


# ---------------------------------------------------------------------------
# Agent status with real active_task_count
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_agent_status_with_active_task_count(
    auth_token_customer_1: str,
) -> None:
    """Verify the agent status endpoint returns real active_task_count."""

    from unittest.mock import AsyncMock, MagicMock
    from datetime import datetime, timezone

    last_activity = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    mock_row = MagicMock()
    mock_row.name = "sherlock"
    mock_row.session_count = 5
    mock_row.active_task_count = 3
    mock_row.last_activity = last_activity

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    async def _mock_get_chat_session():
        return mock_session

    app.dependency_overrides[get_chat_session] = _mock_get_chat_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        response = await client.get(
            "/api/v1/agents/status",
            params={"customer_id": 1},
        )

    assert response.status_code == 200
    agents = response.json()["agents"]
    assert len(agents) == 1
    assert agents[0]["name"] == "sherlock"
    assert agents[0]["active_task_count"] == 3
    assert agents[0]["session_count"] == 5


@pytest.mark.anyio
async def test_agent_status_null_active_task_count_defaults_to_zero(
    auth_token_customer_1: str,
) -> None:
    """Verify active_task_count defaults to 0 when NULL (no tasks)."""

    from unittest.mock import AsyncMock, MagicMock

    mock_row = MagicMock()
    mock_row.name = "bugsy"
    mock_row.session_count = 2
    mock_row.active_task_count = None  # No tasks at all
    mock_row.last_activity = None

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    async def _mock_get_chat_session():
        return mock_session

    app.dependency_overrides[get_chat_session] = _mock_get_chat_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        response = await client.get(
            "/api/v1/agents/status",
            params={"customer_id": 1},
        )

    assert response.status_code == 200
    agents = response.json()["agents"]
    assert len(agents) == 1
    assert agents[0]["active_task_count"] == 0
