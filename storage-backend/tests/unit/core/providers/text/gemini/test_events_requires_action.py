"""Gemini event payload regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from core.providers.text.gemini import events as gemini_events


async def _noop_emit_tool_use_event(**_: Any) -> None:  # pragma: no cover - helper
    return None


@pytest.fixture(autouse=True)
def _patch_emitters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_events, "emit_tool_use_event", _noop_emit_tool_use_event)


@pytest.mark.asyncio
async def test_grounding_payload_marks_requires_action_false() -> None:
    chunk = SimpleNamespace(grounding_metadata={"web_search_queries": ["ai news"]})

    payloads = await gemini_events.handle_gemini_tool_chunk(
        chunk=chunk,
        manager=object(),
        seen=set(),
    )

    assert payloads
    assert all(payload.get("requires_action") is False for payload in payloads)


@pytest.mark.asyncio
async def test_function_call_payload_marks_requires_action_false() -> None:
    part = SimpleNamespace(
        function_call=SimpleNamespace(name="lookup", args={"city": "Berlin"})
    )
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
    chunk = SimpleNamespace(candidates=[candidate])

    payloads = await gemini_events.handle_gemini_tool_chunk(
        chunk=chunk,
        manager=object(),
        seen=set(),
    )

    assert payloads
    assert payloads[0]["requires_action"] is False
