"""Helpers for emitting text-related streaming events."""

from __future__ import annotations

from typing import Any, Dict

from core.streaming.manager import StreamingManager


async def emit_text_timing_event(
    manager: StreamingManager,
    timings: Dict[str, float],
) -> None:
    """Push text timing metrics to the streaming queues for observability."""

    sent_time = timings.get("text_request_sent_time")
    first_response_time = timings.get("text_first_response_time")

    payload: Dict[str, Any] = {}
    if sent_time is not None:
        payload["textRequestSentTime"] = sent_time
    if first_response_time is not None:
        payload["textFirstResponseTime"] = first_response_time
    if sent_time is not None and first_response_time is not None:
        payload["textFirstTokenLatency"] = max(0.0, first_response_time - sent_time)

    if not payload:
        return

    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "textTimings",
            "content": payload,
        }
    )
