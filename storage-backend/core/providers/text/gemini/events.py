"""Utilities for translating Gemini streaming payloads into custom events."""

from __future__ import annotations

import logging
from typing import Any, List, Set

from core.streaming.manager import StreamingManager
from features.chat.services.streaming.events import emit_tool_use_event

from .event_emitters import process_candidate
from .grounding_emitters import emit_grounding_events

logger = logging.getLogger(__name__)


async def handle_gemini_tool_chunk(
    *,
    chunk: Any,
    manager: StreamingManager | None,
    seen: Set[str],
) -> List[dict[str, Any]]:
    """Inspect a streaming chunk for tool usage and emit events."""

    payloads: List[dict[str, Any]] = []
    if manager is None or chunk is None:
        return payloads

    candidates = getattr(chunk, "candidates", None)
    if candidates:
        for candidate in candidates:
            payloads.extend(
                await process_candidate(
                    candidate=candidate, manager=manager, seen=seen
                )
            )

    grounding = getattr(chunk, "grounding_metadata", None)
    if grounding:
        payloads.extend(
            await emit_grounding_events(
                grounding=grounding, manager=manager, seen=seen
            )
        )

    return payloads


__all__ = ["handle_gemini_tool_chunk", "emit_tool_use_event"]
