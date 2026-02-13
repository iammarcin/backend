"""Integration tests for chat history REST endpoints."""

from __future__ import annotations
from dataclasses import replace

from typing import Iterator

import sys
import types

import pytest
from httpx import ASGITransport, AsyncClient

from core.config import settings as app_settings
from core.exceptions import ValidationError
from features.chat.dependencies import get_chat_history_service
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

from features.chat.schemas.responses import (
    ChatSessionPayload,
    MessageWritePayload,
    MessageWriteResult,
)
from main import app


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def _patch_settings(monkeypatch, **overrides):
    """Patch settings in relevant modules."""
    patched = replace(app_settings, **overrides)
    monkeypatch.setattr(deps_module, "settings", patched)
    monkeypatch.setattr(service_module, "settings", patched)
    monkeypatch.setattr(semantic_indexing_module, "settings", patched)


@pytest.fixture(autouse=True)
def disable_semantic_search(monkeypatch) -> None:
    """Disable semantic search for integration tests."""
    _patch_settings(monkeypatch, semantic_search_enabled=False)
    # Also clear any cached service instance
    monkeypatch.setattr(service_module, "_service_instance", None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def auth_token_customer_7(auth_token_factory):
    """Create auth token with customer_id=7."""
    return auth_token_factory(customer_id=7)


@pytest.fixture
def auth_token_customer_9(auth_token_factory):
    """Create auth token with customer_id=9."""
    return auth_token_factory(customer_id=9)


@pytest.mark.anyio
async def test_create_message_endpoint_returns_envelope(auth_token_customer_7: str) -> None:
    class StubService:
        async def create_message(self, request):
            return MessageWritePayload(
                messages=MessageWriteResult(
                    user_message_id=1,
                    ai_message_id=2,
                    session_id="abc",
                ),
                session=None,
            )

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.headers.update({"Authorization": f"Bearer {auth_token_customer_7}"})
        response = await client.post(
            "/api/v1/chat/messages",
            json={
                "customer_id": 7,
                "user_message": {"message": "hello"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["message"], str)
    assert payload["data"]["user_message_id"] == 1
    assert "session" not in payload["data"]


@pytest.mark.anyio
async def test_create_message_endpoint_handles_validation_error(auth_token_customer_7: str) -> None:
    class FailingService:
        async def create_message(self, request):
            raise ValidationError("session missing", field="session_id")

    app.dependency_overrides[get_chat_history_service] = lambda: FailingService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.headers.update({"Authorization": f"Bearer {auth_token_customer_7}"})
        response = await client.post(
            "/api/v1/chat/messages",
            json={
                "customer_id": 7,
                "user_message": {"message": "hello"},
            },
        )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert isinstance(body["message"], str)
    assert body["data"]["field"] == "session_id"


@pytest.mark.anyio
async def test_create_message_endpoint_includes_session_payload(auth_token_customer_9: str) -> None:
    class StubService:
        async def create_message(self, request):
            return MessageWritePayload(
                messages=MessageWriteResult(
                    user_message_id=3,
                    ai_message_id=None,
                    session_id="sess-123",
                ),
                session=ChatSessionPayload(
                    session_id="sess-123",
                    customer_id=9,
                    session_name="Test session",
                ),
            )

    app.dependency_overrides[get_chat_history_service] = lambda: StubService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.headers.update({"Authorization": f"Bearer {auth_token_customer_9}"})
        response = await client.post(
            "/api/v1/chat/messages",
            json={
                "customer_id": 9,
                "user_message": {"message": "hello"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["user_message_id"] == 3
    assert payload["data"]["session"]["session_id"] == "sess-123"
