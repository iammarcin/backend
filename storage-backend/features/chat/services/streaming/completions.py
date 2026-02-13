"""Helpers for emitting completion events after a streaming session."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from .helpers import augment_metadata
from .events import emit_deep_research_completed

logger = logging.getLogger(__name__)


async def emit_completion_events(
    *,
    manager,
    customer_id: int,
    full_text_response: str,
    claude_session_id: Optional[str] = None,
    is_deep_research: bool = False,
):
    """Emit completion events, including clarification prompts when present.

    The claude_session_id parameter is preserved for proactive agent compatibility.
    """

    # Build metadata with claude_session_id if present (used by proactive agent)
    completion_metadata: Dict[str, Any] = {}
    if claude_session_id:
        completion_metadata["claude_session_id"] = claude_session_id

    parsed_response: Optional[Dict[str, Any]] = None
    is_clarification = False

    try:
        candidate = full_text_response.strip()
        if candidate:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                parsed_response = parsed
    except (json.JSONDecodeError, ValueError):
        logger.debug(
            "Response is not valid JSON, treating as regular text (customer=%s)",
            customer_id,
        )

    if parsed_response and "questions" in parsed_response:
        is_clarification = True
        logger.info(
            "Detected clarification questions (customer=%s, questions=%s)",
            customer_id,
            len(parsed_response.get("questions", [])),
        )
        await manager.send_to_queues(
            {
                "type": "custom_event",
                "event_type": "clarificationQuestions",
                "content": parsed_response,
            }
        )

    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "textGenerationCompleted",
            "content": {
                "full_response": full_text_response,
                "metadata": augment_metadata(
                    base=completion_metadata,
                    extra={"is_clarification": True} if is_clarification else None,
                ),
            },
        }
    )

    if is_deep_research:
        await emit_deep_research_completed(manager=manager, citations_count=0)


__all__ = ["emit_completion_events"]
