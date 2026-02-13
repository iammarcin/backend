"""Helper functions shared by the Deepgram STT service."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import suppress
from typing import Any, AsyncIterator, Optional

from core.streaming.manager import StreamingManager
from features.audio.utils import resample_audio

logger = logging.getLogger(__name__)


class KeepAliveState:
    def __init__(self) -> None:
        self.last_audio_ts = time.monotonic()


async def send_keepalive_messages(
    dg_client: "websockets.WebSocketClientProtocol",
    keepalive_state: KeepAliveState,
    *,
    interval_seconds: float = 5.0,
    max_silence_seconds: float = 30.0,
) -> None:
    """Send KeepAlive messages to prevent Deepgram inactivity timeouts."""

    import websockets  # Local import to avoid optional dependency at module import time

    try:
        while True:
            await asyncio.sleep(interval_seconds)
            silence_seconds = time.monotonic() - keepalive_state.last_audio_ts
            if silence_seconds >= max_silence_seconds:
                logger.debug(
                    "KeepAlive stopped after %.1fs of silence",
                    silence_seconds,
                )
                break
            try:
                await dg_client.send(json.dumps({"type": "KeepAlive"}))
                logger.debug(
                    "Sent KeepAlive to Deepgram (silence=%.1fs)",
                    silence_seconds,
                )
            except websockets.exceptions.ConnectionClosed:
                logger.debug("KeepAlive stopped - connection already closed")
                break
            except Exception as exc:  # pragma: no cover - network branch
                logger.warning("Failed to send KeepAlive: %s", exc)
                break
    except asyncio.CancelledError:
        logger.debug("KeepAlive task cancelled")
        raise


async def send_audio_chunks(
    audio_source: AsyncIterator[bytes | None],
    dg_client: "websockets.WebSocketClientProtocol",
    *,
    recording_sample_rate: int,
    target_sample_rate: int,
    keepalive_state: KeepAliveState | None = None,
) -> int:
    """Forward audio chunks from ``audio_source`` to Deepgram."""

    import websockets  # Local import to avoid optional dependency at module import time

    chunk_count = 0
    raw_chunk_count = 0
    pending: bytearray | None = bytearray() if recording_sample_rate != target_sample_rate else None

    try:
        async for audio_chunk in audio_source:
            if audio_chunk is None:
                break

            raw_chunk_count += 1

            chunk = audio_chunk
            if pending is not None:
                pending.extend(audio_chunk)

                if len(pending) < 2:
                    logger.debug("Buffering %s byte audio fragment until enough samples arrive", len(pending))
                    continue

                even_length = len(pending) - (len(pending) % 2)
                if even_length == 0:
                    continue

                chunk = bytes(pending[:even_length])
                del pending[:even_length]

                chunk = resample_audio(chunk, recording_sample_rate, target_sample_rate)

            if not chunk:
                logger.debug("Skipping empty audio payload after resampling step")
                continue

            try:
                await dg_client.send(chunk)
                chunk_count += 1
                if keepalive_state is not None:
                    keepalive_state.last_audio_ts = time.monotonic()
            except websockets.exceptions.ConnectionClosed as exc:  # pragma: no cover - network branch
                logger.warning(
                    "Deepgram connection closed while sending chunk %s/%s (code=%s, reason='%s')",
                    chunk_count,
                    raw_chunk_count,
                    getattr(exc, "code", "unknown"),
                    getattr(exc, "reason", ""),
                )
                raise
            except Exception as exc:  # pragma: no cover - network branch
                logger.error("Failed to send audio chunk to Deepgram: %s", exc)
                raise

        if pending is not None and pending:
            if len(pending) % 2 == 1:
                logger.debug("Padding trailing audio buffer with 1 zero byte to complete sample")
                pending.append(0)

            final_chunk = resample_audio(bytes(pending), recording_sample_rate, target_sample_rate)
            if final_chunk:
                try:
                    await dg_client.send(final_chunk)
                    chunk_count += 1
                    if keepalive_state is not None:
                        keepalive_state.last_audio_ts = time.monotonic()
                except websockets.exceptions.ConnectionClosed as exc:  # pragma: no cover - network branch
                    logger.warning(
                        "Deepgram connection closed while sending final chunk %s/%s (code=%s, reason='%s')",
                        chunk_count,
                        raw_chunk_count,
                        getattr(exc, "code", "unknown"),
                        getattr(exc, "reason", ""),
                    )
                    raise
                except Exception as exc:  # pragma: no cover - network branch
                    logger.error("Failed to send final audio chunk to Deepgram: %s", exc)
                    raise

        if raw_chunk_count and recording_sample_rate != target_sample_rate:
            logger.info(
                "Resampled %s raw audio chunks into %s Deepgram chunks (target_rate=%s)",
                raw_chunk_count,
                chunk_count,
                target_sample_rate,
            )

        with suppress(Exception):
            await dg_client.send(json.dumps({"type": "CloseStream"}))

        logger.info(
            "Finished sending %s audio chunks to Deepgram (raw_chunks=%s)",
            chunk_count,
            raw_chunk_count,
        )
        return chunk_count
    except Exception:
        logger.error(
            "Audio send failed after %s chunks sent (raw_chunks=%s)",
            chunk_count,
            raw_chunk_count,
        )
        raise


async def receive_transcription(
    dg_client: "websockets.WebSocketClientProtocol",
    manager: StreamingManager,
    mode: str,
) -> str:
    """Receive transcription data from Deepgram and push to queues."""

    import websockets  # Local import to avoid optional dependency at module import time

    full_transcription: list[str] = []
    message_count = 0

    try:
        async for message in dg_client:
            message_count += 1
            transcript = extract_transcript(message)
            if not transcript:
                continue

            full_transcription.append(transcript)
            if mode != "realtime":
                await manager.send_to_queues({"type": "transcription", "content": transcript})
            manager.collect_chunk(transcript, "transcription")
    except asyncio.CancelledError:
        logger.info(
            "Deepgram receive task cancelled (segments=%s)",
            len(full_transcription),
        )
        raise
    except websockets.exceptions.ConnectionClosedError as exc:  # pragma: no cover - network branch
        logger.warning(
            "Deepgram connection closed during receive (code=%s, reason='%s', segments=%s)",
            getattr(exc, "code", "unknown"),
            getattr(exc, "reason", ""),
            len(full_transcription),
        )
        if getattr(exc, "code", None) == 1011:
            logger.error(
                "Deepgram timeout: No audio data received within timeout window (segments=%s, messages=%s)",
                len(full_transcription),
                message_count,
            )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Error receiving data from Deepgram (segments=%s, messages=%s): %s",
            len(full_transcription),
            message_count,
            exc,
            exc_info=True,
        )

    combined = " ".join(full_transcription).strip()
    logger.info(
        "Deepgram transcription completed (segments=%s, chars=%s, messages_received=%s)",
        len(full_transcription),
        len(combined),
        message_count,
    )
    if combined:
        logger.debug("Transcription text: %s", combined)
    elif message_count > 0:
        logger.warning(
            "Deepgram sent %s messages but produced no transcript (likely timeout or empty audio)",
            message_count,
        )
    return combined


def extract_transcript(message: str) -> Optional[str]:
    """Extract transcript text from a Deepgram websocket message."""

    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        logger.debug("Received non-JSON message from Deepgram: %s", message)
        return None

    if payload.get("type") != "Results":
        return None

    alternatives = payload.get("channel", {}).get("alternatives", [])
    if not alternatives:
        return None

    transcript = alternatives[0].get("transcript")
    if transcript:
        logger.debug("Deepgram transcript chunk: %s", transcript)
    return transcript or None


def parse_control_message(message: str | dict[str, Any]) -> Optional[str]:
    """Interpret textual control messages from the frontend."""

    if isinstance(message, dict):
        payload = message
    else:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            payload = {"type": message}

    msg_type = str(payload.get("type", "")).lower()
    if msg_type in {"stop", "complete", "recordingfinished", "audio_end", "audio_complete"}:
        return "stop"
    if msg_type == "ping":
        return "ping"
    return None


__all__ = [
    "extract_transcript",
    "KeepAliveState",
    "parse_control_message",
    "receive_transcription",
    "send_audio_chunks",
    "send_keepalive_messages",
]
