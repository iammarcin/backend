"""Format chat history for OpenAI Realtime API.

This module converts the frontend chat history format into OpenAI Realtime API
conversation items. Each message becomes a conversation.item.create event with
properly formatted content based on the message role.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def format_chat_history_for_realtime(
    chat_history: List[Dict[str, Any]] | None,
) -> List[Dict[str, Any]]:
    """Convert chat history to OpenAI Realtime conversation items.

    Args:
        chat_history: List of messages from frontend format:
            [
                {"role": "user", "content": [{"type": "text", "text": "..."}]},
                {"role": "assistant", "content": "..."}
            ]

    Returns:
        List of conversation.item.create event payloads ready to send to OpenAI

    Example:
        >>> history = [
        ...     {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
        ...     {"role": "assistant", "content": "Hello!"}
        ... ]
        >>> events = format_chat_history_for_realtime(history)
        >>> len(events)
        2
        >>> events[0]["type"]
        'conversation.item.create'
    """
    if not chat_history:
        return []

    formatted_events: List[Dict[str, Any]] = []

    for raw_message in chat_history:
        if not isinstance(raw_message, dict):
            logger.warning("Skipping non-dict chat history item: %r", raw_message)
            continue

        role = str(raw_message.get("role") or "user").lower()
        if role not in {"user", "assistant"}:
            logger.warning("Unexpected role '%s' in chat history; defaulting to user", role)
            role = "user"

        content = raw_message.get("content", "")
        content_parts = _format_content(content, role)

        if not content_parts:
            logger.warning(
                "Skipping history message with empty content (role=%s)",
                role,
            )
            continue

        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": role,
                "content": content_parts,
            },
        }

        formatted_events.append(event)

    if formatted_events:
        logger.info(
            "Formatted %d chat history messages into conversation items",
            len(formatted_events),
        )

    return formatted_events


def _format_content(content: Any, role: str) -> List[Dict[str, str]]:
    """Format message content into OpenAI Realtime content parts.

    Args:
        content: Message content (string or list of content parts)
        role: Message role ('user' or 'assistant')

    Returns:
        List of content parts with correct type for the role:
        - User messages: [{"type": "input_text", "text": "..."}]
        - Assistant messages: [{"type": "text", "text": "..."}]
    """
    content_parts: List[Dict[str, str]] = []
    content_type = "input_text" if role == "user" else "text"

    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue

            text = str(part.get("text", "")).strip()
            if text:
                content_parts.append({"type": content_type, "text": text})
    elif isinstance(content, str):
        text = content.strip()
        if text:
            content_parts.append({"type": content_type, "text": text})
    elif isinstance(content, dict):
        text = str(content.get("text", "")).strip()
        if text:
            content_parts.append({"type": content_type, "text": text})
    else:
        logger.warning(
            "Unexpected content type: %s (role=%s)",
            type(content).__name__,
            role,
        )

    return content_parts


__all__ = ["format_chat_history_for_realtime"]
