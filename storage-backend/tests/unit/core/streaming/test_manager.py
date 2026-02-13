"""Tests for the streaming manager."""

import asyncio

import pytest

from core.exceptions import CompletionOwnershipError, StreamingError
from core.streaming.manager import StreamingManager


@pytest.fixture
def anyio_backend() -> str:
    """Use the asyncio backend for streaming manager async tests."""

    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_streaming_manager_fan_out() -> None:
    """Data should be delivered to all registered queues."""

    manager = StreamingManager()
    queue1 = asyncio.Queue()
    queue2 = asyncio.Queue()

    manager.add_queue(queue1)
    manager.add_queue(queue2)

    await manager.send_to_queues("test chunk")

    assert await queue1.get() == "test chunk"
    assert await queue2.get() == "test chunk"


@pytest.mark.anyio("asyncio")
async def test_tts_queue_registration_and_status() -> None:
    """Registering and deregistering the TTS queue should toggle status."""

    manager = StreamingManager()
    tts_queue = asyncio.Queue()

    assert not manager.is_tts_enabled()

    manager.register_tts_queue(tts_queue)
    assert manager.is_tts_enabled()

    manager.deregister_tts_queue()
    assert not manager.is_tts_enabled()


@pytest.mark.anyio("asyncio")
async def test_text_chunk_duplication_to_tts_queue() -> None:
    """Text payloads should be duplicated to the TTS queue as plain strings."""

    manager = StreamingManager()
    frontend_queue = asyncio.Queue()
    tts_queue = asyncio.Queue()

    manager.add_queue(frontend_queue)
    manager.register_tts_queue(tts_queue)

    payload = {"type": "text_chunk", "content": "Hello world"}

    await manager.send_to_queues(payload)

    assert await asyncio.wait_for(frontend_queue.get(), timeout=1.0) == payload
    assert await asyncio.wait_for(tts_queue.get(), timeout=1.0) == "Hello world"
    assert manager.get_tts_chunks_sent() == 1


@pytest.mark.anyio("asyncio")
async def test_non_text_payloads_not_duplicated() -> None:
    """Only text payloads should reach the TTS queue."""

    manager = StreamingManager()
    tts_queue = asyncio.Queue()

    manager.register_tts_queue(tts_queue)

    await manager.send_to_queues({"type": "audio_chunk", "content": "base64"})
    await manager.send_to_queues({"type": "custom_event", "content": {}})

    assert tts_queue.empty()
    assert manager.get_tts_chunks_sent() == 0


@pytest.mark.anyio("asyncio")
async def test_empty_strings_not_sent_to_tts() -> None:
    """Whitespace only strings should be ignored when duplicating."""

    manager = StreamingManager()
    tts_queue = asyncio.Queue()

    manager.register_tts_queue(tts_queue)

    await manager.send_to_queues({"type": "text_chunk", "content": ""})
    await manager.send_to_queues({"type": "text_chunk", "content": "   "})
    await manager.send_to_queues({"type": "text_chunk", "content": "\n\t"})

    assert tts_queue.empty()
    assert manager.get_tts_chunks_sent() == 0


@pytest.mark.anyio("asyncio")
async def test_sentinel_sent_on_deregister() -> None:
    """Deregistering the TTS queue should emit a sentinel value."""

    manager = StreamingManager()
    tts_queue = asyncio.Queue()

    manager.register_tts_queue(tts_queue)
    manager.deregister_tts_queue()

    assert await asyncio.wait_for(tts_queue.get(), timeout=1.0) is None


@pytest.mark.anyio("asyncio")
async def test_streaming_manager_collect() -> None:
    """Collected chunks should aggregate correctly."""

    manager = StreamingManager()

    manager.collect_chunk("Hello ", "text")
    manager.collect_chunk("world", "text")
    manager.collect_chunk("thinking...", "reasoning")

    results = manager.get_results()

    assert results["text"] == "Hello world"
    assert results["reasoning"] == "thinking..."
    assert results["tool_calls"] == []


@pytest.mark.anyio("asyncio")
async def test_streaming_manager_completion() -> None:
    """Completion should send None to queues."""

    manager = StreamingManager()
    queue = asyncio.Queue()
    manager.add_queue(queue)

    token = manager.create_completion_token()
    await manager.signal_completion(token=token)

    assert await queue.get() is None


@pytest.mark.anyio("asyncio")
async def test_signal_completion_sends_tts_sentinel() -> None:
    """Completion should deregister the TTS queue and send sentinel."""

    manager = StreamingManager()
    queue = asyncio.Queue()
    tts_queue = asyncio.Queue()

    manager.add_queue(queue)
    manager.register_tts_queue(tts_queue)

    token = manager.create_completion_token()
    await manager.signal_completion(token=token)

    assert not manager.is_tts_enabled()
    assert await asyncio.wait_for(tts_queue.get(), timeout=1.0) is None


@pytest.mark.anyio("asyncio")
async def test_create_completion_token() -> None:
    """Token creation should return a UUID formatted string."""

    manager = StreamingManager()
    token = manager.create_completion_token()

    assert isinstance(token, str)
    assert len(token) == 36
    assert token.count("-") == 4


@pytest.mark.anyio("asyncio")
async def test_create_token_twice_raises() -> None:
    """Creating more than one token should raise StreamingError."""

    manager = StreamingManager()
    manager.create_completion_token()

    with pytest.raises(StreamingError, match="already created"):
        manager.create_completion_token()


@pytest.mark.anyio("asyncio")
async def test_signal_completion_without_token_raises() -> None:
    """Calling signal_completion without creating a token should fail."""

    manager = StreamingManager()
    queue = asyncio.Queue()
    manager.add_queue(queue)

    with pytest.raises(CompletionOwnershipError, match="No completion token"):
        await manager.signal_completion(token="some-token")

@pytest.mark.anyio("asyncio")
async def test_signal_completion_with_wrong_token_raises() -> None:
    """An invalid token should raise CompletionOwnershipError."""

    manager = StreamingManager()
    queue = asyncio.Queue()
    manager.add_queue(queue)
    manager.create_completion_token()

    with pytest.raises(CompletionOwnershipError, match="Invalid completion token"):
        await manager.signal_completion(token="00000000-0000-0000-0000-000000000000")


@pytest.mark.anyio("asyncio")
async def test_signal_completion_with_empty_token_raises() -> None:
    """Empty tokens should not be accepted."""

    manager = StreamingManager()
    manager.create_completion_token()

    with pytest.raises(CompletionOwnershipError, match="required but not provided"):
        await manager.signal_completion(token="")


@pytest.mark.anyio("asyncio")
async def test_signal_completion_idempotent() -> None:
    """Calling completion twice with the same token should be a no-op."""

    manager = StreamingManager()
    queue = asyncio.Queue()
    manager.add_queue(queue)
    token = manager.create_completion_token()

    await manager.signal_completion(token=token)
    await manager.signal_completion(token=token)

    assert await queue.get() is None
    assert queue.empty()


@pytest.mark.anyio("asyncio")
async def test_streaming_manager_frontend_only() -> None:
    """frontend_only should only target the last queue."""

    manager = StreamingManager()
    tts_queue = asyncio.Queue()
    frontend_queue = asyncio.Queue()

    manager.add_queue(tts_queue)
    manager.add_queue(frontend_queue)

    await manager.send_to_queues("metadata", queue_type="frontend_only")

    assert frontend_queue.qsize() == 1
    assert tts_queue.qsize() == 0


@pytest.mark.anyio("asyncio")
async def test_streaming_manager_invalid_queue_type() -> None:
    """Invalid queue type should raise StreamingError."""

    manager = StreamingManager()

    with pytest.raises(StreamingError):
        await manager.send_to_queues('data', queue_type='unknown')


@pytest.mark.anyio("asyncio")
async def test_collect_tool_call_records_payload() -> None:
    """Tool call payloads should be tracked for later aggregation."""

    manager = StreamingManager()
    manager.collect_tool_call({"name": "search", "arguments": {"query": "hi"}})

    results = manager.get_results()
    assert results["tool_calls"] == [{"name": "search", "arguments": {"query": "hi"}}]


@pytest.mark.anyio("asyncio")
async def test_integration_streaming_with_tts_queue() -> None:
    """Simulate multiple chunks streaming to frontend and TTS queues."""

    manager = StreamingManager()
    frontend_queue = asyncio.Queue()
    tts_queue = asyncio.Queue()

    manager.add_queue(frontend_queue)
    manager.register_tts_queue(tts_queue)

    chunks = ["Hello, ", "this is ", "a test "]

    for chunk in chunks:
        await manager.send_to_queues({"type": "text_chunk", "content": chunk})

    await manager.send_to_queues({"type": "custom_event", "content": {"foo": "bar"}})

    token = manager.create_completion_token()
    await manager.signal_completion(token=token)

    received_frontend = [await asyncio.wait_for(frontend_queue.get(), timeout=1.0) for _ in range(4)]
    assert [item["content"] for item in received_frontend[:3]] == chunks
    assert received_frontend[3]["type"] == "custom_event"

    received_tts = [await asyncio.wait_for(tts_queue.get(), timeout=1.0) for _ in range(4)]
    assert received_tts[:3] == chunks
    assert received_tts[3] is None
