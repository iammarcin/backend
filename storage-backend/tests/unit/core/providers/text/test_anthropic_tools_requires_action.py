"""Anthropic tool payload regression tests."""

from __future__ import annotations

from core.providers.text.anthropic_events import iter_tool_call_payloads


def test_tool_payload_includes_requires_action_flag() -> None:
    block = {
        "type": "tool_use",
        "name": "web_search",
        "input": {"query": "ai"},
        "id": "tool_123",
    }

    payloads = iter_tool_call_payloads([block])

    assert payloads
    assert payloads[0]["requires_action"] is False
    assert payloads[0]["toolName"] == "web_search"
