"""Unit tests covering the additional providers introduced in milestone 6."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.image.flux import FluxImageProvider
from core.providers.image.gemini import GeminiImageProvider
from core.providers.image.stability import StabilityImageProvider
from core.providers.image.xai import XaiImageProvider
from core.providers.text.anthropic import AnthropicTextProvider
from core.providers.text.deepseek import DeepSeekTextProvider
from core.providers.text.gemini import GeminiTextProvider
from core.providers.text.groq import GroqTextProvider
from core.providers.text.perplexity import PerplexityTextProvider
from core.providers.text.xai import XaiTextProvider
from core.streaming.manager import StreamingManager
from features.chat.services.streaming.standard_provider import (
    stream_standard_response,
)

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture(autouse=True)
def isolate_ai_clients():
    """Ensure tests can freely manipulate the ai_clients registry."""

    original = dict(ai_clients)
    ai_clients.clear()
    try:
        yield
    finally:
        ai_clients.clear()
        ai_clients.update(original)


class _MockFilesClient:
    """Capture file uploads made by the xAI formatter."""

    def __init__(self) -> None:
        self.upload_calls: list[tuple[bytes, str | None]] = []

    async def upload(self, file_bytes: bytes, filename: str | None = None):
        self.upload_calls.append((file_bytes, filename))
        return SimpleNamespace(id=f"file-{len(self.upload_calls)}")


class _MockChatConversation:
    def __init__(self, *, response: Any = None, stream_items: list[tuple[Any, Any]] | None = None) -> None:
        self._response = response
        self._stream_items = stream_items or []

    async def sample(self) -> Any:
        return self._response

    async def stream(self):
        for item in self._stream_items:
            yield item


class _MockChatClient:
    def __init__(self) -> None:
        self.response: Any = None
        self.stream_items: list[tuple[Any, Any]] = []
        self.create_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _MockChatConversation:
        self.create_calls.append(kwargs)
        return _MockChatConversation(response=self.response, stream_items=list(self.stream_items))


class _MockXaiClient:
    def __init__(self) -> None:
        self.chat = _MockChatClient()
        self.files = _MockFilesClient()


@pytest.mark.anyio("asyncio")
async def test_gemini_text_generate(monkeypatch):
    """Gemini provider returns text and reasoning metadata."""

    ai_clients["gemini"] = SimpleNamespace()
    provider = GeminiTextProvider()

    mock_response = SimpleNamespace(
        text="Hello",
        candidates=[SimpleNamespace(grounding_metadata="trace")],
    )
    monkeypatch.setattr(provider, "_generate_async", AsyncMock(return_value=mock_response))

    response = await provider.generate(prompt="Hi")

    assert response.text == "Hello"
    assert response.reasoning == "trace"


@pytest.mark.anyio("asyncio")
async def test_gemini_text_generate_defaults_enable_tools(monkeypatch):
    """Default Gemini tool config should expose search and code execution."""

    ai_clients["gemini"] = SimpleNamespace()
    provider = GeminiTextProvider()

    captured: dict[str, Any] = {}

    async def fake_generate(model: str, contents: list[Any], config: Any) -> Any:
        captured["config"] = config
        return SimpleNamespace(text="Default tools", candidates=[])

    monkeypatch.setattr(provider, "_generate_async", fake_generate)

    response = await provider.generate(prompt="Hi")

    assert response.text == "Default tools"
    config = captured.get("config")
    assert config is not None
    tools = getattr(config, "tools", None)
    assert tools, "Expected Gemini tools to be configured by default"

    has_search = any(getattr(tool, "google_search", None) for tool in tools)
    has_code_execution = any(getattr(tool, "code_execution", None) for tool in tools)

    assert has_search, "google_search should be enabled by default"
    assert has_code_execution, "code_execution should be enabled by default"


@pytest.mark.anyio("asyncio")
async def test_gemini_text_generate_with_tools(monkeypatch, caplog):
    """Gemini provider wires Google tooling when requested."""

    ai_clients["gemini"] = SimpleNamespace()
    provider = GeminiTextProvider()

    captured: dict[str, Any] = {}

    async def fake_generate(model: str, contents: list[Any], config: Any) -> Any:
        captured["config"] = config
        return SimpleNamespace(text="Tool output", candidates=[])

    monkeypatch.setattr(provider, "_generate_async", fake_generate)
    caplog.set_level(logging.INFO, logger="core.providers.text.gemini")

    tool_settings = {
        "google_search": {
            "exclude_domains": ["example.com", ""],
            "time_range": {
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-01-31T23:59:59Z",
            },
            "dynamic_retrieval": {
                "mode": "MODE_DYNAMIC",
                "dynamic_threshold": 0.2,
            },
        },
        "url_context": {"urls": ["https://example.com/a", "https://example.com/b"]},
        "code_execution": True,
    }

    response = await provider.generate(prompt="Hi", tool_settings=tool_settings)

    assert response.text == "Tool output"
    config = captured.get("config")
    assert config is not None
    assert getattr(config, "tools", None)

    google_tool = next(
        (tool.google_search for tool in config.tools if getattr(tool, "google_search", None)),
        None,
    )
    assert google_tool is not None
    assert google_tool.exclude_domains == ["example.com"]
    assert google_tool.time_range_filter is not None
    assert google_tool.time_range_filter.start_time.isoformat().startswith("2024-01-01")

    retrieval_tool = next(
        (
            tool.google_search_retrieval
            for tool in config.tools
            if getattr(tool, "google_search_retrieval", None)
        ),
        None,
    )
    assert retrieval_tool is not None
    assert retrieval_tool.dynamic_retrieval_config is not None
    assert retrieval_tool.dynamic_retrieval_config.mode.name == "MODE_DYNAMIC"

    url_tool = next(
        (tool for tool in config.tools if getattr(tool, "url_context", None) is not None),
        None,
    )
    assert url_tool is not None

    code_tool = next(
        (tool for tool in config.tools if getattr(tool, "code_execution", None) is not None),
        None,
    )
    assert code_tool is not None

    matching_records = [
        record for record in caplog.records if "Gemini tools enabled" in record.message
    ]
    assert matching_records, "Expected Gemini tool usage to be logged"
    log_message = matching_records[-1].message
    assert "example.com/a" in log_message
    assert "code_execution" in log_message


@pytest.mark.anyio("asyncio")
async def test_gemini_text_stream():
    """Gemini provider streams chunks via async iterator."""

    async def stream_generator():
        yield SimpleNamespace(text="He")
        yield SimpleNamespace(text="llo")

    ai_clients["gemini"] = SimpleNamespace(
        models=MagicMock(),
        aio=SimpleNamespace(models=SimpleNamespace(generate_content_stream=AsyncMock(return_value=stream_generator()))),
    )

    provider = GeminiTextProvider()
    chunks: list[str] = []
    async for chunk in provider.stream(prompt="Hi"):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello"


@pytest.mark.anyio("asyncio")
async def test_anthropic_generate_and_stream(monkeypatch):
    """Anthropic provider supports both generate and streaming flows."""

    class DummyEvent:
        def __init__(self, event_type: str, **kwargs):
            self.type = event_type
            for key, value in kwargs.items():
                setattr(self, key, value)

    class DummyStream:
        def __init__(self, outputs: list[str]):
            self._outputs = outputs
            self._events = self._build_events(outputs)
            self._iterator = None

        async def __aenter__(self):
            self._iterator = iter(self._events)
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - no cleanup required
            return False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._iterator is None:
                raise StopAsyncIteration
            try:
                return next(self._iterator)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def get_final_message(self):
            return SimpleNamespace(content=[])

        def _build_events(self, outputs: list[str]):
            events = [DummyEvent("content_block_start", content_block=SimpleNamespace(type="text"), index=0)]
            for chunk in outputs:
                events.append(
                    DummyEvent(
                        "content_block_delta",
                        delta=SimpleNamespace(type="text_delta", text=chunk),
                        index=0,
                    )
                )
            return events

    response = SimpleNamespace(content=[SimpleNamespace(text="Claude response")])
    monkeypatch.setitem(
        ai_clients,
        "anthropic_async",
        SimpleNamespace(
            messages=SimpleNamespace(
                create=AsyncMock(return_value=response),
                stream=lambda **_: DummyStream(["hello", " world"]),
            )
        ),
    )

    provider = AnthropicTextProvider()
    result = await provider.generate(prompt="Hi")
    assert result.text == "Claude response"

    streamed = []
    async for chunk in provider.stream(prompt="Hi"):
        streamed.append(chunk)
    assert "".join(streamed) == "hello world"


def _openai_style_client(text: str, *, citations: list | None = None):
    """Return a mock OpenAI-compatible client returning the supplied text."""

    async def create(**kwargs):
        if kwargs.get("stream"):
            async def gen():
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])

            return gen()

        message = SimpleNamespace(content=text)
        choice = SimpleNamespace(message=message, finish_reason="stop")
        usage = SimpleNamespace(model_dump=lambda: {"prompt_tokens": 1})
        response = SimpleNamespace(choices=[choice], usage=usage)
        if citations is not None:
            response.citations = citations
        return response

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=create))))


def _xai_style_client(text: str):
    """Return a client stub that matches the xAI SDK surface."""

    class _FakeChatRequest:
        async def sample(self) -> SimpleNamespace:
            return SimpleNamespace(
                content=text,
                reasoning_content=None,
                tool_calls=[],
                finish_reason="stop",
                usage=None,
                id="resp-123",
                server_side_tool_usage=None,
            )

        async def stream(self):  # pragma: no cover - not exercised here
            yield (
                SimpleNamespace(reasoning_content=None, tool_calls=None),
                SimpleNamespace(content=text, reasoning_content=None, tool_calls=None),
            )

    class _FakeChat:
        def create(self, **_: Any) -> _FakeChatRequest:
            return _FakeChatRequest()

    return SimpleNamespace(chat=_FakeChat())


@pytest.mark.anyio("asyncio")
async def test_groq_provider():
    """Groq provider wraps the OpenAI-compatible API."""

    ai_clients["groq_async"] = _openai_style_client("Groq reply")
    provider = GroqTextProvider()
    response = await provider.generate(prompt="Hi")
    assert response.text == "Groq reply"

    chunks = []
    async for chunk in provider.stream(prompt="Hi"):
        chunks.append(chunk)
    assert "".join(chunks) == "Groq reply"


@pytest.mark.anyio("asyncio")
async def test_perplexity_provider_returns_citations():
    """Perplexity provider exposes citations metadata."""

    citations = [{"title": "Example"}]
    ai_clients["perplexity_async"] = _openai_style_client("Perplexity", citations=citations)
    provider = PerplexityTextProvider()
    response = await provider.generate(prompt="Hi")
    assert response.citations == citations


@pytest.mark.anyio("asyncio")
async def test_deepseek_reasoning(monkeypatch):
    """DeepSeek provider can call reasoning models."""

    client = _openai_style_client("DeepSeek")
    ai_clients["deepseek_async"] = client
    provider = DeepSeekTextProvider()

    result = await provider.generate(prompt="Hi")
    assert result.text == "DeepSeek"

    # Spy on the underlying client to ensure reasoning call uses different model
    async def create(**kwargs):
        assert kwargs["model"] == "deepseek-reasoner"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Reasoned"), finish_reason="stop")],
            usage=SimpleNamespace(model_dump=lambda: {}),
        )

    client.chat.completions.create = AsyncMock(side_effect=create)
    reasoning = await provider.generate_with_reasoning(prompt="Hi")
    assert reasoning.text == "Reasoned"


@pytest.mark.anyio("asyncio")
async def test_xai_text_provider():
    """xAI provider reuses the OpenAI-compatible flow."""

    ai_clients["xai_async"] = _xai_style_client("Grok says hi")
    provider = XaiTextProvider()
    response = await provider.generate(prompt="Hi")
    assert response.text == "Grok says hi"


@pytest.mark.anyio("asyncio")
async def test_xai_generate_formats_attachments_and_metadata(monkeypatch, tmp_path):
    """xAI provider forwards attachments, tool definitions, and metadata."""

    from core.providers.text import xai_format as xai_format_module

    fake_client = _MockXaiClient()
    ai_clients["xai_async"] = fake_client

    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    file_path = tmp_path / "notes.txt"
    file_path.write_text("tool call attachment")

    def _text(value: str):
        return {"type": "text", "value": value}

    def _image(url: str, *, detail: str = "auto"):
        return {"type": "image", "url": url, "detail": detail}

    def _file(file_id: str):
        return {"type": "file", "file_id": file_id}

    def _role(role: str):
        def _builder(*parts):
            return {"role": role, "parts": list(parts)}

        return _builder

    monkeypatch.setattr(xai_format_module.chat, "text", _text)
    monkeypatch.setattr(xai_format_module.chat, "image", _image)
    monkeypatch.setattr(xai_format_module.chat, "file", _file)
    monkeypatch.setattr(xai_format_module.chat, "system", _role("system"))
    monkeypatch.setattr(xai_format_module.chat, "user", _role("user"))
    monkeypatch.setattr(xai_format_module.chat, "assistant", _role("assistant"))
    monkeypatch.setattr(
        xai_format_module.chat,
        "tool",
        lambda name, description="", parameters=None: SimpleNamespace(
            function=SimpleNamespace(name=name, description=description, parameters=parameters or {})
        ),
    )
    monkeypatch.setattr(
        xai_format_module.chat,
        "required_tool",
        lambda name: SimpleNamespace(function_name=name),
    )

    original_formatter = xai_format_module.format_messages_for_xai
    captured: dict[str, Any] = {}

    async def capturing_formatter(messages, *, client, download_fn=None):
        captured["raw_messages"] = messages
        result = await original_formatter(messages, client=client, download_fn=download_fn)
        captured["result"] = result
        return result

    monkeypatch.setattr(
        "core.providers.text.xai.format_messages_for_xai",
        capturing_formatter,
    )

    fake_client.chat.response = SimpleNamespace(
        content="Inspection complete",
        reasoning_content="Step by step",
        tool_calls=[
            SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(
                    name="extract_metadata",
                    arguments=json.dumps({"fileCount": 1, "mimeTypes": ["text/plain"]}),
                ),
            )
        ],
        finish_reason="stop",
        usage=None,
        id="resp-7",
        server_side_tool_usage={"uploads": 1},
    )

    provider = XaiTextProvider()

    tool_settings = {
        "functions": [
            {
                "name": "extract_metadata",
                "description": "Summarise attachment metadata",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fileCount": {"type": "integer"},
                        "mimeTypes": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
    }

    response = await provider.generate(
        prompt="Review the attachments",
        system_prompt="Follow the checklist",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Inspect everything"},
                    {"type": "image_url", "image_url": {"url": str(image_path), "detail": "high"}},
                    {"type": "file_url", "file_url": {"url": str(file_path), "filename": "notes.txt"}},
                ],
            }
        ],
        tool_settings=tool_settings,
    )

    formatted = captured["result"]
    assert formatted.uploaded_file_ids == ["file-1"]
    assert formatted.messages[0]["parts"][1]["url"].startswith("data:")
    assert captured["raw_messages"][0]["content"][1]["image_url"]["url"] == str(image_path)
    assert fake_client.files.upload_calls[0][1] == "notes.txt"

    create_kwargs = fake_client.chat.create_calls[-1]
    assert create_kwargs["messages"] == formatted.messages
    assert create_kwargs["parallel_tool_calls"] is True
    assert create_kwargs["tool_choice"] == "auto"
    assert create_kwargs["tools"][0].function.name == "extract_metadata"

    metadata = response.metadata or {}
    assert metadata.get("uploaded_file_ids") == ["file-1"]
    assert metadata.get("tool_calls")[0]["function"]["arguments"]["mimeTypes"] == ["text/plain"]
    assert metadata.get("server_side_tool_usage") == {"uploads": 1}
    assert response.reasoning == "Step by step"


@pytest.mark.anyio("asyncio")
async def test_xai_streaming_integrates_with_manager(monkeypatch):
    """Streaming from xAI feeds text, reasoning, and tool calls into the manager."""

    fake_client = _MockXaiClient()
    ai_clients["xai_async"] = fake_client

    async def minimal_formatter(messages, *, client, download_fn=None):
        return SimpleNamespace(
            messages=[{"role": "user", "parts": [{"type": "text", "value": "converted"}]}],
            uploaded_file_ids=[],
            temporary_files=[],
        )

    monkeypatch.setattr(
        "core.providers.text.xai.format_messages_for_xai",
        minimal_formatter,
    )

    fake_client.chat.stream_items = [
        (
            SimpleNamespace(),
            SimpleNamespace(reasoning_content="First observation", tool_calls=[], content=""),
        ),
        (
            SimpleNamespace(),
            SimpleNamespace(reasoning_content="", tool_calls=[], content="Partial text"),
        ),
        (
            SimpleNamespace(),
            SimpleNamespace(
                reasoning_content="",
                tool_calls=[
                    SimpleNamespace(
                        id="call-42",
                        function=SimpleNamespace(
                            name="extract_metadata",
                            arguments=json.dumps({"fileCount": 1}),
                        ),
                    )
                ],
                content="",
            ),
        ),
    ]

    provider = XaiTextProvider()

    manager = StreamingManager()
    frontend_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(frontend_queue)

    outcome = await stream_standard_response(
        provider=provider,
        manager=manager,
        prompt_text="Explain the attachment",
        model="grok-4",
        temperature=0.3,
        max_tokens=128,
        system_prompt="",
        messages=[{"role": "user", "content": "Explain"}],
        settings={
            "text": {
                "model": "grok-4",
                "tools": {
                    "functions": [
                        {
                            "name": "extract_metadata",
                            "parameters": {"type": "object", "properties": {}},
                        }
                    ]
                },
            }
        },
    )

    events: list[Any] = []
    while not frontend_queue.empty():
        events.append(frontend_queue.get_nowait())

    # Check for thinking_chunk (reasoning) event
    assert any(
        event.get("type") == "thinking_chunk" and event.get("data", {}).get("content")
        for event in events
    )
    assert {"type": "text_chunk", "content": "Partial text"} in events
    tool_event = next(event for event in events if event.get("type") == "tool_start")
    tool_data = tool_event.get("data", {})
    assert tool_data.get("tool_name") == "extract_metadata"

    results = manager.get_results()
    assert results["text"] == "Partial text"
    assert results["reasoning"] == "First observation"
    stored_tool = results["tool_calls"][0]
    if "function" in stored_tool:
        stored_function = stored_tool["function"]
    else:
        stored_function = (stored_tool.get("value") or [{}])[0]["function"]
    assert stored_function["name"] == "extract_metadata"

    assert outcome.requires_tool_action is True
    summary_payload = outcome.tool_calls[0]
    if "function" in summary_payload:
        arguments = summary_payload["function"]["arguments"]
    else:
        arguments = (summary_payload.get("value") or [{}])[0]["function"]["arguments"]
    assert arguments == {"fileCount": 1}

    create_kwargs = fake_client.chat.create_calls[-1]
    assert create_kwargs.get("tools"), "Expected xAI tool payload to be forwarded"


@pytest.mark.anyio("asyncio")
async def test_stability_image_provider(monkeypatch):
    """Stability provider decodes base64 payloads."""

    monkeypatch.setenv("STABILITY_API_KEY", "key")

    image_bytes = base64.b64encode(b"stability").decode()

    class DummyResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = "ok"

        def json(self):
            return {"artifacts": [{"base64": image_bytes}]}

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):  # pragma: no cover - simple stub
            return DummyResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: DummyClient())

    provider = StabilityImageProvider()
    result = await provider.generate(prompt="Create art")
    assert result == b"stability"


@pytest.mark.anyio("asyncio")
async def test_flux_image_provider(monkeypatch):
    """Flux provider handles immediate responses."""

    monkeypatch.setenv("FLUX_API_KEY", "key")

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"status": "completed", "result": {"image": base64.b64encode(b"flux").decode()}}

        text = "ok"

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            return DummyResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: DummyClient())

    provider = FluxImageProvider()
    result = await provider.generate(prompt="Scene")
    assert result == b"flux"


from core.providers.image.utils.flux_helpers import decode_image_from_response

...

@pytest.mark.anyio("asyncio")
async def test_flux_image_provider_rejects_pending_response(monkeypatch):
    """Flux provider refuses to decode pending responses."""

    monkeypatch.setenv("FLUX_API_KEY", "key")

    with pytest.raises(ProviderError, match="status=pending"):
        await decode_image_from_response({"status": "pending"}, "key")


@pytest.mark.anyio("asyncio")
async def test_flux_image_provider_polls_until_complete(monkeypatch):
    """Flux provider polls queued jobs until completion."""

    monkeypatch.setenv("FLUX_API_KEY", "key")

    completed_payload = {
        "status": "completed",
        "result": {"image": base64.b64encode(b"async_flux").decode()},
    }

    class DummyResponse:
        status_code = 200
        text = "ok"

        def __init__(self, payload: dict[str, Any]):
            self._payload = payload

        def json(self):
            return self._payload

    responses = [
        DummyResponse(
            {
                "status": "queued",
                "id": "task-123",
                "polling_url": "https://api.eu.bfl.ai/v1/polling/task-123",
            }
        ),
        DummyResponse({"status": "processing"}),
        DummyResponse(completed_payload),
    ]

    def _client_factory(*args, **kwargs):  # pragma: no cover - deterministic stub
        class DummyClient:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, exc_type, exc, tb):
                return False

            async def post(self_inner, url, json, headers):
                return responses.pop(0)

            async def get(self_inner, url, headers, params=None):
                return responses.pop(0)

        return DummyClient()

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)

    provider = FluxImageProvider()
    result = await provider.generate(prompt="Scene")

    assert result == b"async_flux"
    assert responses == []


@pytest.mark.anyio("asyncio")
async def test_flux_image_provider_downloads_url(monkeypatch):
    """Flux provider falls back to downloading when only a URL is returned."""

    monkeypatch.setenv("FLUX_API_KEY", "key")

    class DummyResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return {"status": "completed", "result": {"url": "https://example.com/image.png"}}

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            return DummyResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: DummyClient())

    provider = FluxImageProvider()
    download_mock = AsyncMock(return_value=b"downloaded")
    monkeypatch.setattr("core.providers.image.utils.flux_helpers.download_image", download_mock)

    result = await provider.generate(prompt="Scene")

    assert result == b"downloaded"
    download_mock.assert_awaited_once_with("https://example.com/image.png", "key")


@pytest.mark.anyio("asyncio")
async def test_gemini_image_provider_imagen_model(monkeypatch):
    """Gemini image provider decodes bytes for Imagen models."""

    ai_clients["gemini"] = SimpleNamespace(
        models=SimpleNamespace(
            generate_images=lambda **_: None,
            generate_content=lambda **_: None,
        )
    )
    provider = GeminiImageProvider()

    response = SimpleNamespace(images=[SimpleNamespace(image_bytes=b"pixels")])
    to_thread = AsyncMock(return_value=response)
    monkeypatch.setattr(asyncio, "to_thread", to_thread)

    image = await provider.generate(prompt="Sunset", width=1280, height=720)

    assert image == b"pixels"
    assert to_thread.await_args[0][0] is ai_clients["gemini"].models.generate_images


@pytest.mark.anyio("asyncio")
async def test_gemini_image_provider_flash_model(monkeypatch):
    """Gemini image provider decodes inline data for flash models."""

    ai_clients["gemini"] = SimpleNamespace(
        models=SimpleNamespace(
            generate_images=lambda **_: None,
            generate_content=lambda **_: None,
        )
    )
    provider = GeminiImageProvider()

    inline_data = SimpleNamespace(data=base64.b64encode(b"flash").decode("utf-8"))
    response = SimpleNamespace(parts=[SimpleNamespace(inline_data=inline_data)])
    to_thread = AsyncMock(return_value=response)
    monkeypatch.setattr(asyncio, "to_thread", to_thread)

    image = await provider.generate(
        prompt="Sunset",
        model="gemini-2.5-flash-image",
        width=512,
        height=512,
    )

    assert image == b"flash"
    assert to_thread.await_args[0][0] is ai_clients["gemini"].models.generate_content


@pytest.mark.anyio("asyncio")
async def test_xai_image_provider(monkeypatch):
    """xAI image provider decodes base64 image payload."""

    monkeypatch.setenv("XAI_API_KEY", "secret")

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"data": [{"b64_json": base64.b64encode(b"xai").decode()}]}

    class DummyClient:
        def __init__(self) -> None:
            self.last_payload: dict[str, Any] | None = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, json=None, headers=None):
            self.last_payload = {"url": url, "json": json, "headers": headers}
            return DummyResponse()

        async def get(self, *_args, **_kwargs):
            raise AssertionError("Unexpected GET request in xAI test")

    dummy_client = DummyClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: dummy_client)

    provider = XaiImageProvider()
    image = await provider.generate(
        prompt="City skyline",
        width=768,
        height=512,
        size="640x480",
        style="photographic",
        quality="medium",
    )

    assert image == b"xai"
    assert provider.last_quality == "medium"
    payload = dummy_client.last_payload["json"]
    assert payload["width"] == 640
    assert payload["height"] == 480
    assert payload["response_format"] == "b64_json"
    assert payload["style"] == "photographic"
    assert "quality" not in payload


@pytest.fixture
def anyio_backend():
    """Force anyio to use the asyncio backend for deterministic tests."""

    return "asyncio"
