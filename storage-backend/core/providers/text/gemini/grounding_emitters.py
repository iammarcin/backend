"""Grounding metadata event helpers for Gemini streaming."""

from __future__ import annotations

import logging
from typing import Any, List, Set

from core.streaming.manager import StreamingManager
from features.chat.services.streaming.events import emit_tool_use_event

logger = logging.getLogger(__name__)


async def emit_grounding_events(
    *,
    grounding: Any,
    manager: StreamingManager,
    seen: Set[str],
) -> List[dict[str, Any]]:
    payloads: List[dict[str, Any]] = []

    if isinstance(grounding, dict):
        queries = (
            grounding.get("web_search_queries")
            or grounding.get("webSearchQueries")
            or grounding.get("search_queries")
            or grounding.get("searchQueries")
            or grounding.get("queries")
        )
    else:
        queries = (
            getattr(grounding, "web_search_queries", None)
            or getattr(grounding, "webSearchQueries", None)
            or getattr(grounding, "search_queries", None)
            or getattr(grounding, "searchQueries", None)
            or getattr(grounding, "queries", None)
        )

    if not queries:
        if isinstance(grounding, dict):
            logger.debug("Grounding dict keys: %s", list(grounding.keys()))
        return payloads

    if not isinstance(queries, list):
        queries = (
            list(queries)
            if hasattr(queries, "__iter__") and not isinstance(queries, str)
            else [queries]
        )

    for query in queries:
        if not isinstance(query, str):
            logger.debug("Skipping non-string query: %s (type=%s)", query, type(query).__name__)
            continue
        normalized = query.strip()
        if not normalized:
            continue

        dedupe_key = f"web_search:{normalized}"
        if dedupe_key in seen:
            logger.debug("Skipping duplicate query: %s", normalized)
            continue
        seen.add(dedupe_key)

        logger.info("Gemini web search query detected: %s", normalized)

        payload = {"query": normalized}
        await emit_tool_use_event(
            manager=manager,
            provider="gemini",
            tool_name="google_search",
            tool_input=payload,
        )
        payload_dict = {
            "name": "google_search",
            "toolName": "google_search",
            "input": payload,
            "toolInput": payload,
            "id": None,
            "callId": None,
            "provider": "gemini",
            "requires_action": False,
        }
        logger.debug(
            "Gemini google_search payload created: query=%s requires_action=%s",
            normalized,
            payload_dict["requires_action"],
        )
        payloads.append(payload_dict)

    return payloads


__all__ = ["emit_grounding_events"]
