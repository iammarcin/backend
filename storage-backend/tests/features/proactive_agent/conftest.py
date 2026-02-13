"""Fixtures for proactive agent tests.

M4 Cleanup Note: sample_thinking_request and sample_streaming_chunk_request
fixtures have been removed as they were for legacy HTTP streaming endpoints.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from features.proactive_agent.routes import router
from features.proactive_agent.schemas import (
    AgentNotificationRequest,
    MessageDirection,
    MessageSource,
    SendMessageRequest,
)


def _build_proactive_agent_app() -> FastAPI:
    """Build a minimal FastAPI app with proactive agent routes."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def proactive_agent_client() -> TestClient:
    """Return a TestClient for proactive agent routes."""
    app = _build_proactive_agent_app()
    return TestClient(app)


@pytest.fixture
async def async_proactive_agent_client() -> AsyncGenerator[AsyncClient, None]:
    """Return an AsyncClient for proactive agent routes."""
    app = _build_proactive_agent_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def mock_repository() -> MagicMock:
    """Return a mock repository for testing."""
    repo = MagicMock()
    repo.get_or_create_session = AsyncMock()
    repo.get_session_by_id = AsyncMock()
    repo.create_message = AsyncMock()
    repo.get_messages_for_session = AsyncMock()
    repo.get_new_agent_messages = AsyncMock()
    repo.update_session_claude_id = AsyncMock()
    repo.message_to_dict = MagicMock(side_effect=lambda m, include_reasoning=True: {
        "message_id": m.message_id if hasattr(m, "message_id") else 1,
        "content": m.message if hasattr(m, "message") else "test content",
        "direction": "agent_to_user",
        "source": "text",
        "created_at": "2025-12-14T10:00:00Z",
    })
    repo.session_to_dict = MagicMock(side_effect=lambda s: {
        "id": s.session_id,
        "user_id": s.customer_id,
        "claude_session_id": getattr(s, "claude_session_id", None),
        "character_name": getattr(s, "ai_character_name", "sherlock"),
        "is_active": True,
    })
    return repo


@pytest.fixture
def mock_queue_service() -> MagicMock:
    """Return a mock SQS queue service."""
    queue = MagicMock()
    queue.enqueue_timestamped_payload = AsyncMock()
    return queue


@pytest.fixture
def mock_registry() -> MagicMock:
    """Return a mock connection registry."""
    registry = MagicMock()
    registry.push_to_user = AsyncMock(return_value=True)
    registry.get_connections = AsyncMock(return_value=[])
    registry.active_count = 1
    return registry


@pytest.fixture
def sample_session_id() -> str:
    """Return a sample session ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_user_id() -> int:
    """Return a sample user ID."""
    return 1


@pytest.fixture
def internal_api_key() -> str:
    """Return the internal API key for server-to-server endpoints.

    Reads from PROACTIVE_AGENT_INTERNAL_API_KEY environment variable.
    For tests, a test-specific key should be set in the test environment.
    """
    import os
    key = os.getenv("PROACTIVE_AGENT_INTERNAL_API_KEY")
    if not key:
        pytest.skip("PROACTIVE_AGENT_INTERNAL_API_KEY not set")
    return key


@pytest.fixture
def sample_send_message_request() -> SendMessageRequest:
    """Return a sample SendMessageRequest."""
    return SendMessageRequest(
        content="Hey Sherlock, how are you?",
        source=MessageSource.TEXT,
        ai_character_name="sherlock",
        tts_settings={
            "voice": "sherlock",
            "model": "eleven_monolingual_v1",
            "tts_auto_execute": True,
        },
    )


@pytest.fixture
def sample_notification_request(sample_user_id: int, sample_session_id: str) -> AgentNotificationRequest:
    """Return a sample AgentNotificationRequest."""
    return AgentNotificationRequest(
        user_id=sample_user_id,
        session_id=sample_session_id,
        content="Elementary! The clues are quite clear.",
        direction=MessageDirection.AGENT_TO_USER,
        source=MessageSource.TEXT,
        ai_character_name="sherlock",
    )


class MockSession:
    """Mock session object for testing."""

    def __init__(
        self,
        session_id: str,
        customer_id: int = 1,
        claude_session_id: str | None = None,
        ai_character_name: str = "sherlock",
        last_update: Any | None = None,
    ):
        self.session_id = session_id
        self.customer_id = customer_id
        self.claude_session_id = claude_session_id
        self.ai_character_name = ai_character_name
        self.last_update = last_update


class MockMessage:
    """Mock message object for testing."""

    def __init__(
        self,
        message_id: int = 1,
        session_id: str = "test-session",
        message: str = "Test message",
        sender: str = "AI",
    ):
        self.message_id = message_id
        self.session_id = session_id
        self.message = message
        self.sender = sender


@pytest.fixture
def mock_session_factory(sample_session_id: str):
    """Factory for creating mock sessions."""

    def _factory(
        session_id: str | None = None,
        customer_id: int = 1,
        claude_session_id: str | None = None,
    ) -> MockSession:
        return MockSession(
            session_id=session_id or sample_session_id,
            customer_id=customer_id,
            claude_session_id=claude_session_id,
        )

    return _factory


@pytest.fixture
def mock_message_factory():
    """Factory for creating mock messages."""

    def _factory(
        message_id: int = 1,
        session_id: str = "test-session",
        message: str = "Test message",
    ) -> MockMessage:
        return MockMessage(
            message_id=message_id,
            session_id=session_id,
            message=message,
        )

    return _factory
