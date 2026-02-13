from __future__ import annotations

import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .client_forwarder import RealtimeClientForwarder


logger = logging.getLogger(__name__)


async def handle_audio_payload(
    forwarder: "RealtimeClientForwarder", audio_data: object
) -> None:
    if not isinstance(audio_data, (bytes, bytearray, memoryview)):
        logger.warning(
            "Ignoring non-bytes audio payload (session=%s)",
            forwarder.session_id,
        )
        return

    if forwarder.cancel_event.is_set():
        return

    if isinstance(audio_data, memoryview):
        audio_bytes = audio_data.tobytes()
    else:
        audio_bytes = bytes(audio_data)

    if forwarder.metrics:
        forwarder.metrics.record_audio_received(len(audio_bytes))
    await forwarder.input_audio_queue.put(audio_bytes)


__all__ = ["handle_audio_payload"]
