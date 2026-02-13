"""Chart event emission helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.pydantic_schemas import ChartPayload
    from core.streaming.manager import StreamingManager

logger = logging.getLogger(__name__)


async def emit_chart_generation_started(
    manager: "StreamingManager",
    *,
    chart_type: str,
    title: str,
) -> None:
    """Emit event signalling that chart generation has started."""
    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "chartGenerationStarted",
            "content": {
                "chart_type": chart_type,
                "title": title,
            },
        }
    )
    logger.debug("chartGenerationStarted emitted for %s (%s)", title, chart_type)


async def emit_chart_generated(
    manager: "StreamingManager",
    payload: "ChartPayload",
) -> None:
    """Emit completed chart payload to all connected queues."""
    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "chartGenerated",
            "content": payload.model_dump(mode="json"),
        }
    )
    logger.info(
        "chartGenerated emitted for %s (%s)", payload.chart_id, payload.chart_type.value
    )


async def emit_chart_error(
    manager: "StreamingManager",
    *,
    error_message: str,
    chart_type: str | None = None,
    title: str | None = None,
) -> None:
    """Emit chart error notification."""
    content = {"error": error_message}
    if chart_type:
        content["chart_type"] = chart_type
    if title:
        content["title"] = title

    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "chartError",
            "content": content,
        }
    )
    logger.warning(
        "chartError emitted for %s (%s): %s",
        title or "unknown chart",
        chart_type or "unknown",
        error_message,
    )


__all__ = [
    "emit_chart_generation_started",
    "emit_chart_generated",
    "emit_chart_error",
]
