"""Event handlers for OpenClaw adapter streaming events.

This module contains handlers for different chat event states:
- delta: Partial response streaming
- final: Complete response
- error: Error responses
- aborted: Cancelled requests
"""

import logging
from typing import Any

from .stream_types import StreamContext, extract_chat_text

logger = logging.getLogger(__name__)


def _common_prefix_len(a: str, b: str) -> int:
    """Return the shared prefix length between two strings."""
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[i] == b[i]:
        i += 1
    return i


async def handle_delta(context: StreamContext, payload: dict[str, Any]) -> None:
    """Process delta (partial response) event.

    OpenClaw provides accumulated text in each delta.
    Computes incremental chunk by diffing with text_buffer.

    Args:
        context: Stream context
        payload: Event payload
    """
    # Update activity timestamp for timeout tracking
    context.touch()
    
    text = extract_chat_text(payload)

    if not text:
        logger.debug(
            "Chat delta missing text (run_id=%s, seq=%s)",
            context.run_id[:8],
            payload.get("seq"),
        )
        return

    seq = payload.get("seq", 0)
    if seq <= context.seq and len(text) <= len(context.text_buffer):
        return
    if seq > context.seq:
        context.seq = seq

    if not context.started:
        context.started = True
        if context.on_stream_start:
            await context.on_stream_start(context.session_id)

    if text.startswith(context.text_buffer):
        new_text = text[len(context.text_buffer):]
        context.text_buffer = text
    else:
        # Delta reset: new text doesn't continue from buffer
        # This happens when tool use interrupts the stream
        logger.info(
            "Delta reset (run_id=%s): buffer=%d→%d chars, total=%d chars",
            context.run_id[:8], 
            len(context.text_buffer), 
            len(text), 
            len(context.total_text),
        )
        
        # Simple separator: space only if word-to-word boundary
        separator = ""
        if context.total_text and text:
            last_char = context.total_text[-1]
            first_char = text[0]
            if last_char.isalnum() and first_char.isalnum():
                separator = " "
        
        new_text = separator + text
        context.text_buffer = text

    if new_text:
        # Track total text sent to frontend (this never resets)
        context.total_text += new_text
        if context.on_text_chunk:
            await context.on_text_chunk(new_text)


async def handle_final(context: StreamContext, payload: dict[str, Any]) -> None:
    """Process final (complete response) event.

    Args:
        context: Stream context
        payload: Event payload
    """
    final_text = extract_chat_text(payload)

    # Guard: if this context never received any streaming events (no deltas),
    # it's a steer orphan — OpenClaw broadcasts chat/final for queued messages
    # that never started a new run. Sending stream_start + stream_end here
    # would reset the frontend's streaming state and cause the real run's
    # text_chunks to be silently dropped.
    if not context.started:
        logger.info(
            "Skipping final for non-started context (steer orphan): run_id=%s, session=%s, final_text=%d chars",
            context.run_id[:8],
            context.session_id[:8],
            len(final_text or ""),
        )
        return

    streamed_text = context.total_text or context.text_buffer or ""
    best_final = streamed_text

    # Deterministic finalization:
    # 1) Streamed text is for live UX only
    # 2) final_text is the source of truth for persisted output
    # 3) emit only missing tail so UI/TTS can catch up before stream_end
    if final_text:
        prefix_len = _common_prefix_len(streamed_text, final_text)
        tail = final_text[prefix_len:]
        if tail and context.on_text_chunk:
            await context.on_text_chunk(tail)
            logger.info(
                "Reconciled final tail (run_id=%s): prefix=%d, tail=%d",
                context.run_id[:8],
                prefix_len,
                len(tail),
            )
        best_final = final_text
        context.total_text = final_text
        context.text_buffer = final_text
    
    logger.info(
        "Stream final (run_id=%s): total_text=%d, text_buffer=%d, final_text=%d, using=%d chars",
        context.run_id[:8],
        len(context.total_text),
        len(context.text_buffer),
        len(final_text or ""),
        len(best_final),
    )

    if context.on_stream_end:
        await context.on_stream_end(
            context.session_id,
            context.run_id,
            best_final,
        )


async def handle_error(context: StreamContext, payload: dict[str, Any]) -> None:
    """Process error event.

    Args:
        context: Stream context
        payload: Event payload
    """
    error_message = payload.get("errorMessage", "Unknown error")
    logger.warning(f"Stream error: run_id={context.run_id[:8]}..., error={error_message}")

    if context.on_error:
        await context.on_error(error_message)


async def handle_aborted(context: StreamContext) -> None:
    """Process aborted event.

    Args:
        context: Stream context
    """
    logger.info(f"Stream aborted: run_id={context.run_id[:8]}...")

    if context.on_error:
        await context.on_error("Request was aborted")
