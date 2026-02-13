"""Event helpers for semantic prompt enhancement."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.streaming.manager import StreamingManager

from .utils.settings_parser import SemanticSearchSettings


async def send_context_added_event(
    *,
    manager: StreamingManager,
    result_count: int,
    token_count: int,
    settings: SemanticSearchSettings,
    search_mode: str | None = None,
    session_results: list[dict[str, Any]] | None = None,
) -> None:
    """Send WebSocket event to notify frontend that semantic context was added."""

    event_content: dict[str, Any] = {
        "type": "semanticContextAdded",
        "result_count": result_count,
        "tokens_used": token_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if search_mode:
        event_content["search_mode"] = search_mode
    if session_results:
        event_content["session_results"] = session_results

    if settings.has_filters:
        filters_payload: dict[str, Any] = {}

        if settings.tags:
            filters_payload["tags"] = settings.tags

        if settings.date_range:
            filters_payload["date_range"] = {
                "start": settings.date_range[0],
                "end": settings.date_range[1],
            }

        if settings.message_type:
            filters_payload["message_type"] = settings.message_type

        if settings.session_ids:
            filters_payload["session_ids"] = settings.session_ids

        if filters_payload:
            event_content["filters_applied"] = filters_payload

    await manager.send_to_queues(
        {
            "type": "custom_event",
            "content": event_content,
        }
    )


__all__ = ["send_context_added_event"]
