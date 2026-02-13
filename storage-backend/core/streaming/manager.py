"""Streaming Manager - Token-Based Completion Ownership for Multi-Queue Fan-Out
This module implements a streaming orchestration system that manages multiple output
queues (WebSocket, SSE, TTS) with token-based completion ownership to prevent race
conditions.
Core Problem Solved:
    When streaming to multiple consumers (WebSocket, TTS, SSE), we need exactly one
    entity to send the final completion signal. Without coordination, multiple components
    might send completion events, causing client-side errors or duplicate processing.
Token-Based Completion Pattern:
    1. Top-level dispatcher creates completion token via create_completion_token()
    2. Token is passed to all streaming components
    3. Only the holder of the token can call signal_completion(token=...)
    4. CompletionOwnershipError raised if token missing or invalid
Architecture:
    - Queue Fan-Out: Single data source → multiple output queues
    - Chunk Collection: Aggregates streamed chunks for final response
    - TTS Integration: Duplicates text chunks to separate TTS queue
    - Completion Signaling: Token-based single-owner completion semantics
Fan-Out Modes:
    - "all": Send to all registered queues + TTS queue
    - "frontend_only": Send only to last queue (WebSocket) + TTS queue
    - "tts_only": Send only to first queue (TTS queue)
Usage Example:
    # In service/workflow dispatcher
    manager = StreamingManager()
    completion_token = manager.create_completion_token()
    websocket_queue = asyncio.Queue()
    manager.add_queue(websocket_queue)
    # Optional TTS queue for simultaneous audio generation
    if tts_enabled:
        tts_queue = asyncio.Queue()
        manager.register_tts_queue(tts_queue)
    # Stream data
    async for chunk in provider.stream(prompt):
        await manager.send_to_queues({"type": "text", "content": chunk})
        manager.collect_chunk(chunk, "text")
    # Only holder of token can complete
    await manager.signal_completion(token=completion_token)
Design Benefits:
    - Race Condition Prevention: Only one completion signal sent
    - Type Safety: Explicit token passing
    - Testability: Token ownership can be verified
    - Clarity: Completion responsibility is explicit
    - Debugging: Token lifecycle logged
See Also:
    - features/chat/services/streaming/: Agentic workflow implementation
    - features/tts/: TTS queue integration
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from core.exceptions import CompletionOwnershipError, StreamingError
from core.streaming.tts_queue_manager import TTSQueueManager
from core.utils.json_serialization import sanitize_for_json

logger = logging.getLogger(__name__)


class StreamingManager:
    """Manage streaming queues and collected results."""

    def __init__(self) -> None:
        self.queues: List[asyncio.Queue] = []
        self.results: Dict[str, List[Any]] = {
            "text_chunks": [],
            "reasoning_chunks": [],
            "audio_chunks": [],
            "transcription_chunks": [],
            "translation_chunks": [],
            "tool_calls": [],
        }
        self._completed = False
        self._completion_token: Optional[str] = None
        self._token_created = False
        self._tts_manager = TTSQueueManager()
        self._ai_message_id: Any | None = None

    def create_completion_token(self) -> str:
        """Create and return a completion ownership token for this manager."""

        if self._token_created:
            raise StreamingError(
                "Completion token already created. Only one token allowed per manager.",
                stage="completion",
            )

        self._completion_token = str(uuid.uuid4())
        self._token_created = True
        return self._completion_token

    def add_queue(self, queue: asyncio.Queue) -> None:
        """Register a queue to receive streamed data."""

        self.queues.append(queue)
        logger.debug("Added queue. Total queues: %s", len(self.queues))

    def register_tts_queue(self, queue: asyncio.Queue) -> None:
        """Register a queue to receive duplicated text chunks for TTS processing."""

        self._tts_manager.register_queue(queue)

    def deregister_tts_queue(self) -> None:
        """Deregister the TTS text queue and emit sentinel if possible."""

        self._tts_manager.deregister_queue()

    async def send_to_queues(self, data: Any, queue_type: str = "all") -> None:
        """Fan out data to the configured queues."""

        if self._completed:
            logger.warning("Attempted to send to a completed stream")
            return

        try:
            if isinstance(data, dict) and data.get("type") == "tool_start":
                logger.info(
                    "Forwarding tool call payload via streaming manager (keys=%s)",
                    list(data.get("content", {}).keys())
                    if isinstance(data.get("content"), dict)
                    else type(data.get("content")),
                )

            serialized_data = sanitize_for_json(data)
            if isinstance(serialized_data, dict):
                self._attach_ai_message_id(serialized_data)

            if queue_type == "all":
                for queue in self.queues:
                    await queue.put(serialized_data)
                await self._tts_manager.maybe_send_text_chunk(serialized_data)
            elif queue_type == "frontend_only":
                if self.queues:
                    await self.queues[-1].put(serialized_data)
                await self._tts_manager.maybe_send_text_chunk(serialized_data)
            elif queue_type == "tts_only":
                if self.queues:
                    await self.queues[0].put(serialized_data)
            else:
                raise StreamingError(f"Unknown queue_type: {queue_type}", stage="send")

        except Exception as exc:  # pragma: no cover - safety log branch
            logger.error("Error sending to queues: %s", exc)
            raise StreamingError(f"Failed to send to queues: {exc}", stage="fan-out") from exc

    async def send_event(self, event: Dict[str, Any]) -> None:
        """Send an event to all registered queues."""
        await self.send_to_queues(event, queue_type="all")

    async def signal_completion(self, *, token: str) -> None:
        """Notify all queues that streaming has completed using an ownership token."""

        if self._completed:
            return

        if not self._token_created:
            raise CompletionOwnershipError(
                "No completion token was created for this manager. "
                "Top-level dispatcher must call create_completion_token() first."
            )

        if not token:
            raise CompletionOwnershipError(
                "Completion token required but not provided. Only code with the token "
                "can complete the stream. See DocumentationApp/FINAL-completion-token-implementation.md"
            )

        if token != self._completion_token:
            raise CompletionOwnershipError(
                "Invalid completion token. Only the owner of the token can complete the stream."
            )

        logger.debug("Signalling completion to all queues")
        if self._tts_manager.is_enabled():
            self.deregister_tts_queue()
        for queue in self.queues:
            try:
                await queue.put(None)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Error signalling completion: %s", exc)
        self._completed = True

    def is_tts_enabled(self) -> bool:
        """Return True when a TTS queue is currently registered."""

        return self._tts_manager.is_enabled()

    def get_tts_chunks_sent(self) -> int:
        """Return the number of text chunks duplicated to the TTS queue."""

        return self._tts_manager.get_chunks_sent()

    def collect_chunk(self, chunk: str, chunk_type: str = "text") -> None:
        """Store a streamed chunk for later aggregation."""

        key = f"{chunk_type}_chunks"
        if key in self.results:
            self.results[key].append(chunk)
        else:
            logger.warning("Unknown chunk_type: %s", chunk_type)

    def collect_tool_call(self, payload: Dict[str, Any]) -> None:
        """Persist tool call payloads for downstream consumers."""

        self.results.setdefault("tool_calls", []).append(payload)

    def set_ai_message_id(self, message_id: Any | None) -> None:
        """Record the AI message identifier for downstream events."""

        self._ai_message_id = message_id

    def get_results(self) -> Dict[str, Any]:
        """Return the aggregated streaming results."""

        return {
            "text": "".join(self.results["text_chunks"]),
            "reasoning": "".join(self.results["reasoning_chunks"]),
            "audio": "".join(self.results["audio_chunks"]),
            "transcription": "".join(self.results["transcription_chunks"]),
            "translation": "".join(self.results["translation_chunks"]),
            "tool_calls": list(self.results.get("tool_calls", [])),
        }

    def reset(self) -> None:
        """Reset queues and collected data for reuse."""

        self.queues.clear()
        self.results = {
            "text_chunks": [],
            "reasoning_chunks": [],
            "audio_chunks": [],
            "transcription_chunks": [],
            "translation_chunks": [],
            "tool_calls": [],
        }
        self._completed = False
        self._completion_token = None
        self._token_created = False
        self._tts_manager.reset()
        self._ai_message_id = None

    def _attach_ai_message_id(self, payload: Dict[str, Any]) -> None:
        if self._ai_message_id is None:
            return

        if "aiMessageId" in payload or "ai_message_id" in payload:
            return

        payload["aiMessageId"] = self._ai_message_id
