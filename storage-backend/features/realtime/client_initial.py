from __future__ import annotations

import json
import logging
from typing import Mapping, TYPE_CHECKING

from core.exceptions import ProviderError
from core.observability import render_payload_preview

from .chat_history import send_chat_history


if TYPE_CHECKING:
    from .client_forwarder import RealtimeClientForwarder


logger = logging.getLogger(__name__)


async def dispatch_initial_payload(forwarder: "RealtimeClientForwarder") -> None:
    initial_payload = forwarder.initial_payload
    if initial_payload is None:
        return
    try:
        json.dumps(initial_payload)
    except TypeError:
        logger.warning(
            "Initial realtime payload for session %s is not JSON serialisable",
            forwarder.session_id,
        )
        return
    logger.debug(
        "Processing realtime initial payload (session=%s): %s",
        forwarder.session_id,
        render_payload_preview(initial_payload),
    )
    await forwarder.send_ack()

    await _send_initial_chat_history(forwarder, initial_payload)
    await _handle_initial_prompt(forwarder, initial_payload)


async def _send_initial_chat_history(
    forwarder: "RealtimeClientForwarder", initial_payload: Mapping[str, object]
) -> None:
    user_input = initial_payload.get("user_input")
    if not isinstance(user_input, Mapping):
        return
    chat_history = user_input.get("chat_history")
    if not (isinstance(chat_history, list) and chat_history):
        return

    logger.info(
        "Found %d chat history messages in initial payload (session=%s)",
        len(chat_history),
        forwarder.session_id,
    )
    try:
        sent_count = await send_chat_history(
            provider=forwarder.provider,
            chat_history=chat_history,
            session_id=forwarder.session_id,
        )
        if sent_count > 0:
            logger.info(
                "Chat history context established (%d messages, session=%s)",
                sent_count,
                forwarder.session_id,
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "Error processing chat history (session=%s): %s",
            forwarder.session_id,
            exc,
            exc_info=True,
        )


async def _handle_initial_prompt(
    forwarder: "RealtimeClientForwarder", initial_payload: Mapping[str, object]
) -> None:
    request_type = str(initial_payload.get("request_type") or "")
    user_input = initial_payload.get("user_input")

    if request_type != "text_realtime" or not isinstance(user_input, Mapping):
        return

    prompt_items = user_input.get("prompt")
    text_value = ""
    if isinstance(prompt_items, list) and prompt_items:
        first_prompt = prompt_items[0]
        if isinstance(first_prompt, Mapping):
            text_value = str(first_prompt.get("text") or "").strip()

    if not text_value:
        logger.debug(
            "No initial text prompt supplied for realtime session %s",
            forwarder.session_id,
        )
        return

    create_item = getattr(forwarder.provider, "create_conversation_item", None)
    if not callable(create_item):
        logger.warning(
            "Realtime provider %s does not support conversation items; skipping initial text dispatch (session=%s)",
            forwarder.provider.name,
            forwarder.session_id,
        )
        return

    try:
        await create_item(text=text_value)
    except ProviderError as exc:
        logger.error(
            "Failed to create realtime conversation item (session=%s): %s",
            forwarder.session_id,
            exc,
        )
        return

    request_response = getattr(forwarder.provider, "request_response", None)
    if callable(request_response):
        try:
            await request_response()
        except ProviderError as exc:
            logger.error(
                "Failed to request realtime response (session=%s): %s",
                forwarder.session_id,
                exc,
            )
    else:
        logger.warning(
            "Realtime provider missing request_response capability; cannot trigger response for session %s",
            forwarder.session_id,
        )


__all__ = ["dispatch_initial_payload"]
