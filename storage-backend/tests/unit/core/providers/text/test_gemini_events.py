from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from core.providers.text.gemini import events as gemini_events


async def _noop_emit_tool_use_event(**_: Any) -> None:  # pragma: no cover - helper stub
    return None


@pytest.fixture(autouse=True)
def _patch_emit_tool_use_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_events, "emit_tool_use_event", _noop_emit_tool_use_event)


@pytest.mark.asyncio
async def test_function_call_payload_has_requires_action_flag() -> None:
    chunk = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            function_call=SimpleNamespace(
                                name="lookup",
                                args={"city": "Berlin"},
                            )
                        )
                    ]
                )
            )
        ]
    )

    payloads = await gemini_events.handle_gemini_tool_chunk(
        chunk=chunk,
        manager=object(),
        seen=set(),
    )

    assert payloads
    assert payloads[0]["requires_action"] is False


@pytest.mark.asyncio
async def test_code_execution_payload_has_requires_action_flag() -> None:
    chunk = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            executable_code=SimpleNamespace(
                                code="print('hello')",
                                language="PYTHON",
                            )
                        )
                    ]
                )
            )
        ]
    )

    payloads = await gemini_events.handle_gemini_tool_chunk(
        chunk=chunk,
        manager=object(),
        seen=set(),
    )

    assert payloads
    assert payloads[0]["requires_action"] is False


@pytest.mark.asyncio
async def test_web_search_payload_has_requires_action_flag() -> None:
    chunk = SimpleNamespace(
        grounding_metadata={"web_search_queries": ["weather tomorrow"]}
    )

    payloads = await gemini_events.handle_gemini_tool_chunk(
        chunk=chunk,
        manager=object(),
        seen=set(),
    )

    assert payloads
    assert payloads[0]["requires_action"] is False
