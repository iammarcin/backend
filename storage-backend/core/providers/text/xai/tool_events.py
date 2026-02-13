"""Utility helpers for emitting xAI tool usage events."""

from __future__ import annotations

import json
import logging
from typing import Any, Set

from core.streaming.manager import StreamingManager
from features.chat.services.streaming.events import emit_tool_use_event

logger = logging.getLogger(__name__)


async def emit_xai_tool_events(
    *,
    calls: list[dict[str, Any]],
    manager: StreamingManager,
    seen: Set[str],
) -> None:
    """Emit tool usage events for server-side tool invocations."""

    if not calls:
        return

    for call in calls:
        call_id = call.get("id") or call.get("call_id")

        function_obj = call.get("function", {})
        name = function_obj.get("name") or call.get("name") or call.get("type") or "function_call"
        arguments = (
            function_obj.get("arguments")
            or call.get("arguments")
            or call.get("input")
            or {}
        )

        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
                arguments = parsed
            except ValueError:
                pass

        if isinstance(arguments, (dict, list)):
            serialized_args = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        else:
            serialized_args = str(arguments)

        dedupe_key = f"{name}:{call_id}:{serialized_args}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        logger.info("xAI tool call detected: %s id=%s", name, call_id or "<none>")

        await emit_tool_use_event(
            manager=manager,
            provider="xai",
            tool_name=str(name),
            tool_input=arguments,
            call_id=str(call_id) if call_id else None,
        )


__all__ = ["emit_xai_tool_events"]
