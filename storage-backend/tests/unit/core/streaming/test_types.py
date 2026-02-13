"""Tests for streaming types."""

from core.streaming.types import StreamEvent, StreamEventType


def test_stream_event_creation():
    event = StreamEvent(type=StreamEventType.TEXT, content="hello")
    assert event.type == StreamEventType.TEXT
    assert event.metadata == {}
