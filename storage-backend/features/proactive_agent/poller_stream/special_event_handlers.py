"""Specialized event handlers for proactive agent streaming.

Handles chart, research, scene, and component update events.
Extracted from event_emitter.py for modularity.
"""

import logging
from typing import Any

from pydantic import ValidationError

from core.connections import get_proactive_registry

from ..schemas import ChartGenerationRequest, DeepResearchRequest
from ..services.chart_handler import ChartHandler
from ..services.deep_research_handler import DeepResearchHandler

logger = logging.getLogger(__name__)


async def handle_chart_event(
    data: dict[str, Any],
    user_id: int,
    session_id: str,
    ai_character_name: str,
    chart_handler: ChartHandler,
) -> None:
    """Handle chart marker - pass through all supported fields.

    Validation errors are logged and skipped to prevent stream crashes.
    """
    chart_data = data.get("chart_data", {})
    try:
        request = ChartGenerationRequest(
            user_id=user_id,
            session_id=session_id,
            ai_character_name=ai_character_name,
            chart_type=chart_data.get("chart_type", "line"),
            title=chart_data.get("title", "Chart"),
            # Optional fields that were previously dropped (M6.4 fix)
            subtitle=chart_data.get("subtitle"),
            chart_id=chart_data.get("chart_id"),
            data=chart_data.get("data"),
            data_query=chart_data.get("data_query"),
            mermaid_code=chart_data.get("mermaid_code"),
            options=chart_data.get("options"),
        )
        await chart_handler.generate_chart(request)
    except (ValidationError, ValueError) as e:
        # Log and skip malformed chart markers - don't crash the stream
        logger.warning(
            f"Skipping invalid chart marker: {e}",
            extra={"session_id": session_id, "chart_data": str(chart_data)[:200]},
        )


async def handle_research_event(
    data: dict[str, Any],
    user_id: int,
    session_id: str,
    ai_character_name: str,
    research_handler: DeepResearchHandler,
) -> None:
    """Handle research marker.

    Validation errors are logged and skipped to prevent stream crashes.
    """
    research_data = data.get("research_data", {})
    try:
        request = DeepResearchRequest(
            user_id=user_id,
            session_id=session_id,
            ai_character_name=ai_character_name,
            query=research_data.get("query", ""),
        )
        await research_handler.execute_research(request)
    except (ValidationError, ValueError) as e:
        logger.warning(
            f"Skipping invalid research marker: {e}",
            extra={"session_id": session_id, "research_data": str(research_data)[:200]},
        )


async def handle_scene_event(
    data: dict[str, Any],
    user_id: int,
    session_id: str,
) -> None:
    """Handle detected scene marker - push to frontend via WebSocket."""
    scene_data = data.get("scene_data", {})

    # Validate scene has required fields
    if not scene_data.get("scene_id"):
        logger.warning(
            "Scene marker missing scene_id, skipping",
            extra={"session_id": session_id},
        )
        return

    if not scene_data.get("components"):
        logger.warning(
            "Scene marker missing components, skipping",
            extra={"session_id": session_id},
        )
        return

    # Push scene event to all user's WebSocket connections
    registry = get_proactive_registry()
    await registry.push_to_user(
        user_id=user_id,
        message={
            "type": "scene",
            "session_id": session_id,
            "content": scene_data,
        },
    )

    logger.info(
        f"Scene emitted: scene_id={scene_data.get('scene_id')}, "
        f"components={len(scene_data.get('components', []))}",
        extra={"session_id": session_id},
    )


async def handle_component_update_event(
    data: dict[str, Any],
    user_id: int,
    session_id: str,
) -> None:
    """Handle component update - push to frontend via WebSocket."""
    update_data = data.get("update_data", {})

    component_id = update_data.get("component_id")
    if not component_id:
        logger.warning(
            "Component update missing component_id, skipping",
            extra={"session_id": session_id},
        )
        return

    content = update_data.get("content")
    if content is None:
        logger.warning(
            "Component update missing content, skipping",
            extra={"session_id": session_id},
        )
        return

    append = update_data.get("append", False)

    registry = get_proactive_registry()
    await registry.push_to_user(
        user_id=user_id,
        message={
            "type": "component_update",
            "session_id": session_id,
            "component_id": component_id,
            "content": content,
            "append": append,
        },
    )

    logger.debug(
        f"Component update: component_id={component_id}, "
        f"append={append}, content_length={len(str(content))}",
        extra={"session_id": session_id},
    )


__all__ = [
    "handle_chart_event",
    "handle_research_event",
    "handle_scene_event",
    "handle_component_update_event",
]
