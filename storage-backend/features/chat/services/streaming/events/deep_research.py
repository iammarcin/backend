"""Deep research streaming event helpers."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.streaming.manager import StreamingManager


logger = logging.getLogger(__name__)


async def emit_deep_research_event(
    manager: StreamingManager,
    event_type: str,
    stage: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit deep research progress event."""

    content = {
        "type": event_type,
        "message": message,
        "stage": stage,
    }
    if metadata:
        content.update(metadata)

    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "deepResearch",
            "content": content,
        }
    )
    logger.info("Deep research event: %s (stage: %s)", event_type, stage)


async def emit_deep_research_started(manager: StreamingManager) -> None:
    """Emit event when deep research begins."""

    await emit_deep_research_event(
        manager=manager,
        event_type="deepResearchStarted",
        stage="initialization",
        message="Starting deep research workflow",
    )


async def emit_deep_research_optimizing(manager: StreamingManager) -> None:
    """Emit event when prompt optimization begins."""

    await emit_deep_research_event(
        manager=manager,
        event_type="deepResearchOptimizing",
        stage="optimization",
        message="Optimizing research prompt",
    )


async def emit_deep_research_searching(
    manager: StreamingManager,
    optimized_prompt: Optional[str] = None,
) -> None:
    """Emit event when research search begins."""

    metadata: Dict[str, Any] = {}
    if optimized_prompt:
        metadata["optimizedPrompt"] = optimized_prompt[:200]

    await emit_deep_research_event(
        manager=manager,
        event_type="deepResearchSearching",
        stage="research",
        message="Searching web sources via Perplexity",
        metadata=metadata or None,
    )


async def emit_deep_research_analyzing(manager: StreamingManager) -> None:
    """Emit event when analysis stage begins."""

    await emit_deep_research_event(
        manager=manager,
        event_type="deepResearchAnalyzing",
        stage="analysis",
        message="Analyzing research findings",
    )


async def emit_deep_research_completed(
    manager: StreamingManager,
    citations_count: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit event when deep research completes."""

    payload = {"citationsCount": citations_count, "tag": "notification"}
    if metadata:
        payload.update(metadata)

    await emit_deep_research_event(
        manager=manager,
        event_type="deepResearchCompleted",
        stage="completed",
        message="Deep research completed",
        metadata=payload,
    )


__all__ = [
    "emit_deep_research_event",
    "emit_deep_research_started",
    "emit_deep_research_optimizing",
    "emit_deep_research_searching",
    "emit_deep_research_analyzing",
    "emit_deep_research_completed",
]
