"""Streaming helpers for forwarding workflow events to the frontend.

The chat WebSocket endpoint fans out streaming responses from the backend
pipeline to the browser. Keeping the asyncio plumbing in a dedicated module
lets the endpoint stay focused on high-level orchestration.
"""

import asyncio
import logging
from contextlib import suppress
from typing import Any, Dict, Optional

from fastapi import WebSocket

from core.utils.json_serialization import sanitize_for_json
from .websocket_session import WorkflowSession
from .websocket_stream_buffer import get_stream_buffer_manager

logger = logging.getLogger(__name__)

_MIN_IDLE_CHECK_SECONDS = 15
_MAX_IDLE_CHECK_SECONDS = 60


async def send_to_frontend(
    queue: asyncio.Queue,
    websocket: WebSocket,
    *,
    session_id: Optional[str] = None,
) -> None:
    """Stream queued data to the frontend WebSocket."""

    buffer_manager = get_stream_buffer_manager()
    chunk_counter = 0  # Per-stream sequence number for resumption

    while True:
        chunk = await queue.get()

        if chunk is None:
            # NOTE: Completion events (text_completed, tts_completed/tts_not_requested)
            # are sent by standard_executor.py. This queue sentinel just ends the loop.
            logger.debug("Queue sentinel received, ending stream (session=%s)", session_id)

            # Mark stream as completed in buffer
            if session_id:
                await buffer_manager.mark_completed(session_id)

            break

        if isinstance(chunk, dict):
            payload = dict(chunk)
            # Add session_id to the appropriate location based on event structure
            if session_id:
                # For events with 'data' structure (thinking_chunk, tool_start, etc.),
                # session_id goes inside data to match frontend schema
                if "data" in payload and isinstance(payload["data"], dict):
                    if "session_id" not in payload["data"]:
                        payload["data"] = dict(payload["data"])
                        payload["data"]["session_id"] = session_id
                elif "session_id" not in payload:
                    payload["session_id"] = session_id

            message_type = payload.get("type")

            # Add chunk_index and buffer for streamable types (text_chunk, thinking_chunk)
            if message_type in ("text_chunk", "thinking_chunk"):
                chunk_counter += 1
                if "data" in payload and isinstance(payload["data"], dict):
                    payload["data"]["chunk_index"] = chunk_counter
                else:
                    payload["chunk_index"] = chunk_counter

                # Buffer for potential replay after reconnect
                if session_id:
                    await buffer_manager.add_chunk(session_id, payload)
                    # Log every 10th chunk to avoid spam
                    if chunk_counter % 10 == 1:
                        logger.info(
                            "📦 Buffering chunk %d (type=%s, session=%s)",
                            chunk_counter,
                            message_type,
                            session_id[:8] if session_id else "none",
                        )
                else:
                    logger.warning(
                        "⚠️ Cannot buffer chunk %d - no session_id!",
                        chunk_counter,
                    )

                logger.debug(
                    "Streaming chunk %d (type=%s, session=%s)",
                    chunk_counter,
                    message_type,
                    session_id[:8] if session_id else "none",
                )

            if message_type == "error":
                logger.error(
                    "Forwarding workflow error to frontend (session=%s, stage=%s, detail=%s)",
                    session_id,
                    payload.get("stage"),
                    payload.get("content"),
                )
            elif message_type == "working":
                descriptor = payload.get("content")
                logger.debug(
                    "Forwarding workflow progress event (session=%s, descriptor=%s)",
                    session_id,
                    descriptor,
                )
            elif message_type == "db_operation_executed":
                content = payload.get("content")
                content_keys = list(content.keys()) if isinstance(content, dict) else []
                logger.info(
                    "Database operation acknowledged by backend (session=%s, content_keys=%s)",
                    session_id,
                    content_keys,
                )
            elif message_type == "tool_start":
                call_overview = payload.get("content")
                logger.info(
                    "Forwarding tool call to frontend (session=%s, summary_keys=%s)",
                    session_id,
                    list(call_overview.keys())
                    if isinstance(call_overview, dict)
                    else type(call_overview),
                )
            elif message_type in {"custom_event"}:
                # Claude sidecar events come wrapped as custom_event
                logger.debug(
                    "Forwarding custom event to frontend (session=%s, type=%s)",
                    session_id,
                    message_type,
                )
            elif message_type == "thinking_chunk":
                logger.debug(
                    "Forwarding reasoning chunk to frontend (session=%s)",
                    session_id,
                )

            sanitized_payload = sanitize_for_json(payload)
            await websocket.send_json(sanitized_payload)
        else:
            # PATH 2: Plain string chunks - also need chunk_index and buffering
            chunk_counter += 1
            text_preview = str(chunk)
            if len(text_preview) > 120:
                text_preview = f"{text_preview[:117]}…"
            logger.debug(
                "Streaming text chunk %d to frontend (session=%s, preview=%s)",
                chunk_counter,
                session_id[:8] if session_id else "none",
                text_preview,
            )
            payload = {
                "type": "text_chunk",
                "content": chunk,
                "chunk_index": chunk_counter,
            }
            if session_id:
                payload["session_id"] = session_id
                await buffer_manager.add_chunk(session_id, payload)

            sanitized_payload = sanitize_for_json(payload)
            await websocket.send_json(sanitized_payload)


async def monitor_session_idle(
    websocket: WebSocket,
    session: WorkflowSession,
    *,
    timeout_seconds: int,
) -> None:
    """Close idle sessions after the configured timeout."""

    poll_interval = min(max(timeout_seconds / 6, _MIN_IDLE_CHECK_SECONDS), _MAX_IDLE_CHECK_SECONDS)

    try:
        while True:
            await asyncio.sleep(poll_interval)

            if session.is_expired(timeout_seconds):
                logger.info(
                    "Closing idle websocket session %s (customer=%s)",
                    session.session_id,
                    session.customer_id,
                )
                with suppress(Exception):
                    await websocket.send_json(
                        {
                            "type": "closing",
                            "reason": "timeout",
                            "session_id": session.session_id,
                        }
                    )
                with suppress(Exception):
                    await websocket.close(code=1001)
                break
    except asyncio.CancelledError:
        logger.debug("Session idle monitor cancelled for %s", session.session_id)
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Idle monitor error for session %s: %s", session.session_id, exc)
