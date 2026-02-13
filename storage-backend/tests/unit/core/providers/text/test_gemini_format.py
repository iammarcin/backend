"""Tests for Gemini chat history conversion helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from google.genai import types  # type: ignore

from core.providers.text.utils import prepare_gemini_contents


def _text_part(part: types.Part) -> str | None:
    return getattr(part, "text", None)


def test_prepare_gemini_contents_converts_messages() -> None:
    messages = [
        {"role": "system", "content": "ignore"},
        {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "How are you?"},
    ]

    contents = prepare_gemini_contents(prompt="ignored", messages=messages)

    assert [content.role for content in contents] == ["user", "model", "user"]
    assert [_text_part(content.parts[0]) for content in contents] == ["Hi", "Hello", "How are you?"]


def _mock_remote_binary(monkeypatch: pytest.MonkeyPatch, payloads: dict[str, bytes]) -> None:
    class _Response:
        def __init__(self, data: bytes):
            self.content = data

        def raise_for_status(self) -> None:  # pragma: no cover - simple stub
            return None

    def _fake_get(url: str, timeout: int = 30) -> _Response:
        return _Response(payloads[url])

    monkeypatch.setattr(
        "core.providers.text.utils.gemini_attachments.requests.get",
        _fake_get,
    )


def test_prepare_gemini_contents_limits_user_attachments(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "First"},
                {"type": "image_url", "image_url": {"url": "https://example.com/1.png"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Second"},
                {"type": "image_url", "image_url": {"url": "https://example.com/2.png"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Third"},
                {"type": "image_url", "image_url": {"url": "https://example.com/3.png"}},
            ],
        },
    ]

    _mock_remote_binary(
        monkeypatch,
        {
            "https://example.com/1.png": b"img-a",
            "https://example.com/2.png": b"img-b",
            "https://example.com/3.png": b"img-c",
        },
    )

    contents = prepare_gemini_contents(messages=messages, prompt="", attachment_limit=2)

    assert len(contents) == 3
    # First two messages keep their attachments, the third exceeds the limit.
    assert contents[0].parts[1].inline_data.data == b"img-a"
    assert contents[1].parts[1].inline_data.data == b"img-b"
    assert len(contents[2].parts) == 1  # Only the text part remains.


def test_prepare_gemini_contents_inlines_file_attachments(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF-1.5 data")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Doc"},
                {"type": "file_url", "file_url": {"url": str(file_path), "mime_type": "application/pdf"}},
            ],
        }
    ]

    contents = prepare_gemini_contents(messages=messages, prompt="", attachment_limit=2)

    assert len(contents) == 1
    file_part = contents[0].parts[1]
    assert file_part.inline_data.data == b"%PDF-1.5 data"
    assert file_part.inline_data.mime_type == "application/pdf"


def test_prepare_gemini_contents_appends_audio_parts() -> None:
    audio_part = types.Part.from_bytes(data=b"123", mime_type="audio/wav")

    contents = prepare_gemini_contents(
        messages=[],
        prompt="Say something",
        audio_parts=[audio_part],
    )

    assert len(contents) == 1
    assert contents[0].role == "user"
    assert _text_part(contents[0].parts[0]) == "Say something"
    assert contents[0].parts[1].inline_data.data == b"123"
