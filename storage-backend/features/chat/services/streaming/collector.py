"""Helpers for collecting streamed chunks from providers."""

from __future__ import annotations

import logging
import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.streaming.manager import StreamingManager

from .standard_provider import stream_standard_response


logger = logging.getLogger(__name__)


@dataclass
class StreamCollection:
    """Result of streaming from a provider."""

    chunks: List[str]
    reasoning_chunks: List[str]
    claude_session_id: Optional[str]  # Preserved for proactive agent flows
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]  # Tool execution results (for database persistence)
    requires_tool_action: bool
    is_deep_research: bool = False
    deep_research_metadata: Optional[Dict[str, Any]] = None
    chart_payloads: List[Dict[str, Any]] = field(default_factory=list)


async def collect_streaming_chunks(
    *,
    provider: Any,
    manager: StreamingManager,
    prompt_text: str,
    model: str,
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str],
    settings: Dict[str, Any],
    timings: Dict[str, float],
    user_input: Optional[Dict[str, Any]] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    customer_id: Optional[int] = None,
    session_id: Optional[str] = None,
    runtime=None,
) -> StreamCollection:
    """Stream from the provider and normalise the response payloads."""

    text_settings = settings.get("text", {}) if isinstance(settings, dict) else {}

    deep_research_enabled = bool(text_settings.get("deep_research_enabled", False))
    if deep_research_enabled:
        logger.info(
            "Deep research enabled for customer %s", customer_id if customer_id is not None else "unknown"
        )
        from .deep_research import DeepResearchOutcome, stream_deep_research_response

        resolved_session_id = session_id
        if resolved_session_id is None and isinstance(user_input, dict):
            resolved_session_id = user_input.get("session_id")

        response = stream_deep_research_response(
            prompt=messages or [],
            settings=settings,
            customer_id=customer_id or 0,
            manager=manager,
            session_id=resolved_session_id,
        )

        streamed_chunks: List[str] = []
        outcome: DeepResearchOutcome | None = None

        if inspect.isawaitable(response):
            outcome = await response
        else:
            async for chunk in response:
                streamed_chunks.append(chunk)
            outcome_payload = getattr(response, "deep_research_outcome", None)
            if isinstance(outcome_payload, dict):
                outcome_candidate = outcome_payload.get("value") or outcome_payload.get("outcome")
            else:
                outcome_candidate = outcome_payload
            if isinstance(outcome_candidate, DeepResearchOutcome):
                outcome = outcome_candidate

        if outcome is None and isinstance(response, DeepResearchOutcome):
            outcome = response

        if outcome is None:
            raise RuntimeError("Deep research workflow did not produce an outcome")

        if not streamed_chunks and outcome.analysis_chunks:
            streamed_chunks = list(outcome.analysis_chunks)

        if not streamed_chunks:
            streamed_chunks = list(manager.results.get("text_chunks", []))

        metadata = {
            "session_id": outcome.session_id,
            "citations": outcome.citations,
            "stage_timings": outcome.stage_timings,
            "message_ids": outcome.message_ids,
            "notification_tagged": outcome.notification_tagged,
            "optimized_prompt": outcome.optimized_prompt,
            "research_response": outcome.research_response,
            "analysis_response": "".join(streamed_chunks),
        }

        return StreamCollection(
            chunks=streamed_chunks,
            reasoning_chunks=[],
            claude_session_id=None,
            tool_calls=[],
            tool_results=[],
            requires_tool_action=False,
            is_deep_research=True,
            deep_research_metadata=metadata,
        )

    standard_outcome = await stream_standard_response(
        provider=provider,
        manager=manager,
        prompt_text=prompt_text,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        user_input=user_input,
        messages=messages,
        settings=settings,
        runtime=runtime,
        session_id=session_id,
    )
    return StreamCollection(
        chunks=standard_outcome.text_chunks,
        reasoning_chunks=standard_outcome.reasoning_chunks,
        claude_session_id=None,
        tool_calls=standard_outcome.tool_calls,
        tool_results=[],  # Standard provider doesn't execute internal tools
        requires_tool_action=standard_outcome.requires_tool_action,
        chart_payloads=[],
    )


__all__ = ["StreamCollection", "collect_streaming_chunks"]
