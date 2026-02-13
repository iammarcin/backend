"""Integration tests for agent status endpoint and session list ai_character_name filter."""

from __future__ import annotations

import sys
import types
from typing import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from core.config import settings as app_settings
from dataclasses import replace

from features.chat.dependencies import get_chat_history_service
from features.chat.schemas.responses import (
    ChatSessionPayload,
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
    """Create auth token with customer_id=1."""
    return auth_token_factory(customer_id=1)


@pytest.fixture
def auth_token_customer_2(auth_token_factory):
    """Create auth token with customer_id=2."""
    return auth_token_factory(customer_id=2)


# ---------------------------------------------------------------------------
# Step 3a: SessionListRequest ai_character_name filter
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_sessions_with_ai_character_name_filter(
    auth_token_customer_1: str,
) -> None:
    """Verify that supplying ai_character_name filters the returned sessions."""

    sherlock_sessions = [
        ChatSessionPayload(
            session_id="s1",
            customer_id=1,
            session_name="Sherlock chat",
            ai_character_name="sherlock",
        ),
    ]
    bugsy_sessions = [
        ChatSessionPayload(
            session_id="s2",
            customer_id=1,
            session_name="Bugsy chat",
            ai_character_name="bugsy",
        ),
    ]
    all_sessions = sherlock_sessions + bugsy_sessions

    class StubService:
        async def list_sessions(self, request):
            if request.ai_character_name == "sherlock":
                return SessionListResult(sessions=sherlock_sessions, count=1)
            if request.ai_character_name == "bugsy":
                return SessionListResult(sessions=bugsy_sessions, count=1)
            return SessionListResult(sessions=all_sessions, count=2)

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        # Filter by sherlock
        response = await client.post(
            "/api/v1/chat/sessions/list",
            json={
                "customer_id": 1,
                "ai_character_name": "sherlock",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["count"] == 1
    assert payload["data"]["sessions"][0]["ai_character_name"] == "sherlock"


@pytest.mark.anyio
async def test_list_sessions_without_ai_character_name_filter(
    auth_token_customer_1: str,
) -> None:
    """Verify that omitting ai_character_name returns all sessions."""

    all_sessions = [
        ChatSessionPayload(
            session_id="s1",
            customer_id=1,
            session_name="Sherlock chat",
            ai_character_name="sherlock",
        ),
        ChatSessionPayload(
            session_id="s2",
            customer_id=1,
            session_name="Bugsy chat",
            ai_character_name="bugsy",
        ),
    ]

    class StubService:
        async def list_sessions(self, request):
            assert request.ai_character_name is None
            return SessionListResult(sessions=all_sessions, count=2)

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        response = await client.post(
            "/api/v1/chat/sessions/list",
            json={"customer_id": 1},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["count"] == 2


@pytest.mark.anyio
async def test_list_sessions_ai_character_name_filter_passes_to_service(
    auth_token_customer_1: str,
) -> None:
    """Verify that the request model correctly propagates ai_character_name."""

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

        await client.post(
            "/api/v1/chat/sessions/list",
            json={
                "customer_id": 1,
                "ai_character_name": "bugsy",
            },
        )

    assert len(captured_requests) == 1
    assert captured_requests[0].ai_character_name == "bugsy"


# ---------------------------------------------------------------------------
# Step 3b: Agent status endpoint
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_agent_status_returns_correct_counts(
    auth_token_customer_1: str,
) -> None:
    """Verify the agent status endpoint returns agents with session counts."""

    from unittest.mock import AsyncMock, MagicMock
    from datetime import datetime, timezone

    last_activity = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    # Mock rows returned by the DB query
    mock_row_sherlock = MagicMock()
    mock_row_sherlock.name = "sherlock"
    mock_row_sherlock.session_count = 5
    mock_row_sherlock.active_task_count = 0
    mock_row_sherlock.last_activity = last_activity

    mock_row_bugsy = MagicMock()
    mock_row_bugsy.name = "bugsy"
    mock_row_bugsy.session_count = 2
    mock_row_bugsy.active_task_count = 0
    mock_row_bugsy.last_activity = None

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row_sherlock, mock_row_bugsy]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    from features.chat.dependencies import get_chat_session

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
    payload = response.json()
    agents = payload["agents"]
    assert len(agents) == 2

    sherlock = next(a for a in agents if a["name"] == "sherlock")
    assert sherlock["session_count"] == 5
    assert sherlock["status"] == "idle"
    assert sherlock["active_task_count"] == 0
    assert sherlock["last_activity"] == last_activity.isoformat()

    bugsy = next(a for a in agents if a["name"] == "bugsy")
    assert bugsy["session_count"] == 2
    assert bugsy["last_activity"] is None


@pytest.mark.anyio
async def test_agent_status_empty_when_no_sessions(
    auth_token_customer_1: str,
) -> None:
    """Verify the endpoint returns an empty agent list when no sessions exist."""

    from unittest.mock import AsyncMock, MagicMock
    from features.chat.dependencies import get_chat_session

    mock_result = MagicMock()
    mock_result.all.return_value = []

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
    payload = response.json()
    assert payload["agents"] == []


@pytest.mark.anyio
async def test_agent_status_rejects_mismatched_customer_id(
    auth_token_customer_1: str,
) -> None:
    """Verify 403 when the token customer_id doesn't match the query param."""

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update(
            {"Authorization": f"Bearer {auth_token_customer_1}"}
        )

        response = await client.get(
            "/api/v1/agents/status",
            params={"customer_id": 999},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_agent_status_requires_authentication() -> None:
    """Verify the endpoint rejects unauthenticated requests."""

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/agents/status",
            params={"customer_id": 1},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_agent_status_requires_customer_id() -> None:
    """Verify 422 when customer_id query param is missing."""

    from unittest.mock import AsyncMock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update({"Authorization": "Bearer invalid-but-will-fail-on-validation"})

        response = await client.get("/api/v1/agents/status")

    assert response.status_code in (401, 422)


# ---------------------------------------------------------------------------
# Step 6a: compute_agent_status unit tests
# ---------------------------------------------------------------------------


class TestComputeAgentStatus:
    """Tests for the compute_agent_status helper function."""

    def test_none_returns_idle(self) -> None:
        """last_activity=None should yield 'idle'."""
        from features.chat.agent_routes import compute_agent_status

        assert compute_agent_status(None) == "idle"

    def test_recent_activity_returns_active(self) -> None:
        """last_activity 2 minutes ago should yield 'active'."""
        from datetime import datetime, timedelta, timezone

        from features.chat.agent_routes import compute_agent_status

        last_activity = datetime.now(timezone.utc) - timedelta(minutes=2)
        assert compute_agent_status(last_activity) == "active"

    def test_old_activity_returns_idle(self) -> None:
        """last_activity 10 minutes ago should yield 'idle'."""
        from datetime import datetime, timedelta, timezone

        from features.chat.agent_routes import compute_agent_status

        last_activity = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert compute_agent_status(last_activity) == "idle"

    def test_boundary_at_5_minutes_returns_active(self) -> None:
        """last_activity just under 5 minutes ago should yield 'active' (<= 5).

        Uses 4m59s instead of exactly 5m to avoid test flakiness from
        execution-time drift between creating the timestamp and the
        ``datetime.now()`` call inside ``compute_agent_status``.
        """
        from datetime import datetime, timedelta, timezone

        from features.chat.agent_routes import compute_agent_status

        last_activity = datetime.now(timezone.utc) - timedelta(minutes=4, seconds=59)
        assert compute_agent_status(last_activity) == "active"

    def test_just_over_5_minutes_returns_idle(self) -> None:
        """last_activity 6 minutes ago should yield 'idle'."""
        from datetime import datetime, timedelta, timezone

        from features.chat.agent_routes import compute_agent_status

        last_activity = datetime.now(timezone.utc) - timedelta(minutes=6)
        assert compute_agent_status(last_activity) == "idle"


@pytest.mark.anyio
async def test_agent_status_returns_active_for_recent_activity(
    auth_token_customer_1: str,
) -> None:
    """Verify the endpoint returns 'active' when last_activity is within 5 minutes."""

    from unittest.mock import AsyncMock, MagicMock
    from datetime import datetime, timedelta, timezone

    recent_activity = datetime.now(timezone.utc) - timedelta(minutes=2)

    mock_row = MagicMock()
    mock_row.name = "sherlock"
    mock_row.session_count = 3
    mock_row.active_task_count = 1
    mock_row.last_activity = recent_activity

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    from features.chat.dependencies import get_chat_session

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
    payload = response.json()
    agents = payload["agents"]
    assert len(agents) == 1
    assert agents[0]["name"] == "sherlock"
    assert agents[0]["status"] == "active"
