"""PollerStreamSession - manages state for a single poller stream connection.

Handles the producer/consumer pattern for processing NDJSON lines from
the Claude CLI poller.
"""

import asyncio
import logging
import time
from typing import Optional, Protocol

from fastapi import WebSocket, WebSocketDisconnect

from config.proactive_agent import (
    POLLER_STREAM_QUEUE_SIZE,
    POLLER_STREAM_QUEUE_TIMEOUT,
)

from .error_mapper import get_user_friendly_error
from .ndjson_parser import EventType, NDJSONLineParser
from .schemas import CompleteMessage, ErrorMessage, InitMessage

logger = logging.getLogger(__name__)


class EventEmitterProtocol(Protocol):
    """Protocol for event emitters to allow dependency injection."""

    async def emit(self, event) -> None: ...
    async def finalize(self, full_content: str) -> None: ...
    async def emit_error(self, code: str, message: str) -> None: ...


class PollerStreamSession:
    """Manages state for a single poller stream connection."""

    def __init__(
        self,
        websocket: WebSocket,
        init_data: InitMessage,
        emitter: EventEmitterProtocol,
    ) -> None:
        self.websocket = websocket
        self.user_id = init_data.user_id
        self.session_id = init_data.session_id
        self.ai_character_name = init_data.ai_character_name
        self.tts_settings = init_data.tts_settings
        self.source = init_data.source
        self.claude_session_id = init_data.claude_session_id

        self.parser = NDJSONLineParser()
        self.emitter = emitter
        self.queue: asyncio.Queue[str | None] = asyncio.Queue(
            maxsize=POLLER_STREAM_QUEUE_SIZE
        )
        self._closed = False
        self._completed = False
        self._error_emitted = False
        self._disconnect_detected = False
        self._last_line_time: Optional[float] = None
        self._last_line_preview: Optional[str] = None
        self._last_control_type: Optional[str] = None

        # M6.7: Observability metrics
        self._start_time: Optional[float] = None
        self._chunk_count = 0
        self._first_content_time: Optional[float] = None

    async def producer(self) -> None:
        """Read from WebSocket and put lines in queue."""
        try:
            while not self._closed:
                data = await self.websocket.receive_text()
                try:
                    await asyncio.wait_for(
                        self.queue.put(data), timeout=POLLER_STREAM_QUEUE_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        f"Queue full timeout after {POLLER_STREAM_QUEUE_TIMEOUT}s: "
                        f"session={self.session_id}, queue_size={self.queue.qsize()}"
                    )
                    user_message = get_user_friendly_error("backpressure")
                    await self.emitter.emit_error("backpressure", user_message)
                    self._error_emitted = True
                    await self.close_with_error("backpressure", user_message)
                    break
        except WebSocketDisconnect:
            last_line_age = (
                time.time() - self._last_line_time if self._last_line_time else None
            )
            logger.info(
                "Poller disconnected: session=%s completed=%s error_emitted=%s "
                "last_control=%s last_line_age=%.3fs queue_size=%d",
                self.session_id,
                self._completed,
                self._error_emitted,
                self._last_control_type,
                last_line_age if last_line_age is not None else -1,
                self.queue.qsize(),
            )
            if self._last_line_preview:
                logger.debug(
                    "Poller last line preview: session=%s preview=%s",
                    self.session_id,
                    self._last_line_preview,
                )
            if not self._completed and not self._error_emitted:
                self._disconnect_detected = True
                self._closed = True
        finally:
            try:
                self.queue.put_nowait(None)  # Signal consumer to stop
            except asyncio.QueueFull:
                _ = self.queue.get_nowait()
                self.queue.put_nowait(None)

    async def consumer(self) -> None:
        """Process lines from queue."""
        try:
            while True:
                line = await self.queue.get()
                if line is None:
                    break
                await self._process_line(line)
                if self._completed or self._error_emitted:
                    break
        except Exception:
            logger.exception(f"Consumer error: session={self.session_id}")
            raise

    async def _process_line(self, line: str) -> None:
        """Process a single line (ndjson, error, complete)."""
        stripped = line.strip()
        if not stripped:
            return
        self._last_line_time = time.time()
        self._last_line_preview = stripped[:200]

        # M6.7: Track start time on first line
        if self._start_time is None:
            self._start_time = time.time()

        # Check for control messages (error/complete)
        if stripped.startswith('{"type":'):
            if '"type": "error"' in stripped or '"type":"error"' in stripped:
                try:
                    self._last_control_type = "error"
                    msg = ErrorMessage.model_validate_json(stripped)
                    self._log_stream_error(msg.code, msg.message)
                    user_message = get_user_friendly_error(msg.code, msg.message)
                    await self.emitter.emit_error(msg.code, user_message)
                    self._error_emitted = True
                    self._closed = True
                    return
                except Exception:
                    pass  # Not a valid error message, treat as NDJSON
            elif '"type": "complete"' in stripped or '"type":"complete"' in stripped:
                try:
                    self._last_control_type = "complete"
                    logger.debug(
                        "Poller complete received: session=%s preview=%s",
                        self.session_id,
                        self._last_line_preview,
                    )
                    msg = CompleteMessage.model_validate_json(stripped)
                    await self._finalize(msg.exit_code)
                    return
                except Exception:
                    pass  # Not a valid complete message, treat as NDJSON

        # Parse NDJSON line and emit events
        events = self.parser.process_line(stripped)
        stream_complete_seen = False
        for event in events:
            # M6.7: Track first content and chunk count
            if self._first_content_time is None:
                self._first_content_time = time.time()
            self._chunk_count += 1
            await self.emitter.emit(event)
            if event.type == EventType.STREAM_COMPLETE:
                stream_complete_seen = True

        if stream_complete_seen and not self._completed:
            self._last_control_type = "stream_complete"
            await self._finalize(0)
            return

    async def _finalize(self, exit_code: int) -> None:
        """Finalize the stream."""
        self._completed = True
        self._closed = True
        # Flush any remaining content
        final_events = self.parser.finalize()
        for event in final_events:
            self._chunk_count += 1
            await self.emitter.emit(event)

        # Get accumulated content (with thinking tags for ai_reasoning extraction)
        full_text = self.parser.get_accumulated_text()

        # Emit stream_end
        await self.emitter.finalize(full_text)

        # M6.7: Log structured stream completion metrics
        self._log_stream_completed(exit_code)

    def _log_stream_completed(self, exit_code: int) -> None:
        """Log structured stream completion data (M6.7 Observability)."""
        end_time = time.time()
        duration = end_time - self._start_time if self._start_time else 0
        time_to_first_content = (
            self._first_content_time - self._start_time
            if self._start_time and self._first_content_time
            else None
        )

        logger.info(
            "stream_completed",
            extra={
                "user_id": self.user_id,
                "session_id": self.session_id,
                "ai_character_name": self.ai_character_name,
                "source": self.source,
                "exit_code": exit_code,
                "duration_seconds": round(duration, 3),
                "chunk_count": self._chunk_count,
                "time_to_first_content_seconds": (
                    round(time_to_first_content, 3) if time_to_first_content else None
                ),
                "status": "completed",
            },
        )

    def _log_stream_error(self, code: str, message: str) -> None:
        """Log structured stream error data (M6.7 Observability)."""
        end_time = time.time()
        duration = end_time - self._start_time if self._start_time else 0

        logger.error(
            "stream_error",
            extra={
                "user_id": self.user_id,
                "session_id": self.session_id,
                "ai_character_name": self.ai_character_name,
                "source": self.source,
                "error_code": code,
                "error_message": message[:200],  # Truncate long messages
                "duration_seconds": round(duration, 3),
                "chunk_count": self._chunk_count,
                "status": "error",
            },
        )

    async def close_with_error(self, code: str, message: str) -> None:
        """Close connection with error."""
        self._closed = True
        try:
            await self.websocket.close(code=1008, reason=message)
        except Exception:
            pass

    async def run(self) -> None:
        """Run producer and consumer concurrently."""
        try:
            await asyncio.gather(self.producer(), self.consumer())
        except WebSocketDisconnect:
            logger.warning(f"WS disconnect mid-stream: session={self.session_id}")
            user_message = get_user_friendly_error("connection_lost")
            await self.emitter.emit_error("connection_lost", user_message)
        except Exception as e:
            logger.exception(f"Stream error: session={self.session_id}")
            await self.emitter.emit_error("unknown", str(e)[:100])
        finally:
            if self._disconnect_detected and not self._completed and not self._error_emitted:
                logger.debug(
                    "Poller disconnect triggers error: session=%s last_control=%s",
                    self.session_id,
                    self._last_control_type,
                )
                user_message = get_user_friendly_error("connection_lost")
                await self.emitter.emit_error("connection_lost", user_message)


__all__ = ["PollerStreamSession"]
