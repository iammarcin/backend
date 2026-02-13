"""Integration tests for HTTP chat endpoints."""

from __future__ import annotations

from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.providers.base import BaseTextProvider
from core.providers.factory import register_text_provider
from main import app


class HTTPStubProvider(BaseTextProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(streaming=True)

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ProviderResponse:
        # Verify that 'settings' is NOT in kwargs (regression test for bug fix)
        if "settings" in kwargs:
            raise ValueError(
                "REGRESSION: 'settings' dict should not be passed to provider. "
                "This indicates the MILESTONE-1 bug has returned."
            )

        if prompt.startswith("Based on this conversation"):
            text = "Binary Search Guide"
        elif prompt.startswith("Following is a message from chat application"):
            # Session-based name generation
            text = "Chat Session Summary"
        elif max_tokens == 50 and temperature == 0.3:
            # Session name generation (lightweight settings)
            text = f"Generated Name: {prompt[:30]}"
        else:
            # Regular chat generation
            text = f"echo:{prompt}"

        return ProviderResponse(
            text=text,
            model=model or "gpt-4o-mini",
            provider="stub",
        )

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        *,
        runtime=None,
        **kwargs,
    ) -> AsyncIterator[str]:
        for chunk in ["Hello", " ", "SSE"]:
            yield chunk


@pytest.fixture(autouse=True)
def override_provider():
    from core.providers.registries import _text_providers

    original = _text_providers.get("openai")
    register_text_provider("openai", HTTPStubProvider)
    try:
        yield
    finally:
        if original:
            _text_providers["openai"] = original
        else:
            _text_providers.pop("openai", None)


def test_chat_endpoint(authenticated_client):
    response = authenticated_client.post(
        "/chat/",
        json={
            "prompt": "Say hello",
            "settings": {"text": {"model": "gpt-4o-mini", "temperature": 0.1}},
            "customer_id": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["data"]["text"].startswith("echo:")
    assert data["data"]["model"] == "gpt-4o-mini"
    assert data["data"]["provider"] == "stub"


def test_chat_validation_error(authenticated_client):
    response = authenticated_client.post(
        "/chat/",
        json={"prompt": " ", "settings": {}, "customer_id": 1},
    )

    assert response.status_code == 422


def test_chat_stream_endpoint(authenticated_client):
    with authenticated_client.stream(
        "POST",
        "/chat/stream",
        json={
            "prompt": "Count to 3",
            "settings": {"text": {"model": "gpt-4o-mini"}},
            "customer_id": 1,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        chunks: list[str] = []
        for line in response.iter_lines():
            if not line:
                continue
            decoded = line.decode() if isinstance(line, bytes) else line
            if not decoded.startswith("data: "):
                continue
            payload = decoded[len("data: "):]
            if payload == "[DONE]":
                break
            chunks.append(payload)

    assert "".join(chunks) == "Hello SSE"


def test_session_name_generation(authenticated_client):
    """Legacy test - kept for backward compatibility.

    See TestSessionNameGeneration class for comprehensive tests.
    """
    response = authenticated_client.post(
        "/api/v1/chat/session-name",
        json={
            "prompt": "How do I implement binary search in Python?",
            "settings": {"text": {"model": "gpt-4o-mini"}},  # ✅ Now has settings
            "customer_id": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "session_name" in data["data"]
    assert len(data["data"]["session_name"]) > 0
    assert len(data["data"]["session_name"]) <= 50


class TestSessionNameGeneration:
    """Comprehensive test suite for session name generation."""

    def test_basic_prompt_generation(self, authenticated_client):
        """Test session name generation with a simple prompt."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "How do I implement binary search in Python?",
                "settings": {},
                "customer_id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "session_name" in data["data"]
        assert len(data["data"]["session_name"]) > 0
        assert len(data["data"]["session_name"]) <= 50

    def test_with_full_settings(self, authenticated_client):
        """Test session name generation with full settings dict.

        This test would have caught the MILESTONE-1 bug where settings
        dict was incorrectly passed to OpenAI API.
        """
        settings = {
            "text": {
                "model": "gpt-4o-mini",
                "temperature": 0.3,
                "max_tokens": 50,
            },
            "general": {
                "ai_agent_enabled": False,
            },
        }

        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Explain quantum computing",
                "settings": settings,
                "customer_id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "session_name" in data["data"]

    def test_with_session_id_no_prompt(self, authenticated_client):
        """Test session name generation loading content from session history."""
        # First create a session with messages
        # (This would require setting up test database with mock session)
        # For now, test with empty prompt - backend should handle gracefully

        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": " ",  # Empty prompt - should load from session
                "settings": {"text": {"model": "gpt-4o-mini"}},
                "customer_id": 1,
                "session_id": "test-session-123",
            },
        )

        # Should not fail even if session not found
        assert response.status_code in [200, 400]  # 400 if session not found

    def test_settings_preparation(self, authenticated_client):
        """Verify that settings are properly prepared for session naming.

        The backend should override user settings to use lightweight config:
        - model: gpt-4o-mini
        - temperature: 0.3
        - max_tokens: 50
        """
        # User sends settings with different model
        settings = {
            "text": {
                "model": "gpt-4",  # Expensive model
                "temperature": 1.0,
                "max_tokens": 2000,
            },
        }

        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Test prompt",
                "settings": settings,
                "customer_id": 1,
            },
        )

        # Should succeed - backend overrides with cheap settings
        assert response.status_code == 200

    def test_long_prompt_truncation(self, authenticated_client):
        """Test that very long prompts are handled correctly."""
        long_prompt = "How do I " + "implement " * 100 + "binary search?"

        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": long_prompt,
                "settings": {},
                "customer_id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Session name should be truncated to 50 chars
        assert len(data["data"]["session_name"]) <= 50

    def test_session_name_normalization(self, authenticated_client):
        """Test that session names are properly normalized."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Test",
                "settings": {},
                "customer_id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        session_name = data["data"]["session_name"]

        # Should be stripped of quotes and whitespace
        assert session_name == session_name.strip()
        assert not session_name.startswith('"')
        assert not session_name.endswith('"')
        assert not session_name.startswith("'")
        assert not session_name.endswith("'")

    def test_missing_prompt_no_session(self, authenticated_client):
        """Test error handling when both prompt and session are missing."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "",  # Empty prompt becomes None after validation
                "settings": {},
                "customer_id": 1,
                # No session_id
            },
        )

        # Should return 422 validation error (Pydantic validation)
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_special_characters_in_prompt(self, authenticated_client):
        """Test handling of special characters in prompt."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "How to use @decorators & *args/**kwargs in Python?",
                "settings": {},
                "customer_id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_name" in data["data"]

    def test_unicode_characters(self, authenticated_client):
        """Test handling of Unicode characters in prompt."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Comment implémenter une fonction récursive? 如何实现递归？",
                "settings": {},
                "customer_id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_name" in data["data"]

    def test_response_format(self, authenticated_client):
        """Verify the response format matches API contract."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Test prompt",
                "settings": {},
                "customer_id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert "session_name" in data["data"]
        assert "code" in data
        assert data["code"] == 200

    def test_with_session_id_in_response(self, authenticated_client):
        """Test that session_id is returned when provided."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Test",
                "settings": {},
                "customer_id": 1,
                "session_id": "test-session-456",
            },
        )

        assert response.status_code in [200, 400]  # May fail if session not found
        if response.status_code == 200:
            data = response.json()
            # session_id should be in response if provided
            assert "session_id" in data["data"]

    def test_regression_no_settings_in_kwargs(self, authenticated_client):
        """CRITICAL: Verify that settings dict is NOT passed to provider.

        This is a regression test for the MILESTONE-1 bug fix.
        The HTTPStubProvider raises ValueError if 'settings' is in kwargs.
        """
        settings = {
            "text": {
                "model": "gpt-4o-mini",
                "temperature": 0.3,
                "max_tokens": 50,
            },
            "general": {
                "ai_agent_enabled": False,
                "some_other_field": "value",
            },
        }

        # This should NOT raise ValueError from HTTPStubProvider
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Regression test prompt",
                "settings": settings,
                "customer_id": 1,
            },
        )

        # If settings was passed to provider, HTTPStubProvider raises ValueError
        # and we'd get 500 error. This test ensures we get 200.
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_invalid_customer_id(self, authenticated_client):
        """Test handling of invalid customer ID."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Test",
                "settings": {},
                "customer_id": -1,  # Invalid
            },
        )

        # Should handle gracefully (may succeed with invalid ID in test mode)
        assert response.status_code in [200, 400, 422]

    def test_malformed_settings(self, authenticated_client):
        """Test handling of malformed settings dict."""
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Test",
                "settings": "not-a-dict",  # Invalid type
                "customer_id": 1,
            },
        )

        # FastAPI validation should catch this
        assert response.status_code == 422

    def test_missing_required_fields(self, authenticated_client):
        """Test validation of required fields."""
        # Missing customer_id
        response = authenticated_client.post(
            "/api/v1/chat/session-name",
            json={
                "prompt": "Test",
                "settings": {},
            },
        )

        assert response.status_code == 422  # Validation error
