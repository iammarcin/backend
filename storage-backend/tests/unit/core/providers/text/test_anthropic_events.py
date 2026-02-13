from __future__ import annotations

from core.providers.text.anthropic_events import iter_tool_call_payloads


def test_iter_tool_call_payloads_include_requires_action_flag() -> None:
    content_blocks = [
        {
            "type": "tool_use",
            "name": "web_search",
            "input": {"query": "sunrise"},
            "id": "tool_1",
        }
    ]

    payloads = iter_tool_call_payloads(content_blocks)

    assert payloads
    assert payloads[0]["requires_action"] is False
