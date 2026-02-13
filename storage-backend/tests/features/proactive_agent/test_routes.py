"""Integration tests for proactive agent HTTP routes.

M4 Cleanup Note: Tests for /thinking and /stream endpoints have been removed
as those endpoints were part of the legacy HTTP streaming architecture.
The Python poller now uses WebSocket streaming via /ws/poller-stream.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from features.proactive_agent.dependencies import get_proactive_agent_repository
from features.proactive_agent.routes import router

from .conftest import MockMessage, MockSession


def _build_test_app(mock_repository: MagicMock = None) -> FastAPI:
    """Build a minimal FastAPI app with proactive agent routes."""
    app = FastAPI()
    app.include_router(router)

    if mock_repository:
        app.dependency_overrides[get_proactive_agent_repository] = lambda: mock_repository

    return app


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, mock_registry: MagicMock):
        """Test health endpoint returns status."""
        app = _build_test_app()
        mock_registry.active_count = 5

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            with patch(
                "core.connections.get_proactive_registry",
                return_value=mock_registry,
            ):
                response = await client.get("/api/v1/proactive-agent/health")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"
        assert data["data"]["character"] == "sherlock"
        assert data["data"]["active_ws_connections"] == 5


class TestSessionEndpoint:
    """Tests for /session endpoint."""

    @pytest.mark.asyncio
    async def test_get_or_create_session(self, mock_repository: MagicMock):
        """Test getting or creating a session."""
        session = MockSession(session_id="test-session-123", customer_id=1)
        mock_repository.get_or_create_session = AsyncMock(return_value=session)
        mock_repository.get_messages_for_session = AsyncMock(return_value=([], 0))
        mock_repository.session_to_dict = MagicMock(
            return_value={
                "session_id": session.session_id,
                "user_id": session.customer_id,
                "claude_session_id": None,
                "ai_character_name": "sherlock",
                "is_active": True,
            }
        )

        app = _build_test_app(mock_repository)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/proactive-agent/session",
                params={"user_id": 1},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["session_id"] == "test-session-123"


class TestNotificationsEndpoint:
    """Tests for /notifications endpoint (server-to-server).

    This endpoint is still active - used by the heartbeat script.
    """

    @pytest.mark.asyncio
    async def test_receive_notification_without_api_key(self):
        """Test that notification without API key is rejected."""
        app = _build_test_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/proactive-agent/notifications",
                json={
                    "user_id": 1,
                    "session_id": "abc-123",
                    "content": "Test notification",
                },
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_receive_notification_with_invalid_api_key(self):
        """Test that notification with invalid API key is rejected."""
        app = _build_test_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/proactive-agent/notifications",
                headers={"X-Internal-Api-Key": "wrong-key"},
                json={
                    "user_id": 1,
                    "session_id": "abc-123",
                    "content": "Test notification",
                },
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_receive_notification_with_valid_api_key(
        self, mock_repository: MagicMock, mock_registry: MagicMock
    ):
        """Test successful notification with valid API key."""
        session = MockSession(session_id="abc-123", customer_id=1)
        message = MockMessage(message_id=1, session_id="abc-123")

        mock_repository.get_session_by_id = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)

        app = _build_test_app(mock_repository)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            with patch(
                "features.proactive_agent.utils.websocket_push.get_proactive_registry",
                return_value=mock_registry,
            ):
                # Use the configured internal API key from environment
                import os
                api_key = os.getenv("PROACTIVE_AGENT_INTERNAL_API_KEY", "")
                response = await client.post(
                    "/api/v1/proactive-agent/notifications",
                    headers={"X-Internal-Api-Key": api_key},
                    json={
                        "user_id": 1,
                        "session_id": "abc-123",
                        "content": "Elementary!",
                        "direction": "agent_to_user",
                        "source": "text",
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["stored"] is True
