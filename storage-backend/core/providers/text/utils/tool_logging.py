"""Utility helpers for logging tool usage details from provider responses."""

from __future__ import annotations

import logging
from typing import Any, Iterable


def log_tool_usage(
    provider_name: str,
    content_blocks: Iterable[Any] | None,
    *,
    logger: logging.Logger | None = None,
) -> None:
    """Log tool usage extracted from Anthropic-style content blocks."""

    if not content_blocks:
        return

    active_logger = logger or logging.getLogger(__name__)

    for block in content_blocks:
        block_type = getattr(block, "type", None) or (
            block.get("type") if isinstance(block, dict) else None
        )
        if block_type != "tool_use":
            continue

        tool_name = getattr(block, "name", None) or (
            block.get("name") if isinstance(block, dict) else None
        )
        tool_input = getattr(block, "input", None) or (
            block.get("input") if isinstance(block, dict) else None
        )

        query: str | None = None
        if isinstance(tool_input, dict):
            raw_query = tool_input.get("query") or tool_input.get("search_query")
            if isinstance(raw_query, str) and raw_query.strip():
                query = raw_query.strip()
        elif isinstance(tool_input, str) and tool_input.strip():
            query = tool_input.strip()

        if query:
            active_logger.info(
                "%s tool use detected: %s query=\"%s\"",
                provider_name,
                tool_name or "unknown",
                query,
            )
        else:
            active_logger.info(
                "%s tool use detected: %s input=%r",
                provider_name,
                tool_name or "unknown",
                tool_input,
            )
