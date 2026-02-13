"""Tests for EventEmitter - bridges NDJSON parser to proactive handlers."""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from features.proactive_agent.poller_stream.event_emitter import EventEmitter, StreamSession
from features.proactive_agent.poller_stream.ndjson_parser import EventType, ParsedEvent
from features.proactive_agent.poller_stream.schemas import InitMessage


@pytest.fixture
def init_data():
    """Create test init data."""
    return InitMessage(
        type="init",
        user_id=1,
        session_id="test-session",
        ai_character_name="sherlock",
        source="text",
        tts_settings={"voice": "sherlock"},
    )


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return AsyncMock()


@pytest.fixture
def mock_chart_handler():
    """Create mock chart handler."""
    return AsyncMock()


@pytest.fixture
def mock_research_handler():
    """Create mock research handler."""
    return AsyncMock()


@pytest.fixture
def mock_create_message():
    """Create mock create_message function."""
    return AsyncMock()


@pytest.fixture
def emitter(init_data, mock_repository, mock_chart_handler, mock_research_handler, mock_create_message):
    """Create EventEmitter with mocked dependencies."""
    return EventEmitter(
        init_data=init_data,
        repository=mock_repository,
        chart_handler=mock_chart_handler,
        research_handler=mock_research_handler,
        create_message_func=mock_create_message,
    )


class TestStreamSession:
    """Tests for StreamSession dataclass."""

    def test_stream_session_attributes(self):
        """StreamSession has required attributes."""
        session = StreamSession(session_id="test-123", customer_id=42)
        assert session.session_id == "test-123"
        assert session.customer_id == 42


class TestEventEmitterInit:
    """Tests for EventEmitter initialization."""

    def test_init_sets_attributes(self, init_data, mock_repository, mock_chart_handler, mock_research_handler, mock_create_message):
        """EventEmitter stores init data correctly."""
        emitter = EventEmitter(
            init_data=init_data,
            repository=mock_repository,
            chart_handler=mock_chart_handler,
            research_handler=mock_research_handler,
            create_message_func=mock_create_message,
        )
        assert emitter.user_id == 1
        assert emitter.session_id == "test-session"
        assert emitter.ai_character_name == "sherlock"
        assert emitter.source == "text"
        assert not emitter._stream_started


class TestStreamStartEmission:
    """Tests for stream_start emission."""

    @pytest.mark.asyncio
    async def test_stream_start_on_first_text_chunk(self, emitter):
        """stream_start emitted on first text_chunk."""
        with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_start") as mock_start:
            await emitter.emit(ParsedEvent(
                type=EventType.TEXT_CHUNK,
                data={"content": "Hello"}
            ))
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_start_on_first_thinking_chunk(self, emitter):
        """stream_start emitted on first thinking_chunk."""
        with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_start") as mock_start:
            await emitter.emit(ParsedEvent(
                type=EventType.THINKING_CHUNK,
                data={"content": "Hmm..."}
            ))
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_start_on_first_tool_start(self, emitter):
        """stream_start emitted on first tool_start."""
        with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_start") as mock_start:
            with patch("features.proactive_agent.poller_stream.event_emitter.handle_tool_start"):
                await emitter.emit(ParsedEvent(
                    type=EventType.TOOL_START,
                    data={"name": "Bash", "input": {}, "tool_use_id": "123"}
                ))
                mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_start_only_once(self, emitter):
        """stream_start only emitted once across multiple events."""
        with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_start") as mock_start:
            with patch("features.proactive_agent.poller_stream.event_emitter.handle_text_chunk"):
                await emitter.emit(ParsedEvent(type=EventType.TEXT_CHUNK, data={"content": "a"}))
                await emitter.emit(ParsedEvent(type=EventType.TEXT_CHUNK, data={"content": "b"}))
                await emitter.emit(ParsedEvent(type=EventType.TEXT_CHUNK, data={"content": "c"}))
                assert mock_start.call_count == 1


class TestChunkEmission:
    """Tests for chunk event emission."""

    @pytest.mark.asyncio
    async def test_text_chunk_calls_handler(self, emitter):
        """text_chunk event calls handle_text_chunk."""
        emitter._stream_started = True  # Skip stream_start

        with patch("features.proactive_agent.poller_stream.event_emitter.handle_text_chunk") as mock_handler:
            await emitter.emit(ParsedEvent(
                type=EventType.TEXT_CHUNK,
                data={"content": "Hello world"}
            ))
            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["content"] == "Hello world"
            assert call_kwargs["user_id"] == 1

    @pytest.mark.asyncio
    async def test_thinking_chunk_calls_handler(self, emitter):
        """thinking_chunk event calls handle_thinking_chunk."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.event_emitter.handle_thinking_chunk") as mock_handler:
            await emitter.emit(ParsedEvent(
                type=EventType.THINKING_CHUNK,
                data={"content": "Let me think..."}
            ))
            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["content"] == "Let me think..."


class TestToolEmission:
    """Tests for tool event emission."""

    @pytest.mark.asyncio
    async def test_tool_start_calls_handler(self, emitter):
        """tool_start event calls handle_tool_start."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.event_emitter.handle_tool_start") as mock_handler:
            await emitter.emit(ParsedEvent(
                type=EventType.TOOL_START,
                data={"name": "Bash", "input": {"command": "ls"}, "tool_use_id": "123"}
            ))
            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["tool_name"] == "Bash"
            assert call_kwargs["tool_input"] == {"command": "ls"}

    @pytest.mark.asyncio
    async def test_tool_result_calls_handler(self, emitter):
        """tool_result event calls handle_tool_result."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.event_emitter.handle_tool_result") as mock_handler:
            await emitter.emit(ParsedEvent(
                type=EventType.TOOL_RESULT,
                data={
                    "name": "Bash",
                    "input": {"command": "ls"},
                    "content": "file1.txt\nfile2.txt",
                    "cleaned_content": "file1.txt\nfile2.txt",
                    "tool_use_id": "123",
                }
            ))
            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["tool_name"] == "Bash"
            assert call_kwargs["tool_result"] == "file1.txt\nfile2.txt"


class TestComponentUpdateHandling:
    """Tests for component update event handling."""

    @pytest.mark.asyncio
    async def test_component_update_pushes_to_registry(self, emitter):
        """COMPONENT_UPDATE_DETECTED pushes to WebSocket registry."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.special_event_handlers.get_proactive_registry") as mock_get_registry:
            mock_registry = AsyncMock()
            mock_get_registry.return_value = mock_registry

            await emitter.emit(ParsedEvent(
                type=EventType.COMPONENT_UPDATE_DETECTED,
                data={
                    "update_data": {
                        "component_id": "answer",
                        "content": "Hello world",
                        "append": True
                    }
                }
            ))

            mock_registry.push_to_user.assert_called_once()
            call_kwargs = mock_registry.push_to_user.call_args.kwargs
            assert call_kwargs["user_id"] == 1
            message = call_kwargs["message"]
            assert message["type"] == "component_update"
            assert message["session_id"] == "test-session"
            assert message["component_id"] == "answer"
            assert message["content"] == "Hello world"
            assert message["append"] is True

    @pytest.mark.asyncio
    async def test_component_update_skips_missing_component_id(self, emitter, caplog):
        """Component update without component_id is skipped."""
        emitter._stream_started = True

        import logging
        with caplog.at_level(logging.WARNING):
            with patch("features.proactive_agent.poller_stream.special_event_handlers.get_proactive_registry") as mock_get_registry:
                mock_registry = AsyncMock()
                mock_get_registry.return_value = mock_registry

                await emitter.emit(ParsedEvent(
                    type=EventType.COMPONENT_UPDATE_DETECTED,
                    data={"update_data": {"content": "Hello"}}  # Missing component_id
                ))

                mock_registry.push_to_user.assert_not_called()
                assert "missing component_id" in caplog.text

    @pytest.mark.asyncio
    async def test_component_update_skips_missing_content(self, emitter, caplog):
        """Component update without content is skipped."""
        emitter._stream_started = True

        import logging
        with caplog.at_level(logging.WARNING):
            with patch("features.proactive_agent.poller_stream.special_event_handlers.get_proactive_registry") as mock_get_registry:
                mock_registry = AsyncMock()
                mock_get_registry.return_value = mock_registry

                await emitter.emit(ParsedEvent(
                    type=EventType.COMPONENT_UPDATE_DETECTED,
                    data={"update_data": {"component_id": "answer"}}  # Missing content
                ))

                mock_registry.push_to_user.assert_not_called()
                assert "missing content" in caplog.text

    @pytest.mark.asyncio
    async def test_component_update_defaults_append_to_false(self, emitter):
        """Component update defaults append to False if not specified."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.special_event_handlers.get_proactive_registry") as mock_get_registry:
            mock_registry = AsyncMock()
            mock_get_registry.return_value = mock_registry

            await emitter.emit(ParsedEvent(
                type=EventType.COMPONENT_UPDATE_DETECTED,
                data={
                    "update_data": {
                        "component_id": "status",
                        "content": "Complete"
                        # No append field
                    }
                }
            ))

            call_kwargs = mock_registry.push_to_user.call_args.kwargs
            message = call_kwargs["message"]
            assert message["append"] is False


class TestSceneHandling:
    """Tests for scene event handling."""

    @pytest.mark.asyncio
    async def test_scene_detected_pushes_to_registry(self, emitter):
        """SCENE_DETECTED pushes scene event to WebSocket registry."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.special_event_handlers.get_proactive_registry") as mock_get_registry:
            mock_registry = AsyncMock()
            mock_get_registry.return_value = mock_registry

            await emitter.emit(ParsedEvent(
                type=EventType.SCENE_DETECTED,
                data={
                    "scene_data": {
                        "scene_id": "test-scene",
                        "components": [{"type": "text", "id": "t1", "content": "Hello"}]
                    },
                    "raw_json": "{}",
                }
            ))

            mock_registry.push_to_user.assert_called_once()
            call_kwargs = mock_registry.push_to_user.call_args.kwargs
            assert call_kwargs["user_id"] == 1
            message = call_kwargs["message"]
            assert message["type"] == "scene"
            assert message["session_id"] == "test-session"
            assert message["content"]["scene_id"] == "test-scene"
            assert len(message["content"]["components"]) == 1

    @pytest.mark.asyncio
    async def test_scene_skips_missing_scene_id(self, emitter, caplog):
        """Scene without scene_id is skipped with warning."""
        emitter._stream_started = True

        import logging
        with caplog.at_level(logging.WARNING):
            with patch("features.proactive_agent.poller_stream.special_event_handlers.get_proactive_registry") as mock_get_registry:
                mock_registry = AsyncMock()
                mock_get_registry.return_value = mock_registry

                await emitter.emit(ParsedEvent(
                    type=EventType.SCENE_DETECTED,
                    data={
                        "scene_data": {
                            "components": [{"type": "text", "id": "t1", "content": "Hello"}]
                        },
                    }
                ))

                mock_registry.push_to_user.assert_not_called()
                assert "missing scene_id" in caplog.text

    @pytest.mark.asyncio
    async def test_scene_skips_missing_components(self, emitter, caplog):
        """Scene without components is skipped with warning."""
        emitter._stream_started = True

        import logging
        with caplog.at_level(logging.WARNING):
            with patch("features.proactive_agent.poller_stream.special_event_handlers.get_proactive_registry") as mock_get_registry:
                mock_registry = AsyncMock()
                mock_get_registry.return_value = mock_registry

                await emitter.emit(ParsedEvent(
                    type=EventType.SCENE_DETECTED,
                    data={
                        "scene_data": {
                            "scene_id": "test-scene"
                        },
                    }
                ))

                mock_registry.push_to_user.assert_not_called()
                assert "missing components" in caplog.text

    @pytest.mark.asyncio
    async def test_scene_with_complex_data(self, emitter):
        """Scene with timeline and grid layout is pushed correctly."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.special_event_handlers.get_proactive_registry") as mock_get_registry:
            mock_registry = AsyncMock()
            mock_get_registry.return_value = mock_registry

            scene_data = {
                "scene_id": "complex-scene",
                "layout": "grid",
                "grid": {"columns": 2, "rows": 2},
                "timeline": {
                    "master": "audio-1",
                    "cues": [{"at": 0, "show": ["intro"]}]
                },
                "components": [
                    {"type": "text", "id": "intro", "content": "Welcome"},
                    {"type": "audio_chunk", "id": "audio-1", "src": "tts://auto"}
                ]
            }

            await emitter.emit(ParsedEvent(
                type=EventType.SCENE_DETECTED,
                data={"scene_data": scene_data}
            ))

            call_kwargs = mock_registry.push_to_user.call_args.kwargs
            message = call_kwargs["message"]
            assert message["content"]["layout"] == "grid"
            assert message["content"]["timeline"]["master"] == "audio-1"
            assert len(message["content"]["components"]) == 2


class TestMarkerHandling:
    """Tests for chart and research marker handling."""

    @pytest.mark.asyncio
    async def test_chart_detected_triggers_handler(self, emitter, mock_chart_handler):
        """CHART_DETECTED triggers chart handler."""
        emitter._stream_started = True

        await emitter.emit(ParsedEvent(
            type=EventType.CHART_DETECTED,
            data={
                "chart_data": {
                    "chart_type": "line",
                    "title": "Test Chart",
                    "data": {
                        "labels": ["A", "B"],
                        "datasets": [{"label": "Series 1", "data": [1, 2]}],
                    },
                },
                "raw_json": "{}",
            }
        ))
        mock_chart_handler.generate_chart.assert_called_once()

    @pytest.mark.asyncio
    async def test_chart_preserves_all_fields(self, emitter, mock_chart_handler):
        """M6.4 Bug Fix: All chart marker fields should reach ChartGenerationRequest.

        Previously, chart_id, subtitle, data_query, mermaid_code, and options
        were dropped when creating ChartGenerationRequest. This test verifies
        all fields are now passed through.
        """
        emitter._stream_started = True

        await emitter.emit(ParsedEvent(
            type=EventType.CHART_DETECTED,
            data={
                "chart_data": {
                    "chart_type": "mermaid",
                    "title": "Flow Diagram",
                    "subtitle": "Process overview",
                    "chart_id": "inline_flow_123",
                    "mermaid_code": "graph TD; A-->B;",
                    "options": {"interactive": False, "show_legend": False},
                },
                "raw_json": "{}",
            }
        ))

        mock_chart_handler.generate_chart.assert_called_once()
        request = mock_chart_handler.generate_chart.call_args[0][0]

        # Core fields
        assert request.chart_type == "mermaid"
        assert request.title == "Flow Diagram"

        # Previously dropped fields (M6.4 fix)
        assert request.subtitle == "Process overview"
        assert request.chart_id == "inline_flow_123"
        assert request.mermaid_code == "graph TD; A-->B;"
        # Options get parsed into ChartOptions model
        assert request.options is not None
        assert request.options.interactive is False
        assert request.options.show_legend is False

    @pytest.mark.asyncio
    async def test_chart_with_data_query(self, emitter, mock_chart_handler):
        """Chart with data_query field is passed through."""
        emitter._stream_started = True

        await emitter.emit(ParsedEvent(
            type=EventType.CHART_DETECTED,
            data={
                "chart_data": {
                    "chart_type": "line",
                    "title": "Heart Rate Trend",
                    "data_query": {
                        "source": "garmin_db",
                        "metric": "resting_heart_rate",
                        "time_range": {"last_n_days": 7},
                    },
                },
                "raw_json": "{}",
            }
        ))

        mock_chart_handler.generate_chart.assert_called_once()
        request = mock_chart_handler.generate_chart.call_args[0][0]
        # data_query gets parsed into DataQuery model
        assert request.data_query is not None
        assert request.data_query.metric == "resting_heart_rate"
        assert request.data_query.time_range.last_n_days == 7

    @pytest.mark.asyncio
    async def test_malformed_chart_marker_does_not_crash_stream(self, emitter, mock_chart_handler, caplog):
        """Robustness fix: Malformed chart markers are logged and skipped, not crash the stream.

        ChartGenerationRequest requires exactly one of: data, data_query, or mermaid_code.
        If Claude outputs a malformed marker (e.g., none of these), Pydantic validation
        would raise ValueError. The stream should continue, not crash.
        """
        emitter._stream_started = True

        import logging
        with caplog.at_level(logging.WARNING):
            # Invalid: missing all data sources (data, data_query, mermaid_code)
            await emitter.emit(ParsedEvent(
                type=EventType.CHART_DETECTED,
                data={
                    "chart_data": {
                        "chart_type": "line",
                        "title": "Invalid Chart",
                        # No data, data_query, or mermaid_code!
                    },
                    "raw_json": "{}",
                }
            ))

        # Should NOT have called chart handler (validation failed)
        mock_chart_handler.generate_chart.assert_not_called()
        # Should have logged a warning
        assert "Skipping invalid chart marker" in caplog.text

    @pytest.mark.asyncio
    async def test_research_detected_triggers_handler(self, emitter, mock_research_handler):
        """RESEARCH_DETECTED triggers research handler."""
        emitter._stream_started = True

        await emitter.emit(ParsedEvent(
            type=EventType.RESEARCH_DETECTED,
            data={
                "research_data": {"query": "What is quantum computing?"},
                "raw_json": "{}",
            }
        ))
        mock_research_handler.execute_research.assert_called_once()


class TestSessionIdUpdate:
    """Tests for session ID update."""

    @pytest.mark.asyncio
    async def test_session_id_updates_repository(self, emitter, mock_repository):
        """SESSION_ID event updates repository via fresh DB session."""
        mock_db = AsyncMock()

        @asynccontextmanager
        async def mock_get_db():
            yield mock_db

        with patch(
            "features.proactive_agent.dependencies.get_db_session_direct",
            mock_get_db,
        ), patch(
            "features.proactive_agent.repositories.ProactiveAgentRepository",
            return_value=mock_repository,
        ):
            await emitter.emit(ParsedEvent(
                type=EventType.SESSION_ID,
                data={"session_id": "claude-session-abc123"}
            ))

        mock_repository.update_session_claude_id.assert_called_once_with(
            session_id="test-session",
            claude_session_id="claude-session-abc123"
        )


class TestFinalize:
    """Tests for finalize method."""

    @pytest.mark.asyncio
    async def test_finalize_calls_stream_end(self, emitter):
        """finalize() calls handle_stream_end."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_end") as mock_end:
            with patch("features.proactive_agent.poller_stream.event_emitter.should_trigger_session_naming", new_callable=AsyncMock, return_value=False):
                await emitter.finalize("Final text content")
                mock_end.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_emits_stream_start_if_not_started(self, emitter):
        """finalize() emits stream_start if not already emitted."""
        assert not emitter._stream_started

        with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_start") as mock_start:
            with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_end"):
                with patch("features.proactive_agent.poller_stream.event_emitter.should_trigger_session_naming", new_callable=AsyncMock, return_value=False):
                    await emitter.finalize("Content")
                    mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_triggers_session_naming_in_prod(self, emitter):
        """M6.5: finalize() triggers session naming when conditions are met."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_end"):
            with patch("features.proactive_agent.poller_stream.event_emitter.should_trigger_session_naming", new_callable=AsyncMock, return_value=True) as mock_should:
                with patch("features.proactive_agent.poller_stream.event_emitter.schedule_session_naming") as mock_schedule:
                    await emitter.finalize("Content")

                    mock_should.assert_called_once()
                    mock_schedule.assert_called_once_with("test-session", 1)

    @pytest.mark.asyncio
    async def test_finalize_skips_session_naming_when_not_needed(self, emitter):
        """M6.5: finalize() skips session naming when should_trigger returns False."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_end"):
            with patch("features.proactive_agent.poller_stream.event_emitter.should_trigger_session_naming", new_callable=AsyncMock, return_value=False):
                with patch("features.proactive_agent.poller_stream.event_emitter.schedule_session_naming") as mock_schedule:
                    await emitter.finalize("Content")

                    mock_schedule.assert_not_called()


class TestEmitError:
    """Tests for error emission."""

    @pytest.mark.asyncio
    async def test_emit_error_pushes_to_registry(self, emitter):
        """emit_error pushes error event to registry."""
        with patch("features.proactive_agent.poller_stream.event_emitter.get_proactive_registry") as mock_get_registry:
            mock_registry = AsyncMock()
            mock_get_registry.return_value = mock_registry

            await emitter.emit_error("rate_limit", "Too many requests")

            mock_registry.push_to_user.assert_called_once()
            call_kwargs = mock_registry.push_to_user.call_args.kwargs
            assert call_kwargs["user_id"] == 1
            assert call_kwargs["message"]["type"] == "stream_error"
            assert call_kwargs["message"]["data"]["code"] == "rate_limit"
            assert call_kwargs["message"]["data"]["message"] == "Too many requests"
            assert call_kwargs["message"]["data"]["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_emit_error_persists_if_stream_started(self, emitter):
        """emit_error persists error message if stream was started."""
        emitter._stream_started = True

        with patch("features.proactive_agent.poller_stream.event_emitter.get_proactive_registry") as mock_get_registry:
            with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_end") as mock_end:
                mock_registry = AsyncMock()
                mock_get_registry.return_value = mock_registry

                await emitter.emit_error("rate_limit", "Too many requests")

                # Should persist error message
                mock_end.assert_called_once()
                call_kwargs = mock_end.call_args.kwargs
                assert "⚠️" in call_kwargs["full_content"]
                assert "Too many requests" in call_kwargs["full_content"]

    @pytest.mark.asyncio
    async def test_emit_error_persists_if_stream_not_started(self, emitter):
        """emit_error persists even if stream was not started."""
        assert not emitter._stream_started

        with patch("features.proactive_agent.poller_stream.event_emitter.get_proactive_registry") as mock_get_registry:
            with patch("features.proactive_agent.poller_stream.event_emitter.handle_stream_end") as mock_end:
                mock_registry = AsyncMock()
                mock_get_registry.return_value = mock_registry

                await emitter.emit_error("rate_limit", "Too many requests")

                mock_end.assert_called_once()


class TestUnhandledEvents:
    """Tests for events that don't have explicit handlers."""

    @pytest.mark.asyncio
    async def test_parse_error_is_logged_not_silent(self, emitter, caplog):
        """PARSE_ERROR events are logged (not silently dropped).

        Security fix: Unparseable NDJSON lines should be logged for debugging,
        not silently ignored.
        """
        emitter._stream_started = True

        import logging
        with caplog.at_level(logging.WARNING):
            await emitter.emit(ParsedEvent(
                type=EventType.PARSE_ERROR,
                data={"line": "this is not valid json {{{"}
            ))

        # Should be logged as warning
        assert "Unparseable NDJSON line" in caplog.text
        assert "this is not valid json" in caplog.text

    @pytest.mark.asyncio
    async def test_message_stop_is_silently_ignored(self, emitter):
        """MESSAGE_STOP events are ignored (handled at stream level)."""
        emitter._stream_started = True
        # Should not raise
        await emitter.emit(ParsedEvent(
            type=EventType.MESSAGE_STOP,
            data={}
        ))

    @pytest.mark.asyncio
    async def test_stream_complete_is_silently_ignored(self, emitter):
        """STREAM_COMPLETE events are ignored (handled at stream level)."""
        emitter._stream_started = True
        # Should not raise
        await emitter.emit(ParsedEvent(
            type=EventType.STREAM_COMPLETE,
            data={}
        ))
