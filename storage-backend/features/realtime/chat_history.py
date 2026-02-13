"""Helpers for sending chat history to realtime providers."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from core.exceptions import ProviderError
from core.providers.realtime.base import BaseRealtimeProvider

logger = logging.getLogger(__name__)


async def send_chat_history(
    *,
    provider: BaseRealtimeProvider,
    chat_history: Sequence[Mapping[str, Any]],
    session_id: str,
) -> int:
    """Send chat history messages to establish realtime context.

    Each entry in ``chat_history`` is converted into a
    ``conversation.item.create`` event and sent to the provider in the order
    provided.

    Args:
        provider: Realtime provider instance used to dispatch conversation
            items.
        chat_history: Sequence of chat messages from the client. Expected
            structure::

                [
                    {"role": "user", "content": [{"type": "text", "text": "..."}]},
                    {"role": "assistant", "content": "..."}
                ]

        session_id: Session identifier for logging.

    Returns:
        The number of messages successfully dispatched to the provider.
    """

    if not chat_history:
        logger.debug("No chat history to send (session=%s)", session_id)
        return 0

    logger.info(
        "Processing %d chat history messages (session=%s)",
        len(chat_history),
        session_id,
    )

    create_item = getattr(provider, "create_conversation_item", None)
    if not callable(create_item):
        logger.error(
            "Provider %s does not support conversation history (session=%s)",
            getattr(provider, "name", provider.__class__.__name__),
            session_id,
        )
        return 0

    sent_count = 0
    for idx, message in enumerate(chat_history):
        if not isinstance(message, Mapping):
            logger.warning(
                "Skipping non-mapping chat history entry at index %d (session=%s)",
                idx,
                session_id,
            )
            continue

        role = str(message.get("role", "user")).strip() or "user"
        content = message.get("content", "")
        text = _extract_text_from_content(content)

        if not text:
            logger.warning(
                "Skipping chat history entry %d with empty text (role=%s, session=%s)",
                idx,
                role,
                session_id,
            )
            continue

        try:
            await create_item(text=text, role=role)
        except ProviderError as exc:
            logger.error(
                "Failed to send history entry %d (role=%s, session=%s): %s",
                idx,
                role,
                session_id,
                exc,
            )
            continue
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "Unexpected error sending chat history entry %d (session=%s): %s",
                idx,
                session_id,
                exc,
                exc_info=True,
            )
            continue

        sent_count += 1
        logger.debug(
            "Sent chat history entry %d/%d (role=%s, chars=%d, session=%s)",
            sent_count,
            len(chat_history),
            role,
            len(text),
            session_id,
        )

    logger.info(
        "Successfully sent %d/%d chat history messages (session=%s)",
        sent_count,
        len(chat_history),
        session_id,
    )
    return sent_count


def _extract_text_from_content(content: Any) -> str:
    """Extract plain text from chat history content payloads."""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, Mapping):
                text_value = part.get("text")
                if text_value:
                    text_parts.append(str(text_value))
        return " ".join(text_parts).strip()

    if isinstance(content, Mapping):
        text = content.get("text", "")
        return str(text).strip()

    logger.warning("Unexpected chat history content type: %s", type(content).__name__)
    return ""


__all__ = ["send_chat_history"]
