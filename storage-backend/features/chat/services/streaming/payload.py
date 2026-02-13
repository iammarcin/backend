"""Build the final payload returned by the streaming workflow."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from features.chat.utils.image_workflow import generate_image_from_text

from .collector import StreamCollection
from .tts import maybe_stream_tts


logger = logging.getLogger(__name__)


async def build_streaming_payload(
    *,
    collection: StreamCollection,
    full_text_response: str,
    context,
    settings: Dict[str, Any],
    customer_id: int,
    manager,
    timings: Dict[str, float],
    tts_service,
    tts_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the response dictionary with optional artefacts."""

    result: Dict[str, Any] = {"text_response": full_text_response}
    if collection.reasoning_chunks:
        result["reasoning"] = "".join(collection.reasoning_chunks)
    # claude_session_id preserved for proactive agent compatibility
    if collection.claude_session_id:
        result["claude_session_id"] = collection.claude_session_id
    if collection.tool_calls:
        result["tool_calls"] = list(collection.tool_calls)
        requires_action = any(
            isinstance(call, dict) and call.get("requires_action") is not False
            for call in collection.tool_calls
        )
        if requires_action:
            result["requires_tool_action"] = True
    if collection.requires_tool_action and not result.get("requires_tool_action"):
        result["requires_tool_action"] = True
    # Add tool results for database persistence (e.g., judge verdict)
    if collection.tool_results:
        result["tool_results"] = list(collection.tool_results)
    if collection.chart_payloads:
        result["chart_payloads"] = list(collection.chart_payloads)

    if context.image_mode:
        image_data = await generate_image_from_text(
            text_response=full_text_response,
            input_image_url=context.input_image_url,
            image_mode=context.image_mode,
            settings=settings,
            customer_id=customer_id,
            manager=manager,
            timings=timings,
        )
        result["image_data"] = image_data

    if tts_metadata is not None:
        result["tts"] = tts_metadata
        logger.debug("Using pre-computed TTS metadata from parallel streaming")
    else:
        fallback_metadata = await maybe_stream_tts(
            text_response=full_text_response,
            settings=settings,
            customer_id=customer_id,
            manager=manager,
            timings=timings,
            tts_service=tts_service,
        )
        if fallback_metadata:
            result["tts"] = fallback_metadata

    if collection.is_deep_research:
        result["is_deep_research"] = True
        deep_metadata = collection.deep_research_metadata or {}
        citations = deep_metadata.get("citations") if isinstance(deep_metadata, dict) else None
        if isinstance(citations, list) and citations:
            result["citations"] = citations

        result["research_metadata"] = {
            "stage_count": 3,
            "citations_count": len(citations) if isinstance(citations, list) else 0,
            "notification_tagged": bool(
                deep_metadata.get("notification_tagged") if isinstance(deep_metadata, dict) else False
            ),
            "message_ids": deep_metadata.get("message_ids") if isinstance(deep_metadata, dict) else None,
            "stage_timings": deep_metadata.get("stage_timings") if isinstance(deep_metadata, dict) else None,
            "session_id": deep_metadata.get("session_id") if isinstance(deep_metadata, dict) else None,
            "optimized_prompt": deep_metadata.get("optimized_prompt") if isinstance(deep_metadata, dict) else None,
            "research_response": deep_metadata.get("research_response") if isinstance(deep_metadata, dict) else None,
            "analysis_response": deep_metadata.get("analysis_response") if isinstance(deep_metadata, dict) else None,
            "citations": citations if isinstance(citations, list) else None,
        }

    return result


__all__ = ["build_streaming_payload"]
