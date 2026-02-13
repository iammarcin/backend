from __future__ import annotations

import asyncio
import inspect
import logging
from typing import TYPE_CHECKING

from core.exceptions import ProviderError
from core.observability import render_payload_preview

from .errors import invalid_message_error


if TYPE_CHECKING:
    from .client_forwarder import RealtimeClientForwarder


logger = logging.getLogger(__name__)


async def handle_text_payload(
    forwarder: "RealtimeClientForwarder", raw_message: str
) -> bool:
    payload = forwarder.parse_payload(raw_message)
    if payload is None:
        return False

    message_type = str(payload.get("type") or "")
    logger.debug(
        "Realtime websocket payload received (session=%s): %s",
        forwarder.session_id,
        render_payload_preview(payload),
    )

    await forwarder.send_ack()

    lowered_type = message_type.lower()
    if lowered_type in {"realtime.close", "close", "disconnect"}:
        return await _handle_close_request(
            forwarder,
            force=True,
            reason="client_close",
        )

    if message_type == "RecordingFinished":
        logger.info(
            "Realtime recording finished (session=%s, queue_size=%d)",
            forwarder.session_id,
            forwarder.input_audio_queue.qsize(),
        )
        await forwarder.input_audio_queue.put(None)
        return await _handle_close_request(
            forwarder,
            force=False,
            reason="recording_finished",
        )

    if lowered_type == "cancel":
        return await _handle_cancel(forwarder)

    try:
        await forwarder.provider.send_user_event(payload)
    except ProviderError as exc:
        error = invalid_message_error(str(exc))
        logger.error(error.to_log_message())
        await forwarder.websocket.send_json(
            {**error.to_client_payload(), "session_id": forwarder.session_id}
        )
        if forwarder.metrics:
            forwarder.metrics.record_error(error.code.value)
    return False


async def _handle_close_request(
    forwarder: "RealtimeClientForwarder", force: bool, reason: str
) -> bool:
    logger.info(
        "Realtime websocket received close directive",
        extra={"session_id": forwarder.session_id},
    )
    request = forwarder.request_session_close
    if request is None:
        return force

    try:
        result = request(force, reason)
    except TypeError:
        result = request(force)  # type: ignore[misc]

    if result is None:
        return bool(force)

    if asyncio.isfuture(result) or inspect.isawaitable(result):
        awaited = await result  # type: ignore[func-returns-value]
        return bool(awaited)

    return bool(result)


async def _handle_cancel(forwarder: "RealtimeClientForwarder") -> bool:
    logger.info("Realtime cancel requested (session=%s)", forwarder.session_id)
    forwarder.turn_state.mark_cancelled()
    if not forwarder.cancel_event.is_set():
        forwarder.cancel_event.set()

    try:
        await forwarder.provider.cancel_turn()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Provider cancellation request failed: %s", exc)

    await forwarder.websocket.send_json(
        {
            "type": "realtime.cancelled",
            "session_id": forwarder.session_id,
            "turn_status": forwarder.turn_state.phase.value,
        }
    )
    return False


__all__ = ["handle_text_payload"]
