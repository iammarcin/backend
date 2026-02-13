"""Event emitter for poller stream - bridges NDJSON parser to proactive handlers.

Transforms NDJSONLineParser events into proactive agent WebSocket events,
using existing handler infrastructure.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional

from core.connections import get_proactive_registry

from .ndjson_parser import EventType, ParsedEvent
from .schemas import InitMessage
from .special_event_handlers import (
    handle_chart_event,
    handle_component_update_event,
    handle_research_event,
    handle_scene_event,
)

from ..repositories import ProactiveAgentRepository
from ..utils.session_naming import schedule_session_naming, should_trigger_session_naming
from ..services.chart_handler import ChartHandler
from ..services.deep_research_handler import DeepResearchHandler
from ..utils.streaming_handlers import (
    handle_stream_end,
    handle_stream_start,
    handle_text_chunk,
    handle_thinking_chunk,
    handle_tool_result,
    handle_tool_start,
)

logger = logging.getLogger(__name__)


@dataclass
class StreamSession:
    """Minimal session object for handler compatibility."""

    session_id: str
    customer_id: int


CreateMessageFunc = Callable[..., Coroutine[Any, Any, Any]]
TTSFunc = Callable[..., Coroutine[Any, Any, Any]]
CancelTTSFunc = Callable[..., Coroutine[Any, Any, Any]]


class EventEmitter:
    """Transforms NDJSONLineParser events into proactive agent events."""

    def __init__(
        self,
        init_data: InitMessage,
        repository: ProactiveAgentRepository,
        chart_handler: ChartHandler,
        research_handler: DeepResearchHandler,
        create_message_func: CreateMessageFunc,
        start_tts_func: Optional[TTSFunc] = None,
        complete_tts_func: Optional[TTSFunc] = None,
        cancel_tts_func: Optional[CancelTTSFunc] = None,
    ) -> None:
        self.user_id = init_data.user_id
        self.session_id = init_data.session_id
        self.ai_character_name = init_data.ai_character_name
        self.tts_settings = init_data.tts_settings
        self.source = init_data.source

        self._session = StreamSession(session_id=self.session_id, customer_id=self.user_id)
        self._repository = repository
        self._chart_handler = chart_handler
        self._research_handler = research_handler
        self._create_message_func = create_message_func
        self._start_tts_func = start_tts_func or self._noop_tts
        self._complete_tts_func = complete_tts_func or self._noop_tts_complete
        self._cancel_tts_func = cancel_tts_func or self._noop_tts

        self._stream_started = False
        self._error_emitted = False

    async def emit(self, event: ParsedEvent) -> None:
        """Emit a parsed event to frontends via existing handlers."""
        # Log parse errors (don't silently drop them)
        if event.type == EventType.PARSE_ERROR:
            line = event.data.get("line", "")[:100]
            logger.warning(
                f"Unparseable NDJSON line: {line}",
                extra={"session_id": self.session_id},
            )
            return

        # Emit stream_start on first content event
        if not self._stream_started and event.type in (
            EventType.TEXT_CHUNK, EventType.THINKING_CHUNK, EventType.TOOL_START
        ):
            await self._emit_stream_start()
            self._stream_started = True

        # Route event to appropriate handler
        handler = {
            EventType.TEXT_CHUNK: self._emit_text_chunk,
            EventType.THINKING_CHUNK: self._emit_thinking_chunk,
            EventType.TOOL_START: self._emit_tool_start,
            EventType.TOOL_RESULT: self._emit_tool_result,
            EventType.CHART_DETECTED: self._handle_chart,
            EventType.RESEARCH_DETECTED: self._handle_research,
            EventType.SCENE_DETECTED: self._handle_scene,
            EventType.COMPONENT_UPDATE_DETECTED: self._handle_component_update,
            EventType.SESSION_ID: self._update_session_id,
        }.get(event.type)

        if handler:
            await handler(event.data)

    async def finalize(self, full_content: str) -> None:
        """Finalize stream and emit stream_end using fresh DB connection."""
        if not self._stream_started:
            await self._emit_stream_start()
        
        # Use fresh DB session to avoid stale connection issues
        await self._handle_stream_end_with_fresh_db(full_content)

        # M6.5: Trigger session naming on first response (prod only)
        # Use fresh session for this check too
        from features.proactive_agent.dependencies import get_db_session_direct
        from features.proactive_agent.repositories import ProactiveAgentRepository
        try:
            async with get_db_session_direct() as fresh_db:
                fresh_repo = ProactiveAgentRepository(fresh_db)
                if await should_trigger_session_naming(fresh_repo, self.session_id):
                    schedule_session_naming(self.session_id, self.user_id)
        except Exception as e:
            logger.warning("Failed to check session naming: %s", e, exc_info=True)

    async def emit_error(self, code: str, message: str) -> None:
        """Emit error, persist as message if stream started, and push to frontends."""
        if self._error_emitted:
            return
        self._error_emitted = True
        logger.error(f"Stream error: code={code} session={self.session_id}")

        try:
            await self._cancel_tts_func(
                session_id=self.session_id,
                user_id=self.user_id,
            )
        except Exception:
            logger.exception("Failed to cancel TTS session on error")

        # Push error to frontends
        registry = get_proactive_registry()
        await registry.push_to_user(
            user_id=self.user_id,
            message={
                "type": "stream_error",
                "data": {
                    "code": code,
                    "message": message,
                    "session_id": self.session_id,
                },
            },
        )

        # Persist error as message so it shows in history (use fresh DB)
        await self._handle_stream_end_with_fresh_db(f"⚠️ {message}", is_error=True)
    
    async def _handle_stream_end_with_fresh_db(
        self, full_content: str, is_error: bool = False
    ) -> None:
        """Handle stream end with a fresh DB connection to avoid stale sessions."""
        from features.proactive_agent.dependencies import get_db_session_direct
        from features.proactive_agent.repositories import ProactiveAgentRepository
        
        try:
            async with get_db_session_direct() as fresh_db:
                fresh_repo = ProactiveAgentRepository(fresh_db)
                _, message = await handle_stream_end(
                    session=self._session,
                    user_id=self.user_id,
                    full_content=full_content,
                    ai_character_name=self.ai_character_name,
                    create_message_func=fresh_repo.create_message,
                    complete_tts_func=self._noop_tts_complete if is_error else self._complete_tts_func,
                )
                try:
                    from features.chat.services.group_stream_handler import handle_group_stream_end

                    await handle_group_stream_end(
                        db=fresh_db,
                        proactive_session_id=self.session_id,
                        user_id=self.user_id,
                        ai_character_name=self.ai_character_name,
                        content=message.message if message else None,
                        chart_data=message.chart_data if message else None,
                        ai_reasoning=message.ai_reasoning if message else None,
                    )
                except Exception:
                    logger.exception("Failed to handle group stream completion")
        except Exception as e:
            logger.error("Failed to persist message with fresh DB: %s", e, exc_info=True)

    # ========== Private Methods ==========

    async def _emit_stream_start(self) -> None:
        await handle_stream_start(
            session=self._session,
            user_id=self.user_id,
            ai_character_name=self.ai_character_name,
            tts_settings=self.tts_settings,
            start_tts_func=self._start_tts_func,
        )

    async def _emit_text_chunk(self, data: dict) -> None:
        await handle_text_chunk(
            session=self._session,
            user_id=self.user_id,
            content=data.get("content"),
            ai_character_name=self.ai_character_name,
        )

    async def _emit_thinking_chunk(self, data: dict) -> None:
        await handle_thinking_chunk(
            session=self._session,
            user_id=self.user_id,
            content=data.get("content"),
            ai_character_name=self.ai_character_name,
        )

    async def _emit_tool_start(self, data: dict) -> None:
        await handle_tool_start(
            session=self._session,
            user_id=self.user_id,
            tool_name=data.get("name"),
            tool_input=data.get("input", {}),
            ai_character_name=self.ai_character_name,
        )

    async def _emit_tool_result(self, data: dict) -> None:
        await handle_tool_result(
            session=self._session,
            user_id=self.user_id,
            tool_name=data.get("name"),
            tool_input=data.get("input", {}),
            tool_result=data.get("cleaned_content", data.get("content", "")),
            ai_character_name=self.ai_character_name,
        )

    async def _handle_chart(self, data: dict) -> None:
        """Handle chart marker - delegates to special_event_handlers."""
        await handle_chart_event(
            data=data,
            user_id=self.user_id,
            session_id=self.session_id,
            ai_character_name=self.ai_character_name,
            chart_handler=self._chart_handler,
        )

    async def _handle_research(self, data: dict) -> None:
        """Handle research marker - delegates to special_event_handlers."""
        await handle_research_event(
            data=data,
            user_id=self.user_id,
            session_id=self.session_id,
            ai_character_name=self.ai_character_name,
            research_handler=self._research_handler,
        )

    async def _handle_scene(self, data: dict) -> None:
        """Handle scene marker - delegates to special_event_handlers."""
        await handle_scene_event(
            data=data,
            user_id=self.user_id,
            session_id=self.session_id,
        )

    async def _handle_component_update(self, data: dict) -> None:
        """Handle component update - delegates to special_event_handlers."""
        await handle_component_update_event(
            data=data,
            user_id=self.user_id,
            session_id=self.session_id,
        )

    async def _update_session_id(self, data: dict) -> None:
        """Update Claude session ID using a fresh DB connection.
        
        Uses a fresh DB session to avoid stale connection issues during
        long-running streams. The original repository session may become
        stale during extended Claude CLI operations.
        """
        claude_session_id = data.get("session_id")
        if claude_session_id:
            # Use fresh DB session to avoid stale connection timeouts
            from features.proactive_agent.dependencies import get_db_session_direct
            from features.proactive_agent.repositories import ProactiveAgentRepository
            
            try:
                async with get_db_session_direct() as fresh_db:
                    fresh_repo = ProactiveAgentRepository(fresh_db)
                    await fresh_repo.update_session_claude_id(
                        session_id=self.session_id, claude_session_id=claude_session_id
                    )
                logger.debug("Updated Claude session ID: %s", claude_session_id)
            except Exception as e:
                # Log but don't fail the stream - this is a non-critical update
                logger.warning("Failed to update Claude session ID: %s", e, exc_info=True)

    async def _noop_tts(self, **kwargs: Any) -> None:
        """No-op TTS start function."""
        pass

    async def _noop_tts_complete(self, **kwargs: Any) -> Optional[str]:
        """No-op TTS complete function."""
        return None


__all__ = ["EventEmitter", "StreamSession"]
