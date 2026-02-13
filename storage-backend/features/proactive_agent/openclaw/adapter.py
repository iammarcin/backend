"""OpenClaw Chat Adapter for Sherlock mobile events.

This module adapts OpenClaw Gateway protocol to the mobile WebSocket event format.
It handles sending chat messages and mapping streaming responses to mobile events.

Event Mapping:
- First delta -> stream_start
- Each delta -> text_chunk (incremental)
- Final -> stream_end
- Error/Aborted -> stream_error

Design: Single shared OpenClaw connection serving multiple sessions concurrently.
"""

import base64
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

import httpx

# Timeout for streams that stop receiving events (10 minutes).
# CLI agents (sherlock) can have multi-minute gaps between events during:
# - Context auto-compaction (2-3+ min with zero events)
# - Complex tool chains, subagent spawns, long bash commands
# The idle threshold must exceed those gaps to avoid force-completing live streams.
STREAM_TIMEOUT_SECONDS = 600
STALE_CLEANUP_INTERVAL_SECONDS = 60.0
STALE_CLEANUP_IDLE_SECONDS = STREAM_TIMEOUT_SECONDS

from .adapter_handlers import handle_aborted, handle_delta, handle_error, handle_final
from .client import OpenClawClient
from .exceptions import RequestError
from .stream_types import StreamContext

logger = logging.getLogger(__name__)

# Re-export StreamContext for backwards compatibility
__all__ = ["OpenClawAdapter", "StreamContext"]


class OpenClawAdapter:
    """Adapts OpenClaw Gateway protocol to Sherlock mobile event format.

    Handles:
    - Sending chat.send requests
    - Mapping streaming events to mobile format
    - Per-run callback routing (shared connection)
    - Text accumulation for final message
    """

    def __init__(self, client: OpenClawClient):
        """Initialize the adapter.

        Args:
            client: Connected OpenClawClient instance
        """
        self._client = client
        self._active_streams: dict[str, StreamContext] = {}
        self._last_stale_cleanup_monotonic = 0.0

    @property
    def active_stream_count(self) -> int:
        """Return count of active streams."""
        return len(self._active_streams)

    def get_active_run_ids(self) -> list[str]:
        """Return list of active run IDs."""
        return list(self._active_streams.keys())

    def get_run_id_for_session(self, session_id: str) -> str | None:
        """Find the active run ID for a given session ID.

        Args:
            session_id: Session ID to look up

        Returns:
            run_id if found, None otherwise
        """
        for run_id, context in self._active_streams.items():
            if context.session_id == session_id:
                return run_id
        return None

    async def send_message(
        self,
        *,
        user_id: int,
        session_id: str,
        session_key: str,
        message: str,
        on_stream_start: Callable[[str], Awaitable[None]],
        on_text_chunk: Callable[[str], Awaitable[None]],
        on_stream_end: Callable[[str, str, str], Awaitable[None]],
        on_error: Callable[[str], Awaitable[None]],
        on_tool_start: Optional[Callable[[str, Optional[dict], Optional[str]], Awaitable[None]]] = None,
        on_tool_result: Optional[Callable[[str, Any, bool, Optional[str]], Awaitable[None]]] = None,
        on_thinking_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
        attachments: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """Send message to OpenClaw and start tracking response stream.

        Args:
            user_id: User ID
            session_id: Session identifier
            session_key: OpenClaw session key (e.g., "openclaw:session-1")
            message: Message text to send
            on_stream_start: Callback for stream_start(session_id)
            on_text_chunk: Callback for text_chunk(text)
            on_stream_end: Callback for stream_end(session_id, message_id, final_text)
            on_error: Callback for stream_error(error_message)
            on_tool_start: Callback for tool_start(tool_name, args, tool_call_id)
            on_tool_result: Callback for tool_result(tool_name, result, is_error, tool_call_id)
            on_thinking_chunk: Callback for thinking_chunk(text)
            attachments: Optional list of attachments (images, files)

        Returns:
            run_id (used as idempotency key)

        Raises:
            RequestError: If chat.send request fails
        """
        run_id = str(uuid.uuid4())

        context = StreamContext(
            user_id=user_id,
            session_id=session_id,
            run_id=run_id,
            session_key=session_key,
            attachments=attachments,
            on_stream_start=on_stream_start,
            on_text_chunk=on_text_chunk,
            on_stream_end=on_stream_end,
            on_error=on_error,
            on_tool_start=on_tool_start,
            on_tool_result=on_tool_result,
            on_thinking_chunk=on_thinking_chunk,
        )
        self._active_streams[run_id] = context

        params = await self._build_send_params(session_key, message, run_id, attachments)

        try:
            response = await self._client.request("chat.send", params)

            # Check if OpenClaw returns a different runId than our idempotencyKey
            response_run_id = response.get("runId")
            if response_run_id and response_run_id != run_id:
                # OpenClaw assigned its own runId - re-register with the correct one
                logger.warning(
                    "OpenClaw assigned different runId: sent=%s, received=%s",
                    run_id[:8],
                    response_run_id[:8],
                )
                self._active_streams.pop(run_id, None)
                context.run_id = response_run_id
                self._active_streams[response_run_id] = context
                run_id = response_run_id

            logger.info(f"chat.send accepted: run_id={run_id[:8]}..., status={response.get('status')}")
            return run_id
        except Exception as e:
            self._active_streams.pop(run_id, None)
            logger.error(f"chat.send failed: run_id={run_id[:8]}..., error={e}")
            raise

    async def _build_send_params(
        self,
        session_key: str,
        message: str,
        run_id: str,
        attachments: Optional[list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Build chat.send request parameters.
        
        For image attachments, fetches the image from URL and converts to base64
        as required by OpenClaw Gateway.
        """
        params: dict[str, Any] = {
            "sessionKey": session_key,
            "message": message,
            "idempotencyKey": run_id,
        }

        if attachments:
            openclaw_attachments = []
            document_refs: list[str] = []
            async with httpx.AsyncClient(timeout=30.0) as client:
                for att in attachments:
                    att_type = att.get("type")
                    att_url = att.get("url")
                    
                    if att_type == "image" and att_url:
                        try:
                            # Fetch image from URL
                            response = await client.get(att_url)
                            response.raise_for_status()
                            
                            # Get content type and filename
                            content_type = response.headers.get("content-type", "image/png")
                            # Clean content type (remove charset etc)
                            content_type = content_type.split(";")[0].strip()
                            filename = att.get("filename") or att_url.split("/")[-1] or "image.png"
                            
                            # Base64 encode
                            b64_content = base64.b64encode(response.content).decode("utf-8")
                            
                            # OpenClaw expects this format
                            openclaw_attachments.append({
                                "type": content_type,
                                "mimeType": content_type,
                                "fileName": filename,
                                "content": b64_content,
                            })
                            
                            logger.info(
                                f"Attachment fetched: {filename} ({content_type}, {len(response.content)} bytes)"
                            )
                            
                        except Exception as e:
                            logger.warning(f"Failed to fetch attachment {att_url}: {e}")
                            # Skip failed attachments rather than failing the whole message
                            continue
                    
                    elif att_type == "document" and att_url:
                        filename = att.get("filename") or att_url.split("/")[-1] or "document.pdf"
                        document_refs.append(
                            f'The user attached a document.\n'
                            f'Download it first, then read it:\n'
                            f'1. curl -sS -o "/tmp/{filename}" "{att_url}"\n'
                            f'2. Read the file'
                        )
                        logger.info(f"Document attachment URL added to message: {filename}")
            
            if document_refs:
                refs_text = "\n".join(document_refs)
                params["message"] = f"{refs_text}\n\n{params['message']}"
                logger.info(f"Added {len(document_refs)} document URL(s) to message")

            if openclaw_attachments:
                params["attachments"] = openclaw_attachments
                logger.info(f"Sending {len(openclaw_attachments)} attachment(s) to OpenClaw")
                # Debug: log first 100 chars of base64 content for verification
                for att in openclaw_attachments:
                    content_preview = att.get("content", "")[:100]
                    logger.debug(
                        f"Attachment debug: mimeType={att.get('mimeType')}, "
                        f"fileName={att.get('fileName')}, content_preview={content_preview}..."
                    )

        logger.debug(f"chat.send params keys: {list(params.keys())}")
        return params

    async def handle_event(self, event: dict[str, Any]) -> None:
        """Process incoming events from OpenClaw (chat + agent).

        Routes events to appropriate handlers based on type.
        Args:
            event: Event frame from OpenClawClient
        """
        await self._maybe_cleanup_stale_streams()
        event_type = event.get("event")

        if event_type == "chat":
            await self._handle_chat_event(event)
        elif event_type == "agent":
            await self._handle_agent_event(event)
        # else: ignore other event types

    async def _handle_chat_event(self, event: dict[str, Any]) -> None:
        """Handle chat events (text streaming)."""
        payload = event.get("payload", {})
        run_id = payload.get("runId")

        if not run_id:
            logger.warning(f"Chat event missing runId: {event}")
            return

        context = self._active_streams.get(run_id)
        if not context:
            # Expected noise: OpenClaw broadcasts events to ALL connected
            # clients, including cron jobs the backend didn't initiate.
            state = payload.get("state")
            session_key = payload.get("sessionKey", "?")
            logger.debug(
                "Chat event for non-tracked run_id: %s, state=%s, session=%s (broadcast noise)",
                run_id[:8], state, session_key,
            )
            return

        state = payload.get("state")
        #logger.debug(f"Processing chat event: run_id={run_id[:8]}..., state={state}")

        if state == "delta":
            await handle_delta(context, payload)
        elif state == "final":
            await handle_final(context, payload)
            self._active_streams.pop(run_id, None)
            logger.debug(f"Stream completed: run_id={run_id[:8]}...")
        elif state == "error":
            await handle_error(context, payload)
            self._active_streams.pop(run_id, None)
        elif state == "aborted":
            await handle_aborted(context)
            self._active_streams.pop(run_id, None)
        else:
            logger.warning(f"Unknown chat state: {state}")

    async def _handle_agent_event(self, event: dict[str, Any]) -> None:
        """Handle agent events (tool execution, thinking).

        Event format from OpenClaw:
        {
            "event": "agent",
            "payload": {
                "runId": "...",
                "sessionKey": "...",
                "stream": "tool" | "thinking",
                "data": { ... }
            }
        }
        """
        payload = event.get("payload", {})
        run_id = payload.get("runId")

        if not run_id:
            logger.debug("Agent event missing runId, ignoring")
            return

        context = self._active_streams.get(run_id)
        if not context:
            # Expected noise: OpenClaw broadcasts agent events to ALL connected
            # clients, including cron jobs the backend didn't initiate.
            stream = payload.get("stream", "?")
            session_key = payload.get("sessionKey", "?")
            #logger.debug(
            #    "Agent event for non-tracked run_id: %s, stream=%s, session=%s (broadcast noise)",
            #    run_id[:8], stream, session_key,
            #)
            return

        # Update activity timestamp - agent events count as activity
        context.touch()

        stream = payload.get("stream")
        data = payload.get("data", {})

        if stream == "lifecycle":
            await self._handle_lifecycle_event(context, run_id, data)
        elif stream in ("tool", "tool-info"):
            await self._handle_tool_event(context, data)
        elif stream == "thinking":
            await self._handle_thinking_event(context, data)
        elif stream == "assistant":
            # Assistant stream duplicates chat content - ignore it
            # Only "thinking" stream contains actual extended thinking
            pass
        else:
            logger.debug(f"Unknown agent stream type: {stream}")

    async def _handle_lifecycle_event(
        self,
        context: StreamContext,
        run_id: str,
        data: dict[str, Any],
    ) -> None:
        """Handle lifecycle events emitted by OpenClaw agent runner."""
        phase = data.get("phase")
        if phase != "steered":
            return

        # Reset text buffers — the agent resets runAssistantText on steer,
        # so our context must mirror that. Without this, iter2's deltas
        # append to iter1's total_text and handle_final's reconciliation
        # re-emits the entire iter2 text as a spurious tail (duplication).
        logger.info(
            "Steer context reset: run_id=%s, session=%s, discarding %d chars",
            run_id[:8],
            context.session_id[:8],
            len(context.total_text),
        )
        context.text_buffer = ""
        context.total_text = ""
        context.seq = 0

        orphan_ids = [
            candidate_run_id
            for candidate_run_id, candidate_context in self._active_streams.items()
            if candidate_run_id != run_id
            and candidate_context.session_id == context.session_id
            and not candidate_context.started
        ]
        for orphan_run_id in orphan_ids:
            self._active_streams.pop(orphan_run_id, None)

        if orphan_ids:
            logger.info(
                "Steer lifecycle cleanup: run_id=%s, session=%s, removed_orphans=%d",
                run_id[:8],
                context.session_id[:8],
                len(orphan_ids),
            )

    async def _maybe_cleanup_stale_streams(self) -> None:
        """Periodically force-complete stale streams as safety net."""
        now = time.monotonic()
        if now - self._last_stale_cleanup_monotonic < STALE_CLEANUP_INTERVAL_SECONDS:
            return
        self._last_stale_cleanup_monotonic = now
        cleaned = await self.cleanup_stale_streams(timeout_seconds=STALE_CLEANUP_IDLE_SECONDS)
        if cleaned > 0:
            logger.warning("Periodic stale stream cleanup removed %d stream(s)", cleaned)

    async def _handle_tool_event(self, context: StreamContext, data: dict[str, Any]) -> None:
        """Handle tool execution events."""
        phase = data.get("phase")
        tool_name = data.get("name")
        tool_call_id = data.get("toolCallId")

        # Guard: require tool_name
        if not tool_name:
            logger.debug("Tool event missing name, ignoring")
            return

        if phase == "start":
            args = data.get("args", {})
            # Log tool details for debugging
            args_preview = ""
            if isinstance(args, dict):
                # Extract useful info based on tool type
                if tool_name == "read" or tool_name == "Read":
                    args_preview = f"path={args.get('path', args.get('file_path', '?'))}"
                elif tool_name == "exec":
                    cmd = args.get("command", "")[:50]
                    args_preview = f"cmd={cmd}..."
                elif tool_name == "write" or tool_name == "Write":
                    args_preview = f"path={args.get('path', args.get('file_path', '?'))}"
                elif tool_name == "edit" or tool_name == "Edit":
                    args_preview = f"path={args.get('path', args.get('file_path', '?'))}"
                else:
                    # Generic: show first key-value
                    for k, v in list(args.items())[:1]:
                        args_preview = f"{k}={str(v)[:30]}"
            logger.info(f"🔧 TOOL START: {tool_name} | {args_preview}")
            
            if context.on_tool_start:
                # Guard: ensure args is dict or None
                if args is not None and not isinstance(args, dict):
                    args = {"raw": str(args)}
                await context.on_tool_start(tool_name, args, tool_call_id)

        elif phase == "result":
            is_error = data.get("isError", False)
            result = data.get("result", {})
            result_preview = str(result)[:100] if result else ""
            status = "❌ ERROR" if is_error else "✅ OK"
            logger.info(f"🔧 TOOL RESULT: {tool_name} {status} | {result_preview}...")
            
            if context.on_tool_result:
                await context.on_tool_result(tool_name, result, is_error, tool_call_id)

        elif phase == "update":
            # Drop update events (partial results) - UI doesn't need them
            logger.debug(f"Dropping tool update event: {tool_name}")

        else:
            logger.debug(f"Unknown tool phase: {phase}")

    async def _handle_thinking_event(self, context: StreamContext, data: dict[str, Any]) -> None:
        """Handle thinking/reasoning events."""
        if not context.on_thinking_chunk:
            return

        text = data.get("text", "")
        if text:
            await context.on_thinking_chunk(text)

    async def _handle_assistant_stream(self, context: StreamContext, data: dict[str, Any]) -> None:
        """Handle assistant stream events (reasoning/narration text).
        
        The assistant stream contains cumulative text like "Let me check...", "Now I'll..."
        that represents Claude's reasoning/narration before taking actions.
        
        We route this to thinking_chunk to display separately from main response.
        """
        if not context.on_thinking_chunk:
            return

        text = data.get("text", "")
        if not text:
            return
        
        # Assistant stream sends CUMULATIVE text (like chat deltas)
        # We need to track what we've sent and only send the new part
        # Use a separate buffer on the context for assistant text
        if not hasattr(context, '_assistant_buffer'):
            context._assistant_buffer = ""
        
        if text.startswith(context._assistant_buffer):
            # Normal case: new text extends the buffer
            new_text = text[len(context._assistant_buffer):]
            context._assistant_buffer = text
        else:
            # Reset case: new text doesn't continue from buffer
            # (happens when tool interrupts and Claude continues with new reasoning)
            logger.debug(f"Assistant stream reset: buffer={len(context._assistant_buffer)}→{len(text)}")
            new_text = text
            context._assistant_buffer = text
        
        if new_text:
            await context.on_thinking_chunk(new_text)

    async def abort(self, run_id: str) -> bool:
        """Cancel an active request.

        Args:
            run_id: Run ID to cancel

        Returns:
            True if abort request was sent, False if run_id not found or request failed
        """
        context = self._active_streams.get(run_id)
        if not context:
            logger.debug(f"Abort requested for unknown run_id: {run_id[:8]}...")
            return False

        try:
            await self._client.request("chat.abort", {"sessionKey": context.session_key, "runId": run_id})
            logger.info(f"Abort sent: run_id={run_id[:8]}...")
            return True
        except RequestError as e:
            logger.warning(f"Abort failed: run_id={run_id[:8]}..., error={e}")
            return False
        except Exception as e:
            logger.error(f"Abort error: run_id={run_id[:8]}..., error={e}")
            return False

    def cleanup_stream(self, run_id: str) -> None:
        """Remove stream context without sending events."""
        if run_id in self._active_streams:
            self._active_streams.pop(run_id)
            logger.debug(f"Stream cleaned up: run_id={run_id[:8]}...")

    def cleanup_all_streams(self) -> list[str]:
        """Remove all stream contexts without sending events."""
        run_ids = list(self._active_streams.keys())
        self._active_streams.clear()
        logger.info(f"Cleaned up {len(run_ids)} streams")
        return run_ids

    def get_stale_streams(self, timeout_seconds: float = STREAM_TIMEOUT_SECONDS) -> list[str]:
        """Return run_ids of streams that have been idle for too long.
        
        Args:
            timeout_seconds: Max idle time before stream is considered stale
            
        Returns:
            List of stale run_ids
        """
        stale = []
        for run_id, context in self._active_streams.items():
            if context.idle_seconds() > timeout_seconds:
                stale.append(run_id)
        return stale

    async def force_complete_stream(self, run_id: str, reason: str = "timeout") -> bool:
        """Force a stream to complete, saving accumulated content.
        
        This is used to recover from streams that never receive a final event.
        It sends stream_end with the accumulated total_text.
        
        Args:
            run_id: Run ID of stream to complete
            reason: Reason for force completion (for logging)
            
        Returns:
            True if stream was completed, False if not found
        """
        context = self._active_streams.pop(run_id, None)
        if not context:
            return False
        
        logger.warning(
            "Force completing stream (reason=%s): run_id=%s, session=%s, "
            "total_text=%d chars, age=%.1fs, idle=%.1fs",
            reason,
            run_id[:8],
            context.session_id[:8],
            len(context.total_text),
            context.age_seconds(),
            context.idle_seconds(),
        )
        
        # Orphan guard: never-started contexts should not emit synthetic
        # stream_start/stream_end or persist empty/partial output.
        if not context.started:
            logger.info(
                "Skipping force completion for non-started context: run_id=%s, session=%s",
                run_id[:8],
                context.session_id[:8],
            )
            return True
        
        # Use total_text (accumulated) or text_buffer as final content
        final_text = context.total_text or context.text_buffer
        
        if context.on_stream_end:
            await context.on_stream_end(
                context.session_id,
                context.run_id,
                final_text,
            )
        
        return True

    async def cleanup_stale_streams(self, timeout_seconds: float = STREAM_TIMEOUT_SECONDS) -> int:
        """Check for and force-complete any stale streams.
        
        Args:
            timeout_seconds: Max idle time before stream is considered stale
            
        Returns:
            Number of streams cleaned up
        """
        stale_ids = self.get_stale_streams(timeout_seconds)
        for run_id in stale_ids:
            await self.force_complete_stream(run_id, reason="idle_timeout")
        return len(stale_ids)
