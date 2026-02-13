"""Integration tests ensuring first-message attachments are processed."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from features.chat.utils.content_processor import is_native_pdf_model
from tests.integration.chat.conftest import _build_chat_test_app

class _StubProvider:
    """Lightweight provider stub for chat streaming tests."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def get_model_config(self):  # pragma: no cover - simple stub
        return None

    async def stream(self, *, runtime=None, **_: object) -> AsyncIterator[str]:  # pragma: no cover - trivial
        yield "stub"


async def _post_chat_stream(payload: dict, auth_token: str = None) -> tuple[int, bytes]:
    app = _build_chat_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if auth_token:
            client.headers.update({"Authorization": f"Bearer {auth_token}"})
        response = await client.post("/chat/stream", json=payload)
    return response.status_code, response.content


def test_file_attachment_first_message_openai(auth_token: str) -> None:
    """OpenAI models should convert first-message PDFs into images."""

    payload = {
        "request_type": "text",
        "prompt": [
            {"type": "text", "text": "What's in the document?"},
            {"type": "file_url", "file_url": {"url": "https://example.com/test.pdf"}},
        ],
        "user_input": {
            "prompt": [
                {"type": "text", "text": "What's in the document?"},
                {"type": "file_url", "file_url": {"url": "https://example.com/test.pdf"}},
            ],
            "chat_history": [],
        },
        "settings": {"text": {"model": "gpt-4o-mini"}},
        "customer_id": 1,
    }

    stub_provider = _StubProvider("openai")

    with patch("features.chat.utils.generation_context.get_text_provider", return_value=stub_provider), patch(
        "features.chat.utils.content_processor.process_file_attachments"
    ) as mock_process:
        mock_process.return_value = ["/tmp/page_0.png"]

        status, _ = asyncio.run(_post_chat_stream(payload, auth_token))

    assert status == 200
    mock_process.assert_called_once()


def test_image_attachment_first_message_anthropic(auth_token: str) -> None:
    """Anthropic models should convert images to base64 on first message."""

    payload = {
        "request_type": "text",
        "prompt": [
            {"type": "text", "text": "Describe the picture"},
            {"type": "image_url", "image_url": {"url": "https://example.com/test.jpg"}},
        ],
        "user_input": {
            "prompt": [
                {"type": "text", "text": "Describe the picture"},
                {"type": "image_url", "image_url": {"url": "https://example.com/test.jpg"}},
            ],
            "chat_history": [],
        },
        "settings": {"text": {"model": "claude-haiku-4-5"}},
        "customer_id": 1,
    }

    stub_provider = _StubProvider("anthropic")

    with patch("features.chat.utils.generation_context.get_text_provider", return_value=stub_provider), patch(
        "features.chat.utils.content_processor.get_base64_for_image"
    ) as mock_base64:
        mock_base64.return_value = ("image/jpeg", "base64string")

        status, _ = asyncio.run(_post_chat_stream(payload, auth_token))

    assert status == 200
    mock_base64.assert_called_once()


def test_is_native_pdf_model_matches_expectations() -> None:
    """Integration sanity check for native PDF detection helper."""

    assert is_native_pdf_model("anthropic", "claude-haiku-4-5") is True
    assert is_native_pdf_model("openai", "gpt-5-mini") is True
    assert is_native_pdf_model("openai", "gpt-4o-mini") is False
