"""Utilities for preparing and sending realtime chat history."""

from __future__ import annotations

import logging
from typing import Any, List

from core.providers.realtime.base import BaseRealtimeProvider
from features.chat.utils.realtime_history_formatter import (
    format_chat_history_for_realtime,
)

logger = logging.getLogger(__name__)


def extract_text_from_content(content: Any) -> str:
    """Extract plain text from conversation content structures."""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: List[str] = []
        for part in content:
            if isinstance(part, dict):
                text = str(part.get("text", "")).strip()
                if text:
                    text_parts.append(text)
        return " ".join(text_parts)

    if isinstance(content, dict):
        return str(content.get("text", "")).strip()

    logger.warning(
        "Unexpected content type while extracting text: %s", type(content).__name__
    )
    return ""


async def send_chat_history(provider: BaseRealtimeProvider, chat_history: list) -> None:
    """Send chat history as conversation items to the provider."""

    if not chat_history:
        logger.debug("No chat history to send")
        return

    logger.info("Processing %d history messages", len(chat_history))

    conversation_events = format_chat_history_for_realtime(chat_history)
    if not conversation_events:
        logger.warning("Chat history formatting produced no events")
        return

    sent_count = 0
    for event in conversation_events:
        item = event.get("item", {})
        role = item.get("role", "user")
        content = item.get("content", [])

        text = extract_text_from_content(content)
        if not text:
            logger.warning("Skipping history message with empty text (role=%s)", role)
            continue

        try:
            await provider.create_conversation_item(text=text, role=role)
            sent_count += 1
            logger.debug(
                "Sent history message #%d (role=%s, chars=%d)",
                sent_count,
                role,
                len(text),
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to send history message (role=%s): %s", role, exc)

    logger.info("Successfully sent %d/%d history messages", sent_count, len(conversation_events))


__all__ = ["extract_text_from_content", "send_chat_history"]
