"""Utilities for orchestrating parallel TTS streaming during chat flows."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from core.streaming.manager import StreamingManager
from features.tts.schemas.requests import TTSUserSettings
from features.tts.service import TTSService
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)


class TTSOrchestrator:
    """Manage lifecycle of queue-based TTS streaming alongside text generation."""

    def __init__(
        self,
        *,
        manager: StreamingManager,
        tts_service: TTSService,
        settings: Dict[str, Any],
        customer_id: int,
        timings: Dict[str, float],
    ) -> None:
        self.manager = manager
        self.tts_service = tts_service
        self.settings = settings
        self.customer_id = customer_id
        self.timings = timings

        self._tts_queue: Optional[asyncio.Queue[str | None]] = None
        self._tts_task: Optional[asyncio.Task[None]] = None
        self._tts_metadata: Optional[Dict[str, Any]] = None
        self._tts_enabled = False

    def should_enable_tts(self) -> bool:
        """Return True when settings indicate auto-executed streaming TTS."""

        if not isinstance(self.settings, dict):
            return False

        tts_settings = self.settings.get("tts")
        if not isinstance(tts_settings, dict):
            return False

        auto_execute = bool(tts_settings.get("tts_auto_execute"))
        streaming_enabled = tts_settings.get("streaming")

        return auto_execute and streaming_enabled is not False

    async def start_tts_streaming(self) -> bool:
        """Initialise queue duplication and background TTS streaming."""

        if not self.should_enable_tts():
            logger.debug("TTS orchestrator disabled by settings (customer=%s)", self.customer_id)
            return False

        tts_settings = self.settings.get("tts", {}) if isinstance(self.settings, dict) else {}
        payload = {
            "general": self.settings.get("general", {}) if isinstance(self.settings, dict) else {},
            "tts": tts_settings,
        }

        try:
            user_settings = TTSUserSettings.model_validate(payload)
        except PydanticValidationError as exc:
            logger.warning(
                "Skipping parallel TTS streaming due to invalid settings (customer=%s): %s",
                self.customer_id,
                exc,
            )
            return False

        self._tts_queue = asyncio.Queue()
        self.manager.register_tts_queue(self._tts_queue)
        self._tts_enabled = True
        self._tts_metadata = None

        logger.info("Registered TTS queue for customer %s", self.customer_id)

        self._tts_task = asyncio.create_task(
            self._run_tts_streaming(user_settings),
            name=f"tts-streaming-{self.customer_id}",
        )

        logger.info("Started parallel TTS streaming task (customer=%s)", self.customer_id)
        return True

    async def _run_tts_streaming(self, user_settings: TTSUserSettings) -> None:
        """Consume the duplicated text queue and stream audio via TTS service."""

        queue = self._tts_queue
        if queue is None:
            logger.debug("TTS queue missing when attempting to stream (customer=%s)", self.customer_id)
            return

        try:
            metadata = await self.tts_service.stream_from_text_queue(
                text_queue=queue,
                customer_id=self.customer_id,
                user_settings=user_settings,
                manager=self.manager,
                timings=self.timings,
            )
        except asyncio.CancelledError:
            logger.debug("Parallel TTS task cancelled (customer=%s)", self.customer_id)
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Parallel TTS streaming failed (customer=%s): %s",
                self.customer_id,
                exc,
                exc_info=True,
            )
            return

        self._tts_metadata = {
            "provider": metadata.provider,
            "model": metadata.model,
            "voice": metadata.voice,
            "format": metadata.format,
            "text_chunk_count": metadata.text_chunk_count,
            "audio_chunk_count": metadata.audio_chunk_count,
            "audio_file_url": metadata.audio_file_url,
            "storage_metadata": metadata.storage_metadata,
        }

        logger.info(
            "Parallel TTS streaming completed (customer=%s, audio_chunks=%s, text_chunks=%s)",
            self.customer_id,
            metadata.audio_chunk_count,
            metadata.text_chunk_count,
        )

    async def wait_for_completion(self) -> Optional[Dict[str, Any]]:
        """Await the background task and return collected metadata when available."""

        if not self._tts_enabled or self._tts_task is None:
            return None

        if self.manager.is_tts_enabled():
            self.manager.deregister_tts_queue()

        # Use a generous timeout to accommodate long-form audio (5+ min content).
        # The underlying WebSocket streaming can take up to 300s for ElevenLabs
        # to deliver all audio chunks after text generation completes.
        try:
            await asyncio.wait_for(self._tts_task, timeout=360.0)
        except asyncio.TimeoutError:
            logger.warning("TTS task timed out after 360s (customer=%s)", self.customer_id)
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error while awaiting TTS completion (customer=%s): %s", self.customer_id, exc)

        return self._tts_metadata

    async def cleanup(self) -> None:
        """Ensure background task and queue are tidied up."""

        if self.manager.is_tts_enabled():
            self.manager.deregister_tts_queue()

        if self._tts_task is not None and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass

        self._tts_task = None
        self._tts_queue = None
        self._tts_enabled = False
        self._tts_metadata = None

    def is_enabled(self) -> bool:
        """Return True when parallel TTS streaming is active."""

        return self._tts_enabled


__all__ = ["TTSOrchestrator"]
