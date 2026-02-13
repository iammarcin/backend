from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.providers.text.xai_format import format_messages_for_xai


class DummyFilesClient:
    def __init__(self) -> None:
        self.upload_calls: list[tuple[bytes, str | None]] = []

    async def upload(self, file_bytes: bytes, filename: str | None = None):  # noqa: D401 - simple mock
        self.upload_calls.append((file_bytes, filename))
        return SimpleNamespace(id=f"file_{len(self.upload_calls)}")


class DummyAsyncClient:
    def __init__(self) -> None:
        self.files = DummyFilesClient()


@pytest.fixture(autouse=True)
def patch_chat(monkeypatch: pytest.MonkeyPatch):
    def _text(value: str):
        return {"type": "text", "value": value}

    def _image(image_url: str, *, detail: str = "auto"):
        return {"type": "image", "url": image_url, "detail": detail}

    def _file(file_id: str):
        return {"type": "file", "file_id": file_id}

    def _role(role: str):
        def _builder(*parts):
            return {"role": role, "parts": list(parts)}

        return _builder

    def _tool(result: str):
        return {"role": "tool_result", "result": result}

    monkeypatch.setattr("core.providers.text.xai_format.chat.text", _text)
    monkeypatch.setattr("core.providers.text.xai_format.chat.image", _image)
    monkeypatch.setattr("core.providers.text.xai_format.chat.file", _file)
    monkeypatch.setattr("core.providers.text.xai_format.chat.system", _role("system"))
    monkeypatch.setattr("core.providers.text.xai_format.chat.user", _role("user"))
    monkeypatch.setattr("core.providers.text.xai_format.chat.assistant", _role("assistant"))
    monkeypatch.setattr("core.providers.text.xai_format.chat.tool_result", _tool)


@pytest.mark.asyncio
async def test_format_messages_basic_text() -> None:
    client = DummyAsyncClient()
    messages = [
        {"role": "system", "content": "Be helpful"},
        {"role": "user", "content": "Hello"},
    ]

    result = await format_messages_for_xai(messages, client=client)

    assert len(result.messages) == 2
    assert result.messages[0]["role"] == "system"
    assert result.messages[0]["parts"] == [{"type": "text", "value": "Be helpful"}]
    assert result.messages[1]["parts"] == [{"type": "text", "value": "Hello"}]
    assert result.uploaded_file_ids == []
    assert result.temporary_files == []


@pytest.mark.asyncio
async def test_format_messages_handles_image_with_detail() -> None:
    client = DummyAsyncClient()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/cat.png", "detail": "high"},
                },
            ],
        }
    ]

    result = await format_messages_for_xai(messages, client=client)

    assert len(result.messages) == 1
    parts = result.messages[0]["parts"]
    assert parts[0] == {"type": "text", "value": "Describe"}
    assert parts[1] == {
        "type": "image",
        "url": "https://example.com/cat.png",
        "detail": "high",
    }


@pytest.mark.asyncio
async def test_format_messages_uploads_files_once() -> None:
    client = DummyAsyncClient()
    download_calls: list[str] = []

    async def _download(url: str) -> bytes:
        download_calls.append(url)
        return b"file-bytes"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "See attachment"},
                {"type": "file_url", "file_url": {"url": "https://example.com/report.pdf"}},
                {"type": "file_url", "file_url": {"url": "https://example.com/report.pdf"}},
            ],
        }
    ]

    result = await format_messages_for_xai(messages, client=client, download_fn=_download)

    assert len(client.files.upload_calls) == 1
    assert download_calls == ["https://example.com/report.pdf"]
    assert result.uploaded_file_ids == ["file_1"]
    parts = result.messages[0]["parts"]
    assert parts[1] == {"type": "file", "file_id": "file_1"}
    assert parts[2] == {"type": "file", "file_id": "file_1"}


@pytest.mark.asyncio
async def test_format_messages_handles_tool_result_serialisation() -> None:
    client = DummyAsyncClient()
    messages = [
        {"role": "tool", "content": {"result": "42"}},
    ]

    result = await format_messages_for_xai(messages, client=client)

    assert len(result.messages) == 1
    tool_message = result.messages[0]
    assert tool_message["role"] == "tool_result"
    assert tool_message["result"] == "{\"result\": \"42\"}"


@pytest.mark.asyncio
async def test_format_messages_converts_local_image_to_data_url(tmp_path: Path) -> None:
    client = DummyAsyncClient()
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"\x89PNG\r\n")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": str(image_path)},
                }
            ],
        }
    ]

    result = await format_messages_for_xai(messages, client=client)

    part = result.messages[0]["parts"][0]
    assert part["url"].startswith("data:")
    assert image_path in result.temporary_files


@pytest.mark.asyncio
async def test_format_messages_handles_base64_image() -> None:
    client = DummyAsyncClient()
    encoded = base64.b64encode(b"fake-image").decode("ascii")
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": encoded,
                    },
                }
            ],
        }
    ]

    result = await format_messages_for_xai(messages, client=client)

    part = result.messages[0]["parts"][0]
    assert part == {
        "type": "image",
        "url": f"data:image/png;base64,{encoded}",
        "detail": "auto",
    }


@pytest.mark.asyncio
async def test_format_messages_handles_local_file_upload(tmp_path: Path) -> None:
    client = DummyAsyncClient()
    file_path = tmp_path / "notes.pdf"
    file_path.write_bytes(b"pdf-bytes")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "file_url", "file_url": {"url": str(file_path)}},
            ],
        }
    ]

    result = await format_messages_for_xai(messages, client=client)

    assert len(client.files.upload_calls) == 1
    uploaded_bytes, filename = client.files.upload_calls[0]
    assert uploaded_bytes == b"pdf-bytes"
    assert filename == "notes.pdf"
    assert result.uploaded_file_ids == ["file_1"]
    assert file_path in result.temporary_files

