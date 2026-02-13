"""Unit tests for the multimodal content processor utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from features.chat.utils.content_processor import (
    is_native_pdf_model,
    process_image_attachments,
    process_message_content,
)


def test_process_message_content_text_only() -> None:
    """Text-only content should be returned unchanged."""

    content = [{"type": "text", "text": "Hello world"}]

    result = process_message_content(
        content=content,
        provider_name="openai",
        model_name="gpt-4o-mini",
    )

    assert result == content


@patch("features.chat.utils.content_processor.process_file_attachments")
def test_process_message_content_with_file_non_native_model(mock_process: MagicMock) -> None:
    """Non-native models should trigger file conversion for PDF attachments."""

    mock_process.return_value = ["/tmp/page_0.png", "/tmp/page_1.png"]
    content = [
        {"type": "text", "text": "Check this document"},
        {"type": "file_url", "file_url": {"url": "https://example.com/doc.pdf"}},
    ]

    result = process_message_content(
        content=content,
        provider_name="openai",
        model_name="gpt-4o-mini",
    )

    assert any(item.get("type") == "image_url" for item in result)
    mock_process.assert_called_once()


def test_process_message_content_with_file_native_model() -> None:
    """Native models should keep file_url entries intact."""

    content = [
        {"type": "text", "text": "Please read this"},
        {"type": "file_url", "file_url": {"url": "https://example.com/doc.pdf"}},
    ]

    result = process_message_content(
        content=content,
        provider_name="anthropic",
        model_name="claude-haiku-4-5",
    )

    assert result[1]["type"] == "file_url"
    assert result[1]["file_url"]["url"] == "https://example.com/doc.pdf"


@patch("features.chat.utils.content_processor.get_base64_for_image")
def test_process_image_attachments_anthropic(mock_base64: MagicMock) -> None:
    """Anthropic providers should return base64 encoded images."""

    mock_base64.return_value = ("image/jpeg", "base64data")
    items = [
        {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
    ]

    result = process_image_attachments(
        image_items=items,
        provider_name="anthropic",
        model_name="claude-haiku-4-5",
    )

    assert result[0]["type"] == "image"
    assert result[0]["source"]["data"] == "base64data"
    mock_base64.assert_called_once()


def test_process_image_attachments_openai_preserves_urls() -> None:
    """Non-Anthropic providers should keep image_url entries."""

    items = [
        {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
    ]

    result = process_image_attachments(
        image_items=items,
        provider_name="openai",
        model_name="gpt-4o-mini",
    )

    assert result == items


@pytest.mark.parametrize(
    "provider,model,expected",
    [
        ("anthropic", "claude-haiku-4-5", True),
        ("gemini", "gemini-flash-latest", True),
        ("openai", "gpt-5-nano", True),
        ("openai", "gpt-4o-mini", False),
        ("groq", "llama-3.3-70b-versatile", False),
    ],
)
def test_is_native_pdf_model(provider: str, model: str, expected: bool) -> None:
    """Native PDF detection should align with provider/model expectations."""

    assert is_native_pdf_model(provider, model) is expected
