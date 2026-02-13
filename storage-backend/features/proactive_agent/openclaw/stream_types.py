"""Stream types for OpenClaw Chat Adapter.

This module defines types used for stream management in the adapter:
- StreamContext: Tracks state and callbacks for a single message stream
- extract_chat_text: Extracts text content from OpenClaw chat payloads
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class StreamContext:
    """Tracks state and callbacks for a single message stream.

    Attributes:
        user_id: User ID for the stream
        session_id: Session identifier
        run_id: Unique run identifier (idempotency key)
        session_key: OpenClaw session key (e.g., "openclaw:session-1")
        started: Whether stream_start has been emitted
        text_buffer: Accumulated text from deltas
        seq: Last processed sequence number
        attachments: Optional list of attachments (images, files)
        on_stream_start: Callback for stream start (session_id)
        on_text_chunk: Callback for text chunks (text)
        on_stream_end: Callback for stream end (session_id, run_id, final_text)
        on_error: Callback for errors (error_message)
        on_tool_start: Callback for tool start (tool_name, args, tool_call_id)
        on_tool_result: Callback for tool result (tool_name, result, is_error, tool_call_id)
        on_thinking_chunk: Callback for thinking/reasoning (text)
    """

    user_id: int
    session_id: str
    run_id: str
    session_key: str
    started: bool = False
    text_buffer: str = ""  # Buffer for diffing with OpenClaw cumulative deltas
    total_text: str = ""   # Total text sent to frontend (never reset, only appends)
    seq: int = 0
    attachments: Optional[list[dict[str, Any]]] = None
    on_stream_start: Optional[Callable[[str], Awaitable[None]]] = None
    on_text_chunk: Optional[Callable[[str], Awaitable[None]]] = None
    on_stream_end: Optional[Callable[[str, str, str], Awaitable[None]]] = None
    on_error: Optional[Callable[[str], Awaitable[None]]] = None
    # Tool event callbacks
    on_tool_start: Optional[Callable[[str, Optional[dict], Optional[str]], Awaitable[None]]] = None
    on_tool_result: Optional[Callable[[str, Any, bool, Optional[str]], Awaitable[None]]] = None
    # Thinking event callback
    on_thinking_chunk: Optional[Callable[[str], Awaitable[None]]] = None
    # Timestamps for timeout tracking
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    def touch(self) -> None:
        """Update last_activity timestamp."""
        self.last_activity = time.time()
    
    def age_seconds(self) -> float:
        """Return seconds since stream was created."""
        return time.time() - self.created_at
    
    def idle_seconds(self) -> float:
        """Return seconds since last activity."""
        return time.time() - self.last_activity


def extract_chat_text(payload: dict[str, Any]) -> str:
    """Extract text content from OpenClaw chat payloads.

    Handles multiple message formats:
    - Direct string: payload.message (str)
    - Content string: payload.message.content (str)
    - Content blocks: payload.message.content (list of dicts with type/text)

    Args:
        payload: Event payload from OpenClaw chat event

    Returns:
        Extracted text string, empty string if no text found
    """
    message = payload.get("message")
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Accumulate ALL text blocks (not just the first one)
        text_parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type in {"text", "output_text"}:
                text = block.get("text") or ""
                if text:
                    text_parts.append(text)
        if text_parts:
            # Join with newlines to separate distinct text blocks
            return "\n\n".join(text_parts)
        # Fallback: look for any block with a "text" field
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if text and isinstance(text, str):
                logger.debug(
                    "Found text in non-standard block type: %s",
                    block.get("type"),
                )
                text_parts.append(text)
        if text_parts:
            return "\n\n".join(text_parts)
        logger.debug("Content is list but no text found (blocks=%d)", len(content))
    elif content is not None:
        # Log unexpected content type
        logger.debug(
            "Unexpected content type: %s (value=%s)",
            type(content).__name__,
            repr(content)[:100] if content else None,
        )
    return ""
