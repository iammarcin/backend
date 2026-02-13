"""Unit tests for generic tool event emission."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from features.chat.services.streaming.events import (
    _extract_tool_snippet,
    _generate_tool_display_text,
    _get_tool_emoji,
    emit_tool_use_event,
)


class TestToolDisplayText:
    """Test display text generation."""

    def test_web_search_display(self) -> None:
        result = _generate_tool_display_text(
            "web_search",
            {"query": "latest AI news"},
        )
        assert result == "🔍 web_search: latest AI news"

    def test_code_interpreter_display(self) -> None:
        result = _generate_tool_display_text(
            "code_interpreter",
            {"code": "print('hello')"},
        )
        assert result == "💻 code_interpreter: print('hello')"

    def test_multiline_code_truncation(self) -> None:
        result = _generate_tool_display_text(
            "code_interpreter",
            {"code": "import os\nprint('hello')\nprint('world')"},
        )
        assert result == "💻 code_interpreter: import os"

    def test_function_call_display(self) -> None:
        result = _generate_tool_display_text(
            "function_call",
            {
                "name": "get_weather",
                "arguments": {"location": "NYC", "units": "metric"},
            },
        )
        assert "get_weather" in result
        assert "location" in result

    def test_unknown_tool_fallback(self) -> None:
        result = _generate_tool_display_text(
            "custom_tool",
            {"param": "value"},
        )
        assert "🛠️ custom_tool" in result


class TestToolEmoji:
    """Test emoji mapping."""

    def test_known_tools(self) -> None:
        assert _get_tool_emoji("web_search") == "🔍"
        assert _get_tool_emoji("code_interpreter") == "💻"
        assert _get_tool_emoji("google_search") == "🌐"

    def test_unknown_tool(self) -> None:
        assert _get_tool_emoji("unknown_tool") == "🛠️"


class TestToolSnippet:
    """Test snippet extraction helpers."""

    def test_function_call_arguments_are_formatted(self) -> None:
        snippet = _extract_tool_snippet(
            "function_call",
            {
                "name": "lookup_user",
                "arguments": {"id": 123, "expand": True},
            },
        )
        assert snippet.startswith("lookup_user(")
        assert "id=123" in snippet

    def test_non_dict_input_is_stringified(self) -> None:
        snippet = _extract_tool_snippet("custom", [1, 2, 3])
        assert snippet.startswith("[")


@pytest.mark.asyncio
async def test_emit_tool_use_event() -> None:
    """Test tool event emission."""

    manager = MagicMock()
    manager.send_to_queues = AsyncMock()

    await emit_tool_use_event(
        manager=manager,
        provider="openai",
        tool_name="web_search",
        tool_input={"query": "test query"},
        call_id="call_123",
    )

    manager.send_to_queues.assert_called_once()
    event = manager.send_to_queues.call_args[0][0]

    assert event["type"] == "tool_start"
    assert event["data"]["provider"] == "openai"
    assert event["data"]["tool_name"] == "web_search"
    assert event["data"]["tool_input"] == {"query": "test query"}
    assert event["data"]["call_id"] == "call_123"
    assert "display_text" in event["data"]


@pytest.mark.asyncio
async def test_emit_tool_use_event_minimal() -> None:
    """Test tool event with minimal parameters."""

    manager = MagicMock()
    manager.send_to_queues = AsyncMock()

    await emit_tool_use_event(
        manager=manager,
        provider="anthropic",
        tool_name="function_call",
        tool_input={},
    )

    event = manager.send_to_queues.call_args[0][0]

    assert event["type"] == "tool_start"
    assert event["data"]["provider"] == "anthropic"
    assert event["data"]["tool_name"] == "function_call"
    assert "call_id" not in event["data"]
    assert "metadata" not in event["data"]
