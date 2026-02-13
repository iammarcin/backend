from __future__ import annotations

from typing import Any, Dict, Set
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.providers.text.openai_responses.tool_events import (
    ToolSeenKey,
    emit_tool_events,
)


def _build_function_call_event(
    event_type: str,
    *,
    call_id: str | None = None,
    arguments: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": event_type,
        "function_call_arguments": {
            "type": "function_call",
            "name": "generate_image",
            "arguments": arguments or {"prompt": "cat"},
        },
    }

    if call_id:
        payload["function_call_arguments"]["id"] = call_id

    return payload


@pytest.mark.asyncio
async def test_emit_tool_events_skips_incomplete_events() -> None:
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()
    seen: Set[ToolSeenKey] = set()

    start_event = _build_function_call_event(
        "response.function_call_arguments.start",
        call_id="call_1",
    )
    await emit_tool_events(payload=start_event, manager=manager, seen=seen)

    manager.send_to_queues.assert_not_called()

    done_event = _build_function_call_event(
        "response.function_call_arguments.done",
        call_id="call_1",
    )
    await emit_tool_events(payload=done_event, manager=manager, seen=seen)

    manager.send_to_queues.assert_called_once()


@pytest.mark.asyncio
async def test_emit_tool_events_deduplicates_by_call_id() -> None:
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()
    seen: Set[ToolSeenKey] = set()

    first = _build_function_call_event(
        "response.function_call_arguments.done",
        call_id="call_dup",
        arguments={"prompt": "cat"},
    )
    second = _build_function_call_event(
        "response.function_call_arguments.done",
        call_id="call_dup",
        arguments={"prompt": "cat", "style": "oil"},
    )

    await emit_tool_events(payload=first, manager=manager, seen=seen)
    await emit_tool_events(payload=second, manager=manager, seen=seen)

    manager.send_to_queues.assert_called_once()
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_emit_tool_events_fallback_dedup_without_call_id() -> None:
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()
    seen: Set[ToolSeenKey] = set()

    payload = _build_function_call_event(
        "response.function_call_arguments.done",
        arguments={"prompt": "cat"},
    )

    await emit_tool_events(payload=payload, manager=manager, seen=seen)
    await emit_tool_events(payload=payload, manager=manager, seen=seen)

    manager.send_to_queues.assert_called_once()
    assert len(seen) == 1


def _build_web_search_event(event_type: str, *, status: str = "completed") -> Dict[str, Any]:
    return {
        "type": event_type,
        "item": {
            "type": "web_search_call",
            "status": status,
            "call_id": "web_1",
            "action": {"query": "latest ai news"},
        },
    }


@pytest.mark.asyncio
async def test_emit_tool_events_handles_web_search_completed_event() -> None:
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()
    seen: Set[ToolSeenKey] = set()

    payload = _build_web_search_event("response.web_search.completed")

    await emit_tool_events(payload=payload, manager=manager, seen=seen)

    manager.send_to_queues.assert_called_once()


@pytest.mark.asyncio
async def test_emit_tool_events_skips_incomplete_web_search_event() -> None:
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()
    seen: Set[ToolSeenKey] = set()

    payload = _build_web_search_event(
        "response.web_search.started",
        status="in_progress",
    )

    await emit_tool_events(payload=payload, manager=manager, seen=seen)

    manager.send_to_queues.assert_not_called()


@pytest.mark.asyncio
async def test_emit_tool_events_handles_output_item_added_web_search() -> None:
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()
    seen: Set[ToolSeenKey] = set()

    payload = _build_web_search_event("response.output_item.added")

    await emit_tool_events(payload=payload, manager=manager, seen=seen)

    manager.send_to_queues.assert_called_once()


@pytest.mark.asyncio
async def test_emit_tool_events_skips_output_item_if_not_completed() -> None:
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()
    seen: Set[ToolSeenKey] = set()

    payload = _build_web_search_event(
        "response.output_item.added",
        status="in_progress",
    )

    await emit_tool_events(payload=payload, manager=manager, seen=seen)

    manager.send_to_queues.assert_not_called()
