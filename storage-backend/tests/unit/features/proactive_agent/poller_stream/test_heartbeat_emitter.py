"""Tests for HeartbeatEmitter - heartbeat-specific NDJSON handling.

Tests cover:
- Silent accumulation (no frontend push)
- HEARTBEAT_OK detection on clean text
- Notification sending for observations
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from features.proactive_agent.poller_stream.heartbeat_emitter import HeartbeatEmitter
from features.proactive_agent.poller_stream.ndjson_parser import EventType, ParsedEvent
from features.proactive_agent.poller_stream.schemas import InitMessage


@pytest.fixture
def init_data():
    """Create test init data for heartbeat mode."""
    return InitMessage(
        type="init",
        user_id=1,
        session_id="test-session-123",
        ai_character_name="sherlock",
        source="heartbeat",
        tts_settings=None,
    )


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    repo = AsyncMock()
    repo.get_session_by_id = AsyncMock(return_value=MagicMock(
        session_id="test-session-123",
        customer_id=1,
    ))
    return repo


@pytest.fixture
def emitter(init_data, mock_repository):
    """Create HeartbeatEmitter with mocked dependencies."""
    return HeartbeatEmitter(
        init_data=init_data,
        repository=mock_repository,
    )


class TestHeartbeatEmitterInit:
    """Tests for HeartbeatEmitter initialization."""

    def test_init_sets_attributes(self, init_data, mock_repository):
        """HeartbeatEmitter stores init data correctly."""
        emitter = HeartbeatEmitter(
            init_data=init_data,
            repository=mock_repository,
        )
        assert emitter.user_id == 1
        assert emitter.session_id == "test-session-123"
        assert emitter.ai_character_name == "sherlock"
        assert emitter._accumulated_text == ""
        assert not emitter._error_emitted


class TestHeartbeatEmitterEmit:
    """Tests for emit method - silent accumulation."""

    @pytest.mark.asyncio
    async def test_emit_accumulates_text_chunks(self, emitter):
        """Text chunks are accumulated silently."""
        await emitter.emit(ParsedEvent(
            type=EventType.TEXT_CHUNK,
            data={"content": "Hello "}
        ))
        await emitter.emit(ParsedEvent(
            type=EventType.TEXT_CHUNK,
            data={"content": "world"}
        ))

        assert emitter._accumulated_text == "Hello world"

    @pytest.mark.asyncio
    async def test_emit_ignores_thinking_chunks(self, emitter):
        """Thinking chunks don't affect accumulated text."""
        await emitter.emit(ParsedEvent(
            type=EventType.THINKING_CHUNK,
            data={"content": "Let me think..."}
        ))

        assert emitter._accumulated_text == ""

    @pytest.mark.asyncio
    async def test_emit_ignores_tool_events(self, emitter):
        """Tool events don't affect accumulated text."""
        await emitter.emit(ParsedEvent(
            type=EventType.TOOL_START,
            data={"name": "Read", "input": {}}
        ))
        await emitter.emit(ParsedEvent(
            type=EventType.TOOL_RESULT,
            data={"name": "Read", "content": "file contents"}
        ))

        assert emitter._accumulated_text == ""

    @pytest.mark.asyncio
    async def test_emit_logs_parse_errors(self, emitter):
        """Parse errors are logged but don't fail."""
        # Should not raise
        await emitter.emit(ParsedEvent(
            type=EventType.PARSE_ERROR,
            data={"line": "invalid json"}
        ))

        assert emitter._accumulated_text == ""


class TestHeartbeatEmitterFinalize:
    """Tests for finalize method - HEARTBEAT_OK detection."""

    @pytest.mark.asyncio
    async def test_finalize_detects_heartbeat_ok(self, emitter):
        """HEARTBEAT_OK in clean text skips notification."""
        with patch.object(emitter, "_send_notification") as mock_notify:
            await emitter.finalize("HEARTBEAT_OK - All quiet")

            mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_finalize_detects_heartbeat_ok_case_insensitive(self, emitter):
        """HEARTBEAT_OK detection is case insensitive."""
        with patch.object(emitter, "_send_notification") as mock_notify:
            await emitter.finalize("heartbeat_ok - nothing to report")

            mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_finalize_sends_notification_for_observation(self, emitter):
        """Non-HEARTBEAT_OK content triggers notification."""
        with patch.object(emitter, "_send_notification") as mock_notify:
            mock_notify.return_value = None

            await emitter.finalize("I found something interesting!")

            mock_notify.assert_called_once_with("I found something interesting!")

    @pytest.mark.asyncio
    async def test_finalize_checks_clean_text_not_full(self, emitter):
        """HEARTBEAT_OK in thinking tags doesn't skip notification.

        If thinking contains HEARTBEAT_OK but actual response is observation,
        we should still send notification. This tests the "check on clean_text"
        behavior.
        """
        with patch.object(emitter, "_send_notification") as mock_notify:
            mock_notify.return_value = None

            # Full content has HEARTBEAT_OK in thinking but actual response is observation
            full_content = "<thinking>HEARTBEAT_OK - all quiet</thinking>Actually I noticed high CPU usage!"

            await emitter.finalize(full_content)

            # Should send notification because clean text doesn't have HEARTBEAT_OK
            mock_notify.assert_called_once_with(full_content)

    @pytest.mark.asyncio
    async def test_finalize_no_notification_when_ok_in_clean_text(self, emitter):
        """HEARTBEAT_OK in clean text (not just thinking) skips notification."""
        with patch.object(emitter, "_send_notification") as mock_notify:
            # Full content has HEARTBEAT_OK outside thinking tags
            full_content = "<thinking>Let me check...</thinking>HEARTBEAT_OK - nothing to report"

            await emitter.finalize(full_content)

            mock_notify.assert_not_called()


class TestHeartbeatEmitterSendNotification:
    """Tests for _send_notification method."""

    @pytest.mark.asyncio
    async def test_send_notification_calls_message_handler(self, emitter):
        """Notification uses MessageHandler.receive_agent_notification."""
        with patch.object(
            emitter._message_handler, "receive_agent_notification"
        ) as mock_receive:
            mock_receive.return_value = {
                "message_id": "msg-123",
                "session_id": "test-session-123",
                "pushed_via_ws": True,
            }

            await emitter._send_notification("I found an issue!")

            mock_receive.assert_called_once()
            call_args = mock_receive.call_args[0][0]

            # Verify request structure
            assert call_args.user_id == 1
            assert call_args.session_id == "test-session-123"
            assert call_args.content == "I found an issue!"
            assert call_args.is_heartbeat_ok is False
            assert call_args.ai_character_name == "sherlock"

    @pytest.mark.asyncio
    async def test_send_notification_handles_errors_gracefully(self, emitter):
        """Notification errors are logged but don't raise."""
        with patch.object(
            emitter._message_handler, "receive_agent_notification"
        ) as mock_receive:
            mock_receive.side_effect = Exception("DB connection failed")

            # Should not raise
            await emitter._send_notification("Test content")


class TestHeartbeatEmitterError:
    """Tests for emit_error method."""

    @pytest.mark.asyncio
    async def test_emit_error_logs_once(self, emitter):
        """Error is logged but only once."""
        await emitter.emit_error("test_error", "Something went wrong")

        assert emitter._error_emitted is True

        # Second call should be no-op
        await emitter.emit_error("another_error", "This shouldn't log")

        # Still true, no exception
        assert emitter._error_emitted is True

    @pytest.mark.asyncio
    async def test_emit_error_does_not_persist(self, emitter, mock_repository):
        """Heartbeat errors don't create DB records."""
        await emitter.emit_error("sdk_error", "SDK daemon unavailable")

        # Repository should not be called to create a message
        mock_repository.create_message.assert_not_called()


class TestHeartbeatOkDetection:
    """Tests for _is_heartbeat_ok helper."""

    def test_is_heartbeat_ok_true(self, emitter):
        """Detects HEARTBEAT_OK in text."""
        assert emitter._is_heartbeat_ok("HEARTBEAT_OK - all quiet") is True
        assert emitter._is_heartbeat_ok("heartbeat_ok nothing to report") is True
        assert emitter._is_heartbeat_ok("Response: HEARTBEAT_OK") is True

    def test_is_heartbeat_ok_false(self, emitter):
        """Returns False when HEARTBEAT_OK not present."""
        assert emitter._is_heartbeat_ok("I found an issue") is False
        assert emitter._is_heartbeat_ok("Disk usage is high") is False
        assert emitter._is_heartbeat_ok("") is False
