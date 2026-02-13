"""Orchestration logic for the deep research streaming workflow."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException

from core.exceptions import ProviderError
from core.streaming.manager import StreamingManager
from ..events import emit_deep_research_completed, emit_deep_research_started
from .context import deep_research_context
from ..deep_research_config import validate_deep_research_settings
from ..deep_research_helpers import (
    emit_deep_research_error,
    extract_chat_history,
    extract_user_query,
)
from .outcome import DeepResearchOutcome
from .stages import (
    analyze_research_findings,
    execute_deep_research,
    optimize_research_prompt,
)


logger = logging.getLogger("features.chat.services.streaming.deep_research")


async def stream_deep_research_response(
    prompt: List[Dict[str, Any]],
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    session_id: Optional[str] = None,
) -> DeepResearchOutcome:
    """Orchestrate the deep research workflow and return outcome object."""

    try:
        validated_settings = validate_deep_research_settings(settings)
    except ValueError as exc:
        logger.error(
            "Invalid deep research settings",
            extra={"customer_id": customer_id, "error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings_local = validated_settings
    started_at = datetime.utcnow()
    logger.info(
        "Deep research workflow started",
        extra={
            "customer_id": customer_id,
            "session_id": session_id,
            "timestamp": started_at.isoformat(),
            "primary_model": settings_local.get("text", {}).get("model"),
            "research_model": settings_local.get("text", {}).get("deep_research_model"),
        },
    )

    await emit_deep_research_started(manager)

    citations: List[Dict[str, Any]] = []
    message_ids: Optional[Dict[str, int]] = None
    resolved_session_id = session_id
    stage_timings: Dict[str, float] = {}
    collected_chunks: List[str] = []
    chunk_count = 0

    try:
        async with deep_research_context():
            user_query = extract_user_query(prompt)
            chat_history = extract_chat_history(settings_local)

            start_time = time.time()
            try:
                optimized_prompt = await optimize_research_prompt(
                    user_query=user_query,
                    chat_history=chat_history,
                    settings=settings_local,
                    customer_id=customer_id,
                    manager=manager,
                )
                stage_timings["optimization"] = time.time() - start_time
                logger.info("Stage 1: Optimization succeeded", extra={"customer_id": customer_id})
            except Exception as exc:
                logger.error(
                    "Deep research failed: prompt optimization error",
                    extra={"customer_id": customer_id, "error": str(exc)},
                    exc_info=True,
                )
                await emit_deep_research_error(
                    manager, f"Failed to optimize research prompt: {str(exc)}"
                )
                raise ProviderError(
                    "Deep research optimization stage failed",
                    provider="openai",
                    original_error=exc,
                ) from exc

            start_time = time.time()
            research_response, citations = await execute_deep_research(
                optimized_prompt=optimized_prompt,
                settings=settings_local,
                customer_id=customer_id,
                manager=manager,
            )
            stage_timings["research"] = time.time() - start_time

            start_time = time.time()
            try:
                async for chunk in analyze_research_findings(
                    research_response=research_response,
                    original_query=user_query,
                    chat_history=chat_history,
                    optimized_prompt=optimized_prompt,
                    settings=settings_local,
                    customer_id=customer_id,
                    manager=manager,
                ):
                    chunk_count += 1
                    collected_chunks.append(chunk)
                    await manager.send_to_queues({"type": "text_chunk", "content": chunk})
                    manager.collect_chunk(chunk, "text")
                stage_timings["analysis"] = time.time() - start_time
                logger.info("Stage 3: Analysis succeeded", extra={"customer_id": customer_id})
            except Exception as exc:
                logger.error(
                    "Deep research failed: analysis streaming error",
                    extra={"customer_id": customer_id, "error": str(exc)},
                    exc_info=True,
                )
                await emit_deep_research_error(
                    manager, f"Failed to analyze research results: {str(exc)}"
                )
                raise ProviderError(
                    "Deep research analysis stage failed",
                    provider="openai",
                    original_error=exc,
                ) from exc

            await emit_deep_research_completed(
                manager,
                citations_count=len(citations),
                metadata={"session_id": resolved_session_id},
            )

        logger.info(
            "Deep research workflow completed",
            extra={
                "customer_id": customer_id,
                "session_id": resolved_session_id,
                "total_duration": sum(stage_timings.values()),
                "stage_timings": stage_timings,
                "citations_count": len(citations),
                "chunks_sent": chunk_count,
            },
        )

        return DeepResearchOutcome(
            session_id=resolved_session_id,
            optimized_prompt=optimized_prompt,
            research_response=research_response,
            citations=citations,
            stage_timings=stage_timings,
            message_ids=message_ids,
            notification_tagged=message_ids is not None,
            analysis_chunks=list(collected_chunks),
        )
    except Exception as exc:
        logger.error(
            "Deep research orchestration failed",
            extra={
                "customer_id": customer_id,
                "session_id": resolved_session_id,
                "stage_timings": stage_timings,
                "error": str(exc),
            },
            exc_info=True,
        )
        await emit_deep_research_error(manager, f"Deep research failed: {exc}")
        raise


__all__ = ["stream_deep_research_response"]
