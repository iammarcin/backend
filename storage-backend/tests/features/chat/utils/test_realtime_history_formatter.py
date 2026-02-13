"""Tests for realtime chat history formatter utilities."""

from __future__ import annotations

from features.chat.utils.realtime_history_formatter import (
    format_chat_history_for_realtime,
)


def test_format_chat_history_converts_roles_and_types() -> None:
    """Ensure both user and assistant history entries are converted."""

    chat_history = [
        {"role": "user", "content": [{"type": "text", "text": "count to 3"}]},
        {"role": "assistant", "content": "1\n2\n3"},
    ]

    events = format_chat_history_for_realtime(chat_history)

    assert len(events) == 2

    user_event = events[0]
    assert user_event["type"] == "conversation.item.create"
    assert user_event["item"]["role"] == "user"
    assert user_event["item"]["content"] == [
        {"type": "input_text", "text": "count to 3"}
    ]

    assistant_event = events[1]
    assert assistant_event["item"]["role"] == "assistant"
    assert assistant_event["item"]["content"] == [
        {"type": "text", "text": "1\n2\n3"}
    ]


def test_format_chat_history_skips_invalid_entries() -> None:
    """Invalid entries should be ignored gracefully."""

    chat_history = [
        {"role": "user", "content": "hello"},
        "not-a-dict",
        {"role": "assistant", "content": []},
        {"role": "assistant", "content": {"type": "text", "text": "reply"}},
    ]

    events = format_chat_history_for_realtime(chat_history)

    assert len(events) == 2
    assert events[0]["item"]["role"] == "user"
    assert events[0]["item"]["content"] == [
        {"type": "input_text", "text": "hello"}
    ]
    assert events[1]["item"]["role"] == "assistant"
    assert events[1]["item"]["content"] == [
        {"type": "text", "text": "reply"}
    ]


def test_format_chat_history_empty_input() -> None:
    """Empty history should return an empty list."""

    assert format_chat_history_for_realtime([]) == []
    assert format_chat_history_for_realtime(None) == []
