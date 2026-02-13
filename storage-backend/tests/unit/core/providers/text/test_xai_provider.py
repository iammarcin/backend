"""Unit tests for the xAI text provider."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any, Iterable, Sequence
import grpc
import pytest
from xai_sdk import chat
from xai_sdk.chat import Chunk, Response
from xai_sdk.proto import chat_pb2, sample_pb2, usage_pb2

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.text.xai import XaiTextProvider

pytestmark = pytest.mark.anyio("asyncio")


class _FakeChatConversation:
    def __init__(self, response: Response | None, stream_items: Sequence[tuple[Response, Chunk]]):
        self._response = response
        self._stream_items = stream_items

    async def sample(self) -> Response:
        if self._response is None:
            raise RuntimeError("sample called with no response configured")
        return self._response

    async def stream(self) -> Iterable[tuple[Response, Chunk]]:
        for item in self._stream_items:
            yield item


class _FakeChatClient:
    def __init__(self) -> None:
        self.response: Response | None = None
        self.stream_items: list[tuple[Response, Chunk]] = []
        self.create_calls: list[dict[str, Any]] = []
        self._side_effect: Any = None

    def create(self, **kwargs: Any) -> _FakeChatConversation:
        if self._side_effect is not None:
            raise self._side_effect
        self.create_calls.append(kwargs)
        return _FakeChatConversation(self.response, list(self.stream_items))


class _FakeXaiClient:
    def __init__(self) -> None:
        self.chat = _FakeChatClient()


async def _minimal_formatter(messages: Sequence[dict[str, Any]], *, client: Any, download_fn: Any = None):
    return SimpleNamespace(messages=[chat.user("converted")], uploaded_file_ids=[], temporary_files=[])


@pytest.fixture(autouse=True)
def isolate_ai_clients() -> None:
    original = dict(ai_clients)
    ai_clients.clear()
    try:
        yield
    finally:
        ai_clients.clear()
        ai_clients.update(original)


def _build_response(
    *,
    content: str,
    reasoning: str = "",
    tool_calls: Sequence[dict[str, Any]] | None = None,
    citations: Sequence[str] | None = None,
) -> Response:
    message = chat_pb2.CompletionMessage()
    message.role = chat_pb2.MessageRole.ROLE_ASSISTANT
    message.content = content
    if reasoning:
        message.reasoning_content = reasoning
    for call in tool_calls or []:
        proto_call = message.tool_calls.add()
        proto_call.id = call.get("id", "call-1")
        proto_call.type = call.get("type", chat_pb2.ToolCallType.TOOL_CALL_TYPE_CLIENT_SIDE_TOOL)
        proto_call.function.name = call.get("name", "lookup")
        proto_call.function.arguments = json.dumps(call.get("arguments", {}))

    output = chat_pb2.CompletionOutput(
        index=0,
        finish_reason=sample_pb2.REASON_STOP,
        message=message,
    )
    response_proto = chat_pb2.GetChatCompletionResponse(
        id="resp-1",
        outputs=[output],
    )
    if citations:
        response_proto.citations.extend(list(citations))
    response_proto.usage.CopyFrom(
        usage_pb2.SamplingUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15)
    )
    return Response(response_proto, 0)


async def test_generate_captures_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeXaiClient()
    ai_clients["xai_async"] = fake_client

    captured_messages: list[dict[str, Any]] = []

    async def fake_formatter(messages: Sequence[dict[str, Any]], *, client: Any, download_fn: Any = None):
        captured_messages.extend(messages)
        return SimpleNamespace(
            messages=[chat.user("converted")],
            uploaded_file_ids=["file-123"],
            temporary_files=[],
        )

    monkeypatch.setattr("core.providers.text.xai.format_messages_for_xai", fake_formatter)

    fake_client.chat.response = _build_response(
        content="Hello world",
        reasoning="Because",
        tool_calls=[{"id": "tool-1", "name": "lookup", "arguments": {"city": "Berlin"}}],
    )

    provider = XaiTextProvider()
    tool_settings = {
        "functions": [
            {
                "name": "lookup_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": "lookup_weather"}},
    }

    response = await provider.generate(
        prompt="Hello",
        system_prompt="Be helpful",
        messages=[{"role": "user", "content": "Hi"}],
        tool_settings=tool_settings,
    )

    assert response.text == "Hello world"
    assert response.reasoning == "Because"
    metadata = response.metadata or {}
    assert metadata.get("usage", {}).get("promptTokens") == 5
    assert metadata.get("finish_reason") == "REASON_STOP"
    tool_payload = metadata.get("tool_calls") or []
    assert tool_payload and tool_payload[0]["function"]["arguments"] == {"city": "Berlin"}
    assert metadata.get("uploaded_file_ids") == ["file-123"]
    assert provider.capabilities.function_calling is True
    assert provider.capabilities.image_input is True
    assert provider.capabilities.file_input is True
    assert provider.capabilities.citations is True

    create_kwargs = fake_client.chat.create_calls[-1]
    tools = create_kwargs.get("tools")
    assert tools and tools[0].function.name == "lookup_weather"
    assert any(getattr(tool, "HasField")("web_search") for tool in tools)
    assert any(getattr(tool, "HasField")("x_search") for tool in tools)
    assert create_kwargs.get("parallel_tool_calls") is False
    tool_choice = create_kwargs.get("tool_choice")
    assert getattr(tool_choice, "function_name", None) == "lookup_weather"
    assert captured_messages, "Expected formatter to receive messages"


async def test_generate_returns_empty_text_when_tool_only(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeXaiClient()
    ai_clients["xai_async"] = fake_client

    monkeypatch.setattr(
        "core.providers.text.xai.format_messages_for_xai",
        _minimal_formatter,
    )

    fake_client.chat.response = _build_response(
        content="",
        tool_calls=[{"id": "tool-1", "name": "lookup", "arguments": {"id": 1}}],
    )

    provider = XaiTextProvider()
    result = await provider.generate(prompt="Hi")

    assert result.text == ""
    assert (result.metadata or {}).get("tool_calls")

    create_kwargs = fake_client.chat.create_calls[-1]
    tools = create_kwargs.get("tools") or []
    assert any(getattr(tool, "HasField")("web_search") for tool in tools)
    assert any(getattr(tool, "HasField")("x_search") for tool in tools)


async def test_generate_logs_server_tool_usage(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    fake_client = _FakeXaiClient()
    ai_clients["xai_async"] = fake_client

    monkeypatch.setattr(
        "core.providers.text.xai.format_messages_for_xai",
        _minimal_formatter,
    )

    fake_client.chat.response = _build_response(
        content="Result",
        tool_calls=[
            {
                "id": "tool-9",
                "name": "web_search",
                "arguments": {"query": "xai"},
                "type": chat_pb2.ToolCallType.TOOL_CALL_TYPE_WEB_SEARCH_TOOL,
            }
        ],
        citations=["https://example.com"],
    )

    provider = XaiTextProvider()

    with caplog.at_level(logging.INFO):
        response = await provider.generate(prompt="Hi")

    messages = [record.getMessage() for record in caplog.records]
    assert any("web_search" in message for message in messages)
    assert any("citations" in message for message in messages)

    assert response.metadata and response.metadata.get("citations") == ["https://example.com"]
    assert response.citations == [{"text": "https://example.com"}]


async def test_stream_yields_reasoning_and_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeXaiClient()
    ai_clients["xai_async"] = fake_client

    monkeypatch.setattr(
        "core.providers.text.xai.format_messages_for_xai",
        _minimal_formatter,
    )

    stream_response = _build_response(content="")

    reasoning_chunk_proto = chat_pb2.GetChatCompletionChunk()
    reasoning_entry = reasoning_chunk_proto.outputs.add()
    reasoning_entry.index = 0
    reasoning_entry.delta.role = chat_pb2.MessageRole.ROLE_ASSISTANT
    reasoning_entry.delta.reasoning_content = "Step 1"

    text_chunk_proto = chat_pb2.GetChatCompletionChunk()
    text_entry = text_chunk_proto.outputs.add()
    text_entry.index = 0
    text_entry.delta.role = chat_pb2.MessageRole.ROLE_ASSISTANT
    text_entry.delta.content = "Partial"

    tool_chunk_proto = chat_pb2.GetChatCompletionChunk()
    tool_entry = tool_chunk_proto.outputs.add()
    tool_entry.index = 0
    tool_entry.delta.role = chat_pb2.MessageRole.ROLE_ASSISTANT
    tool_call = tool_entry.delta.tool_calls.add()
    tool_call.id = "call-99"
    tool_call.type = chat_pb2.ToolCallType.TOOL_CALL_TYPE_CLIENT_SIDE_TOOL
    tool_call.function.name = "lookup"
    tool_call.function.arguments = json.dumps({"foo": "bar"})

    fake_client.chat.stream_items = [
        (stream_response, Chunk(reasoning_chunk_proto, 0)),
        (stream_response, Chunk(text_chunk_proto, 0)),
        (stream_response, Chunk(tool_chunk_proto, 0)),
    ]

    provider = XaiTextProvider()

    chunks: list[Any] = []
    async for item in provider.stream(prompt="Hi"):
        chunks.append(item)

    assert chunks[0] == {"type": "reasoning", "content": "Step 1"}
    assert chunks[1] == "Partial"
    assert chunks[2]["type"] == "tool_call"
    assert chunks[2]["content"]["requires_action"] is True
    assert chunks[2]["content"]["value"][0]["function"]["name"] == "lookup"
    assert provider.capabilities.reasoning is True


async def test_stream_continues_after_server_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeXaiClient()
    ai_clients["xai_async"] = fake_client

    monkeypatch.setattr(
        "core.providers.text.xai.format_messages_for_xai",
        _minimal_formatter,
    )

    stream_response = _build_response(content="")

    tool_chunk_proto = chat_pb2.GetChatCompletionChunk()
    tool_entry = tool_chunk_proto.outputs.add()
    tool_entry.index = 0
    tool_entry.delta.role = chat_pb2.MessageRole.ROLE_ASSISTANT
    tool_call = tool_entry.delta.tool_calls.add()
    tool_call.id = "call-123"
    tool_call.type = chat_pb2.ToolCallType.TOOL_CALL_TYPE_WEB_SEARCH_TOOL
    tool_call.function.name = "web_search"
    tool_call.function.arguments = json.dumps({"query": "latest nba"})

    text_chunk_proto = chat_pb2.GetChatCompletionChunk()
    text_entry = text_chunk_proto.outputs.add()
    text_entry.index = 0
    text_entry.delta.role = chat_pb2.MessageRole.ROLE_ASSISTANT
    text_entry.delta.content = "Final answer"

    fake_client.chat.stream_items = [
        (stream_response, Chunk(tool_chunk_proto, 0)),
        (stream_response, Chunk(text_chunk_proto, 0)),
    ]

    provider = XaiTextProvider()

    chunks: list[Any] = []
    async for item in provider.stream(prompt="Hi"):
        chunks.append(item)

    assert chunks[0]["type"] == "tool_call"
    assert chunks[0]["content"]["requires_action"] is False
    assert chunks[0]["content"]["value"][0]["function"]["name"] == "web_search"
    assert chunks[1] == "Final answer"


async def test_grpc_errors_are_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeXaiClient()
    ai_clients["xai_async"] = fake_client

    monkeypatch.setattr(
        "core.providers.text.xai.format_messages_for_xai",
        _minimal_formatter,
    )

    class _FakeRpcError(grpc.RpcError):
        def __init__(self, code: grpc.StatusCode, details: str) -> None:
            self._code = code
            self._details = details

        def code(self) -> grpc.StatusCode:
            return self._code

        def details(self) -> str:
            return self._details

    fake_client.chat._side_effect = _FakeRpcError(grpc.StatusCode.DEADLINE_EXCEEDED, "timeout")

    provider = XaiTextProvider()
    with pytest.raises(ProviderError) as exc:
        await provider.generate(prompt="Hi")

    assert "timed out" in str(exc.value)
