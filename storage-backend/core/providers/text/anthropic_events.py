"""Event helpers for Anthropic streaming tool calls."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from core.streaming.manager import StreamingManager
from features.chat.services.streaming.events import emit_tool_use_event

logger = logging.getLogger(__name__)


async def emit_anthropic_tool_events(
    *,
    content_blocks: Any,
    manager: StreamingManager | None,
    seen: Set[str],
) -> None:
    """Emit tool usage events extracted from Anthropic content blocks."""

    if manager is None or not content_blocks:
        return

    for block in content_blocks:
        block_data = normalise_content_block(block)
        block_type = block_data.get("type")
        if block_type not in ("tool_use", "server_tool_use"):
            continue

        tool_id = block_data.get("id")
        if tool_id and tool_id in seen:
            continue

        tool_name = block_data.get("name")
        tool_input = block_data.get("input")

        if tool_id:
            seen.add(str(tool_id))

        if not tool_name:
            continue

        payload = tool_input if isinstance(tool_input, dict) else {"input": tool_input}

        logger.info(
            "Anthropic tool use detected: %s (type=%s, id=%s)",
            tool_name,
            block_type,
            tool_id or "<none>",
        )

        await emit_tool_use_event(
            manager=manager,
            provider="anthropic",
            tool_name=str(tool_name),
            tool_input=payload or {},
            call_id=str(tool_id) if tool_id else None,
        )


def iter_tool_call_payloads(content_blocks: Any) -> List[dict[str, Any]]:
    payloads: List[dict[str, Any]] = []
    if not content_blocks:
        return payloads

    for block in content_blocks:
        block_data = normalise_content_block(block)
        block_type = block_data.get("type")
        if block_type not in ("tool_use", "server_tool_use"):
            continue

        tool_name = block_data.get("name")
        if not tool_name:
            continue

        tool_input = block_data.get("input")
        tool_id = block_data.get("id")
        payload = {
            "name": tool_name,
            "toolName": tool_name,
            "input": tool_input or {},
            "toolInput": tool_input or {},
            "id": tool_id,
            "callId": tool_id,
            "provider": "anthropic",
            "requires_action": False,
        }
        logger.debug(
            "Anthropic tool payload created: name=%s requires_action=%s",
            tool_name,
            payload["requires_action"],
        )
        payloads.append(payload)

    return payloads


def normalise_content_block(block: Any) -> Dict[str, Any]:
    if isinstance(block, dict):
        return block

    normalised: Dict[str, Any] = {}
    for attr in ("type", "id", "name", "input"):
        value = getattr(block, attr, None)
        if value is not None:
            normalised[attr] = value
    return normalised


__all__ = ["emit_anthropic_tool_events", "iter_tool_call_payloads", "normalise_content_block"]
