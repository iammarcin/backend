"""TTS Queue Manager - Handles text-to-speech queue coordination.

Extracted from StreamingManager to maintain file size discipline (< 250 lines).
Manages TTS text chunk duplication and queue lifecycle.
"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TTSQueueManager:
    """Manages TTS text queue registration and chunk duplication."""

    def __init__(self) -> None:
        self._tts_text_queue: Optional[asyncio.Queue] = None
        self._tts_enabled = False
        self._tts_text_chunks_sent = 0

    def register_queue(self, queue: asyncio.Queue) -> None:
        """Register a queue to receive duplicated text chunks for TTS processing."""

        self._tts_text_queue = queue
        self._tts_enabled = True
        self._tts_text_chunks_sent = 0
        logger.debug("Registered TTS text queue with streaming manager")

    def deregister_queue(self) -> None:
        """Deregister the TTS text queue and emit sentinel if possible."""

        if self._tts_text_queue is None:
            self._tts_enabled = False
            self._tts_text_chunks_sent = 0
            return

        try:
            self._tts_text_queue.put_nowait(None)
            logger.debug(
                "Sent TTS queue sentinel (total chunks duplicated: %s)",
                self._tts_text_chunks_sent,
            )
        except asyncio.QueueFull:
            logger.warning("TTS queue full when sending sentinel during deregistration")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to send TTS queue sentinel: %s", exc)

        self._tts_text_queue = None
        self._tts_enabled = False
        self._tts_text_chunks_sent = 0

    async def maybe_send_text_chunk(self, data: Any) -> None:
        """Duplicate text payloads to the registered TTS queue when active."""

        if not self._tts_enabled or self._tts_text_queue is None:
            return

        if not isinstance(data, dict):
            return

        if data.get("type") != "text_chunk":
            return

        content = data.get("content")
        if not isinstance(content, str) or not content.strip():
            return

        try:
            await self._tts_text_queue.put(content)
            self._tts_text_chunks_sent += 1
        except asyncio.QueueFull:
            logger.warning("TTS text queue full, dropping text chunk (length=%s)", len(content))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to duplicate text chunk to TTS queue: %s", exc)

    def is_enabled(self) -> bool:
        """Return True when a TTS queue is currently registered."""

        return self._tts_enabled and self._tts_text_queue is not None

    def get_chunks_sent(self) -> int:
        """Return the number of text chunks duplicated to the TTS queue."""

        return self._tts_text_chunks_sent

    def reset(self) -> None:
        """Reset TTS queue state."""

        self._tts_text_queue = None
        self._tts_enabled = False
        self._tts_text_chunks_sent = 0
