"""Stream callback handlers for OpenClaw router.

This module provides callback handlers for OpenClaw streaming events:
- StreamCallbacks: Encapsulates callback functions and TTS state
- Handles stream_start, text_chunk, stream_end, and error events
- Integrates with TTS for parallel audio generation
"""

import logging
from typing import Any, Optional

from features.proactive_agent.poller_stream.marker_detector import (
    MarkerDetector,
    MarkerType,
    DetectedMarker,
)

logger = logging.getLogger(__name__)


def _is_tts_enabled(tts_settings: Optional[dict[str, Any]]) -> bool:
    """Check if TTS auto-execute is enabled in settings."""
    return bool(
        tts_settings
        and isinstance(tts_settings, dict)
        and tts_settings.get("tts_auto_execute", False)
    )


class StreamCallbacks:
    """Encapsulates streaming callback handlers with TTS integration.

    This class provides callback functions for OpenClaw streaming events,
    handling mobile push notifications and TTS audio generation.

    Usage:
        callbacks = StreamCallbacks(
            user_id=1,
            session_id="session-123",
            ai_character_name="sherlock",
            tts_settings={"tts_auto_execute": True},
            registry=proactive_registry,
        )
        await adapter.send_message(
            on_stream_start=callbacks.on_stream_start,
            on_text_chunk=callbacks.on_text_chunk,
            on_stream_end=callbacks.on_stream_end,
            on_error=callbacks.on_error,
        )
    """

    def __init__(
        self,
        user_id: int,
        session_id: str,
        ai_character_name: str,
        tts_settings: Optional[dict[str, Any]],
        registry: Any,
        marker_detector: Optional[MarkerDetector] = None,
    ):
        """Initialize stream callbacks.

        Args:
            user_id: User ID for push notifications
            session_id: Session ID for the chat
            ai_character_name: Character name (for events)
            tts_settings: TTS settings (tts_auto_execute, voice, model, etc.)
            registry: Proactive registry for push notifications
        """
        self.user_id = user_id
        self.session_id = session_id
        self.ai_character_name = ai_character_name
        self.tts_settings = tts_settings
        self.registry = registry
        self.tts_enabled = _is_tts_enabled(tts_settings)
        self.text_sent = False
        self._tts_text_buffer = ""
        self._marker_detector = marker_detector

    async def on_stream_start(self, sess_id: str) -> None:
        """Push stream_start to mobile and start TTS if enabled."""
        if self.tts_enabled:
            await self._start_tts_session(sess_id)

        await self.registry.push_to_user(
            self.user_id,
            {
                "type": "stream_start",
                "data": {
                    "session_id": sess_id,
                    "ai_character_name": self.ai_character_name,
                },
            },
        )
        logger.debug("Pushed stream_start to user %s", self.user_id)

    async def on_text_chunk(self, text: str) -> None:
        """Push text_chunk to mobile and TTS manager."""
        await self.registry.push_to_user(
            self.user_id,
            {
                "type": "text_chunk",
                "data": {
                    "session_id": self.session_id,
                    "content": text,
                    "ai_character_name": self.ai_character_name,
                },
            },
        )

        if self.tts_enabled:
            await self._push_text_to_tts(text)

    async def on_stream_end(self, sess_id: str, run_id: str, final_text: str) -> None:
        """Save message to DB, complete TTS, and push stream_end to mobile."""
        # Detect and strip markers from final text (agent skills emit markers in text stream)
        cleaned_final_text = final_text
        if self._marker_detector and final_text:
            marker_result = self._marker_detector.detect(final_text)
            if marker_result.markers:
                cleaned_final_text = marker_result.cleaned_content
                try:
                    await self._handle_markers(marker_result.markers)
                except Exception as e:
                    logger.warning("Marker handling failed in stream_end, continuing: %s", e)

        from features.proactive_agent.dependencies import get_db_session_direct
        from features.proactive_agent.repositories import ProactiveAgentRepository

        db_message = None
        audio_file_url = None

        try:
            async with get_db_session_direct() as db:
                repository = ProactiveAgentRepository(db)
                db_message = await repository.create_message(
                    session_id=sess_id,
                    customer_id=self.user_id,
                    direction="agent_to_user",
                    content=cleaned_final_text,
                    source="text",
                    ai_character_name=self.ai_character_name,
                )
                logger.debug(
                    "Saved OpenClaw message: session=%s, message_id=%s",
                    sess_id[:8],
                    db_message.message_id,
                )

                # Handle TTS completion
                if self.tts_enabled:
                    audio_file_url = await self._complete_tts_session(
                        sess_id, cleaned_final_text, db_message, repository
                    )
        except Exception as e:
            logger.error("Failed to save OpenClaw message: %s", e)

        # Push stream_end to mobile
        await self.registry.push_to_user(
            self.user_id,
            {
                "type": "stream_end",
                "data": {
                    "session_id": sess_id,
                    "message_id": db_message.message_id if db_message else None,
                    "content": cleaned_final_text,
                    "audio_file_url": audio_file_url,
                    "ai_character_name": self.ai_character_name,
                },
            },
            session_scoped=True,
        )
        logger.info(
            "Stream completed: user=%s, session=%s, message=%s, chars=%d, audio=%s",
            self.user_id,
            sess_id[:8] if sess_id else "none",
            db_message.message_id if db_message else "none",
            len(cleaned_final_text),
            bool(audio_file_url),
        )

    async def on_error(self, error_message: str) -> None:
        """Cancel TTS and push stream_error to mobile."""
        if self.tts_enabled:
            await self._cancel_tts_session()

        await self.registry.push_to_user(
            self.user_id,
            {
                "type": "stream_error",
                "data": {
                    "code": "aborted" if "abort" in error_message.lower() else "error",
                    "message": error_message,
                    "session_id": self.session_id,
                    "recoverable": True,
                },
            },
        )
        logger.warning("Stream error for user %s: %s", self.user_id, error_message)

    async def on_tool_start(
        self,
        tool_name: str,
        args: dict | None,
        tool_call_id: str | None = None,
    ) -> None:
        """Push tool_start event to mobile."""
        display_text = self._make_tool_display_text(tool_name, args)

        payload: dict[str, Any] = {
            "type": "tool_start",
            "data": {
                "session_id": self.session_id,
                "tool_name": tool_name,
                "tool_input": args or {},
                "display_text": display_text,
                "ai_character_name": self.ai_character_name,
            },
        }

        # Include toolCallId for UI correlation (if available)
        if tool_call_id:
            payload["data"]["tool_call_id"] = tool_call_id

        await self.registry.push_to_user(self.user_id, payload)
        logger.debug("Pushed tool_start to user %s: %s", self.user_id, tool_name)

    # Tools whose output is file content — never scan for markers
    # (matches poller_stream/tool_tracker.py:SKIP_MARKER_TOOLS, lowercase for case-insensitive check)
    SKIP_MARKER_TOOLS: set[str] = {"read"}

    async def on_tool_result(
        self,
        tool_name: str,
        result: Any,
        is_error: bool,
        tool_call_id: str | None = None,
    ) -> None:
        """Push tool_result event to mobile, with marker detection."""
        # Detect and handle markers in string results
        cleaned_result = result
        if (
            self._marker_detector
            and isinstance(result, str)
            and not is_error
            and tool_name.lower() not in self.SKIP_MARKER_TOOLS
        ):
            marker_result = self._marker_detector.detect(result)
            if marker_result.markers:
                cleaned_result = marker_result.cleaned_content
                await self._handle_markers(marker_result.markers)

        # Truncate large results for display_text
        result_preview = ""
        if isinstance(cleaned_result, dict):
            result_preview = str(cleaned_result)[:100]
        elif isinstance(cleaned_result, str):
            result_preview = cleaned_result[:100]

        status = "failed" if is_error else "complete"
        display_text = f"{tool_name} {status}"
        if result_preview and not is_error:
            display_text = f"{tool_name}: {result_preview}{'...' if len(str(cleaned_result)) > 100 else ''}"

        payload: dict[str, Any] = {
            "type": "tool_result",
            "data": {
                "session_id": self.session_id,
                "tool_name": tool_name,
                "tool_result": cleaned_result,
                "display_text": display_text,
                "ai_character_name": self.ai_character_name,
            },
        }

        # Include toolCallId and is_error for UI correlation
        if tool_call_id:
            payload["data"]["tool_call_id"] = tool_call_id
        payload["data"]["is_error"] = is_error

        await self.registry.push_to_user(self.user_id, payload)
        logger.debug("Pushed tool_result to user %s: %s (error=%s)", self.user_id, tool_name, is_error)

    async def on_thinking_chunk(self, text: str) -> None:
        """Push thinking_chunk event to mobile."""
        await self.registry.push_to_user(
            self.user_id,
            {
                "type": "thinking_chunk",
                "data": {
                    "session_id": self.session_id,
                    "content": text,
                    "ai_character_name": self.ai_character_name,
                },
            },
        )
        #logger.debug("Pushed thinking_chunk to user %s: %d chars", self.user_id, len(text))

    async def _handle_markers(self, markers: list[DetectedMarker]) -> None:
        """Detect and dispatch marker-based events (charts, scenes, etc.)."""
        from features.proactive_agent.poller_stream.special_event_handlers import (
            handle_chart_event,
            handle_research_event,
            handle_scene_event,
            handle_component_update_event,
        )

        # Scene and component_update don't need DB — handle first
        for marker in markers:
            try:
                if marker.type == MarkerType.SCENE:
                    await handle_scene_event(
                        {"scene_data": marker.data},
                        self.user_id,
                        self.session_id,
                    )
                elif marker.type == MarkerType.COMPONENT_UPDATE:
                    await handle_component_update_event(
                        {"update_data": marker.data},
                        self.user_id,
                        self.session_id,
                    )
            except Exception as e:
                logger.warning("Failed to handle %s marker: %s", marker.type.value, e)

        # Chart and research need DB — fresh session per marker batch
        db_markers = [m for m in markers if m.type in (MarkerType.CHART, MarkerType.RESEARCH)]
        if not db_markers:
            return

        try:
            from features.proactive_agent.dependencies import get_db_session_direct
            from features.proactive_agent.repositories import ProactiveAgentRepository
            from features.proactive_agent.services.chart_handler import ChartHandler
            from features.proactive_agent.services.deep_research_handler import DeepResearchHandler

            async with get_db_session_direct() as db:
                repository = ProactiveAgentRepository(db)
                chart_handler = ChartHandler(repository)
                research_handler = DeepResearchHandler(repository)

                for marker in db_markers:
                    try:
                        if marker.type == MarkerType.CHART:
                            await handle_chart_event(
                                {"chart_data": marker.data},
                                self.user_id,
                                self.session_id,
                                self.ai_character_name,
                                chart_handler,
                            )
                        elif marker.type == MarkerType.RESEARCH:
                            await handle_research_event(
                                {"research_data": marker.data},
                                self.user_id,
                                self.session_id,
                                self.ai_character_name,
                                research_handler,
                            )
                    except Exception as e:
                        logger.warning("Failed to handle %s marker: %s", marker.type.value, e)
        except Exception as e:
            logger.warning("Failed to open DB session for marker handling: %s", e)

    def _make_tool_display_text(self, tool_name: str, args: dict | None) -> str:
        """Generate human-readable display text for tool execution."""
        if not args:
            return f"Running {tool_name}..."

        name_lower = tool_name.lower()

        if name_lower == "web_search":
            query = args.get("query", "...")
            return f"🔍 Search: {query[:50]}{'...' if len(str(query)) > 50 else ''}"
        elif name_lower == "read":
            path = args.get("path", args.get("file_path", "..."))
            filename = path.rsplit("/", 1)[-1] if "/" in path else path
            return f"📖 Read: {filename}"
        elif name_lower in ("exec", "bash"):
            cmd = args.get("command", "...")
            return f"⚡ Exec: {cmd[:50]}{'...' if len(str(cmd)) > 50 else ''}"
        elif name_lower == "write":
            path = args.get("path", args.get("file_path", "..."))
            filename = path.rsplit("/", 1)[-1] if "/" in path else path
            return f"✏️ Write: {filename}"
        elif name_lower == "edit":
            path = args.get("path", args.get("file_path", "..."))
            filename = path.rsplit("/", 1)[-1] if "/" in path else path
            return f"📝 Edit: {filename}"
        elif name_lower == "memory_search":
            query = args.get("query", "...")
            return f"🧠 Memory: {query[:40]}{'...' if len(str(query)) > 40 else ''}"
        elif name_lower == "browser":
            action = args.get("action", "...")
            return f"🌐 Browser: {action}"
        elif name_lower == "message":
            action = args.get("action", "...")
            target = args.get("target", args.get("to", ""))
            return f"Message: {action}" + (f" → {target}" if target else "")

        return f"Running {tool_name}..."

    # TTS helper methods

    async def _start_tts_session(self, sess_id: str) -> None:
        """Start TTS session if enabled."""
        try:
            from features.proactive_agent.streaming_registry import get_session
            from features.proactive_agent.utils.tts_session import start_tts_session
            from features.tts.service import TTSService

            if not get_session(sess_id, self.user_id):
                tts_service = TTSService()
                await start_tts_session(
                    session_id=sess_id,
                    user_id=self.user_id,
                    tts_settings=self.tts_settings or {},
                    tts_service=tts_service,
                )
                logger.debug(
                    "Started TTS session for user %s, session %s",
                    self.user_id,
                    sess_id[:8],
                )
        except Exception as e:
            logger.warning("Failed to start TTS session: %s", e)

    async def _push_text_to_tts(self, text: str) -> None:
        """Push text chunk to TTS manager."""
        try:
            from features.proactive_agent.streaming_registry import get_session

            streaming_session = get_session(self.session_id, self.user_id)
            if streaming_session and text:
                await streaming_session.manager.send_to_queues(
                    {"type": "text_chunk", "content": text}
                )
                self.text_sent = True
                self._tts_text_buffer += text
        except Exception as e:
            logger.warning("Failed to push text to TTS: %s", e)

    async def _complete_tts_session(
        self, sess_id: str, final_text: str, db_message: Any, repository: Any
    ) -> Optional[str]:
        """Complete TTS session and return audio URL."""
        try:
            from features.proactive_agent.streaming_registry import get_session
            from features.proactive_agent.utils.tts_session import complete_tts_session

            streaming_session = get_session(sess_id, self.user_id)
            if final_text and streaming_session:
                # Seed TTS queue with final text if no chunks were sent.
                if not self.text_sent:
                    await streaming_session.manager.send_to_queues(
                        {"type": "text_chunk", "content": final_text}
                    )
                    self.text_sent = True
                    self._tts_text_buffer = final_text
                    logger.debug("Seeded TTS queue with final text (session=%s)", sess_id[:8])
                # If text was streamed, reconcile using common-prefix tail.
                else:
                    streamed = self._tts_text_buffer
                    prefix_len = 0
                    limit = min(len(streamed), len(final_text))
                    while prefix_len < limit and streamed[prefix_len] == final_text[prefix_len]:
                        prefix_len += 1
                    tail = final_text[prefix_len:]
                    if tail:
                        await streaming_session.manager.send_to_queues(
                            {"type": "text_chunk", "content": tail}
                        )
                        logger.debug(
                            "Seeded TTS queue with reconciled tail (session=%s, prefix=%s, tail=%s)",
                            sess_id[:8],
                            prefix_len,
                            len(tail),
                        )
                    self._tts_text_buffer = final_text

            # Complete TTS session
            if get_session(sess_id, self.user_id):
                audio_file_url = await complete_tts_session(
                    session_id=sess_id,
                    user_id=self.user_id,
                    message=db_message,
                    update_audio_url_func=repository.update_message_audio_url,
                )
                if audio_file_url:
                    logger.debug("TTS completed with audio: %s", audio_file_url[:50])
                return audio_file_url
        except Exception as e:
            logger.warning("Failed to complete TTS session: %s", e)
        return None

    async def _cancel_tts_session(self) -> None:
        """Cancel TTS session on error."""
        try:
            from features.proactive_agent.utils.tts_session import cancel_tts_session

            await cancel_tts_session(session_id=self.session_id, user_id=self.user_id)
            logger.debug("Cancelled TTS session on error")
        except Exception as e:
            logger.warning("Failed to cancel TTS session: %s", e)
