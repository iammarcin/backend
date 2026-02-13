"""Tests for OpenAI Responses API tool detection utilities."""

from core.providers.text.utils.responses_tools import _extract_plain_tool_items


def test_extract_web_search_call() -> None:
    """Test that web_search_call items are properly detected.

    web_search_call items have a different structure than typical tools - they
    don't have input fields but should still be detected based on their type.
    """

    # Simulate the OpenAI Responses API response structure for web search
    response_data = {
        "output": [
            {
                "type": "web_search_call",
                "id": "ws_67c9fa0502748190b7dd390736892e100be649c1a5ff9609",
                "status": "completed"
            },
            {
                "type": "message",
                "id": "msg_123",
                "content": [{"type": "output_text", "text": "Here's what I found..."}]
            }
        ]
    }

    tool_items = _extract_plain_tool_items(response_data)

    # Should detect the web_search_call
    assert len(tool_items) == 1
    assert tool_items[0]["type"] == "web_search_call"
    assert tool_items[0]["id"] == "ws_67c9fa0502748190b7dd390736892e100be649c1a5ff9609"


def test_extract_web_search_with_query() -> None:
    """Test extraction of web_search tool with query field."""

    response_data = {
        "output": [
            {
                "type": "web_search",
                "name": "web_search",
                "query": "latest AI news",
                "id": "search_123"
            }
        ]
    }

    tool_items = _extract_plain_tool_items(response_data)

    assert len(tool_items) == 1
    assert tool_items[0]["type"] == "web_search"
    assert tool_items[0]["query"] == "latest AI news"


def test_extract_code_interpreter() -> None:
    """Test extraction of code_interpreter tool."""

    response_data = {
        "output": [
            {
                "type": "code_interpreter",
                "name": "code_interpreter",
                "code": "print('hello')",
                "id": "code_123"
            }
        ]
    }

    tool_items = _extract_plain_tool_items(response_data)

    assert len(tool_items) == 1
    assert tool_items[0]["type"] == "code_interpreter"
    assert tool_items[0]["code"] == "print('hello')"


def test_extract_function_call() -> None:
    """Test extraction of function_call tool."""

    response_data = {
        "output": [
            {
                "type": "function_call",
                "name": "get_weather",
                "arguments": {"location": "NYC"},
                "id": "func_123"
            }
        ]
    }

    tool_items = _extract_plain_tool_items(response_data)

    assert len(tool_items) == 1
    assert tool_items[0]["type"] == "function_call"
    assert tool_items[0]["name"] == "get_weather"
    assert tool_items[0]["arguments"] == {"location": "NYC"}


def test_no_tool_items() -> None:
    """Test that non-tool items are not detected."""

    response_data = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Hello"}]
            }
        ]
    }

    tool_items = _extract_plain_tool_items(response_data)

    assert len(tool_items) == 0


def test_multiple_tool_items() -> None:
    """Test extraction of multiple tool items in one response."""

    response_data = {
        "output": [
            {
                "type": "web_search_call",
                "id": "ws_123",
                "status": "completed"
            },
            {
                "type": "code_interpreter",
                "code": "x = 1 + 1",
                "id": "code_456"
            }
        ]
    }

    tool_items = _extract_plain_tool_items(response_data)

    assert len(tool_items) == 2
    assert tool_items[0]["type"] == "web_search_call"
    assert tool_items[1]["type"] == "code_interpreter"


def test_nested_tool_items() -> None:
    """Test that tool items are found even when nested deeply."""

    response_data = {
        "data": {
            "output": {
                "items": [
                    {
                        "type": "web_search_call",
                        "id": "ws_nested",
                        "status": "completed"
                    }
                ]
            }
        }
    }

    tool_items = _extract_plain_tool_items(response_data)

    assert len(tool_items) == 1
    assert tool_items[0]["type"] == "web_search_call"
    assert tool_items[0]["id"] == "ws_nested"
