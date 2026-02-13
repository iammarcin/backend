"""Unit tests for proactive agent streaming registry."""

from __future__ import annotations

import asyncio

import pytest

from features.proactive_agent.streaming_registry import (
    ProactiveStreamingSession,
    create_forwarder_task,
    get_session,
    register_session,
    remove_session,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    from features.proactive_agent import streaming_registry

    streaming_registry._sessions.clear()
    yield
    streaming_registry._sessions.clear()


def test_register_and_get_session():
    session = ProactiveStreamingSession(
        session_id="sess-1",
        manager=None,
        queue=asyncio.Queue(),
        orchestrator=None,
        forwarder_task=None,
        user_id=123,
        tts_settings={"voice": "test"},
    )

    register_session("sess-1", 123, session)

    retrieved = get_session("sess-1", 123)
    assert retrieved is session

    assert get_session("sess-1", 456) is None


def test_remove_session():
    session = ProactiveStreamingSession(
        session_id="sess-1",
        manager=None,
        queue=asyncio.Queue(),
        orchestrator=None,
        forwarder_task=None,
        user_id=123,
        tts_settings=None,
    )

    register_session("sess-1", 123, session)
    removed = remove_session("sess-1", 123)

    assert removed is session
    assert get_session("sess-1", 123) is None


@pytest.mark.asyncio
async def test_forwarder_attaches_session_id(monkeypatch):
    class DummyRegistry:
        def __init__(self) -> None:
            self.messages = []

        async def push_to_user(self, user_id, message, session_scoped=True):
            self.messages.append((user_id, message, session_scoped))
            return True

    from features.proactive_agent import streaming_registry

    dummy_registry = DummyRegistry()
    monkeypatch.setattr(streaming_registry, "get_proactive_registry", lambda: dummy_registry)

    queue: asyncio.Queue = asyncio.Queue()
    task = await create_forwarder_task(queue, user_id=1, session_id="sess-123")

    await queue.put({"type": "audio_chunk", "content": "abc"})
    await queue.put(None)

    await task

    assert dummy_registry.messages
    _, message, _ = dummy_registry.messages[0]
    assert message["session_id"] == "sess-123"
