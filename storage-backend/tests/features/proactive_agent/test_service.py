"""Unit tests for ProactiveAgentService.

M4 Cleanup Note: Tests for receive_thinking and receive_streaming_chunk have
been removed as those methods were part of the legacy HTTP streaming endpoints.
The Python poller now uses WebSocket streaming via /ws/poller-stream.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from features.proactive_agent.schemas import (
    Attachment,
    AttachmentType,
    AgentNotificationRequest,
    MessageDirection,
    MessageSource,
    SendMessageRequest,
)
from features.proactive_agent.service import ProactiveAgentService

from .conftest import MockMessage, MockSession


class TestSendMessage:
    """Tests for ProactiveAgentService.send_message method."""

    @pytest.mark.asyncio
    async def test_send_message_creates_session_and_message(
        self, mock_repository: MagicMock
    ):
        """Test that sending a message creates session and stores message."""
        session = MockSession(session_id="new-session", customer_id=1)
        message = MockMessage(message_id=1, session_id="new-session")

        mock_repository.get_or_create_session = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)

        service = ProactiveAgentService(repository=mock_repository)

        request = SendMessageRequest(
            content="Hello Sherlock!",
            source=MessageSource.TEXT,
        )

        result = await service.send_message(user_id=1, request=request)

        assert result["session_id"] == "new-session"
        assert result["message_id"] == 1
        assert result["queued"] is False  # No queue service configured
        mock_repository.get_or_create_session.assert_called_once()
        mock_repository.create_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_queues_when_sqs_available(
        self, mock_repository: MagicMock, mock_queue_service: MagicMock
    ):
        """Test that message is queued when SQS service is available."""
        session = MockSession(session_id="test-session", customer_id=1)
        message = MockMessage(message_id=1)

        mock_repository.get_or_create_session = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)

        queue_result = MagicMock()
        queue_result.message_id = "sqs-message-123"
        mock_queue_service.enqueue_timestamped_payload = AsyncMock(
            return_value=queue_result
        )

        service = ProactiveAgentService(
            repository=mock_repository,
            queue_service=mock_queue_service,
        )

        tts_settings = {
            "voice": "sherlock",
            "model": "eleven_monolingual_v1",
            "tts_auto_execute": True,
        }
        attachments = [
            Attachment(type=AttachmentType.IMAGE, url="https://s3.test/photo.png", filename="photo.png"),
            Attachment(type=AttachmentType.DOCUMENT, url="https://s3.test/report.pdf", filename="report.pdf"),
        ]
        request = SendMessageRequest(
            content="Test message",
            tts_settings=tts_settings,
            attachments=attachments,
        )
        result = await service.send_message(user_id=1, request=request)

        assert result["queued"] is True
        assert result["queue_message_id"] == "sqs-message-123"
        mock_queue_service.enqueue_timestamped_payload.assert_called_once()
        payload = mock_queue_service.enqueue_timestamped_payload.call_args[0][0]
        assert payload["tts_settings"] == tts_settings
        assert payload["attachments"] == [
            {
                "type": "image",
                "url": "https://s3.test/photo.png",
                "filename": "photo.png",
                "mime_type": None,
            },
            {
                "type": "document",
                "url": "https://s3.test/report.pdf",
                "filename": "report.pdf",
                "mime_type": None,
            },
        ]

    @pytest.mark.asyncio
    async def test_send_message_with_existing_session(self, mock_repository: MagicMock):
        """Test sending message to existing session."""
        session = MockSession(
            session_id="existing-session",
            customer_id=1,
            claude_session_id="claude-123",
        )
        message = MockMessage(message_id=2)

        mock_repository.get_or_create_session = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)

        service = ProactiveAgentService(repository=mock_repository)

        request = SendMessageRequest(
            content="Follow-up message",
            session_id="existing-session",
        )

        result = await service.send_message(user_id=1, request=request)

        assert result["session_id"] == "existing-session"

    @pytest.mark.asyncio
    async def test_send_message_rotates_stale_claude_session(
        self, mock_repository: MagicMock
    ):
        """Test that stale sessions clear claude_session_id before enqueueing."""
        session = MockSession(
            session_id="stale-session",
            customer_id=1,
            claude_session_id="claude-123",
            last_update=datetime.now(UTC) - timedelta(days=8),
        )
        message = MockMessage(message_id=3)

        mock_repository.get_or_create_session = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)
        mock_repository.update_session_claude_id = AsyncMock(return_value=session)

        service = ProactiveAgentService(repository=mock_repository)
        request = SendMessageRequest(content="Rotate please", session_id="stale-session")

        await service.send_message(user_id=1, request=request)

        mock_repository.update_session_claude_id.assert_called_once_with(
            session_id="stale-session",
            claude_session_id=None,
        )
        assert session.claude_session_id is None

    @pytest.mark.asyncio
    async def test_send_message_keeps_recent_claude_session(
        self, mock_repository: MagicMock
    ):
        """Test that recent sessions keep claude_session_id."""
        session = MockSession(
            session_id="recent-session",
            customer_id=1,
            claude_session_id="claude-456",
            last_update=datetime.now(UTC) - timedelta(days=1),
        )
        message = MockMessage(message_id=4)

        mock_repository.get_or_create_session = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)

        service = ProactiveAgentService(repository=mock_repository)
        request = SendMessageRequest(content="Keep session", session_id="recent-session")

        await service.send_message(user_id=1, request=request)

        mock_repository.update_session_claude_id.assert_not_called()
        assert session.claude_session_id == "claude-456"


class TestReceiveNotification:
    """Tests for ProactiveAgentService.receive_agent_notification method."""

    @pytest.mark.asyncio
    async def test_notification_stored_in_db(
        self, mock_repository: MagicMock, mock_registry: MagicMock
    ):
        """Test that notification is always stored in DB."""
        session = MockSession(session_id="test-session", customer_id=1)
        message = MockMessage(message_id=10)

        mock_repository.get_session_by_id = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)

        service = ProactiveAgentService(repository=mock_repository)

        request = AgentNotificationRequest(
            user_id=1,
            session_id="test-session",
            content="Elementary!",
            direction=MessageDirection.AGENT_TO_USER,
        )

        with patch(
            "features.proactive_agent.utils.websocket_push.get_proactive_registry",
            return_value=mock_registry,
        ):
            result = await service.receive_agent_notification(request)

        assert result["stored"] is True
        assert result["message_id"] == 10
        mock_repository.create_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_pushed_via_websocket(
        self, mock_repository: MagicMock, mock_registry: MagicMock
    ):
        """Test that notification is pushed via WebSocket when user connected."""
        session = MockSession(session_id="test-session", customer_id=1)
        message = MockMessage(message_id=10)

        mock_repository.get_session_by_id = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)
        mock_registry.push_to_user = AsyncMock(return_value=True)

        service = ProactiveAgentService(repository=mock_repository)

        request = AgentNotificationRequest(
            user_id=1,
            session_id="test-session",
            content="Watson, come here!",
        )

        with patch(
            "features.proactive_agent.utils.websocket_push.get_proactive_registry",
            return_value=mock_registry,
        ):
            result = await service.receive_agent_notification(request)

        assert result["pushed_via_ws"] is True
        mock_registry.push_to_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_ok_not_pushed(
        self, mock_repository: MagicMock, mock_registry: MagicMock
    ):
        """Test that HEARTBEAT_OK messages are not pushed via WebSocket."""
        session = MockSession(session_id="test-session", customer_id=1)
        message = MockMessage(message_id=10)

        mock_repository.get_session_by_id = AsyncMock(return_value=session)
        mock_repository.create_message = AsyncMock(return_value=message)

        service = ProactiveAgentService(repository=mock_repository)

        request = AgentNotificationRequest(
            user_id=1,
            session_id="test-session",
            content="HEARTBEAT_OK",
            is_heartbeat_ok=True,
        )

        with patch(
            "features.proactive_agent.utils.websocket_push.get_proactive_registry",
            return_value=mock_registry,
        ):
            result = await service.receive_agent_notification(request)

        assert result["stored"] is True
        assert result["pushed_via_ws"] is False
        mock_registry.push_to_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_notification_session_not_found(self, mock_repository: MagicMock):
        """Test that NotFoundError is raised for non-existent session."""
        from core.exceptions import NotFoundError

        mock_repository.get_session_by_id = AsyncMock(return_value=None)

        service = ProactiveAgentService(repository=mock_repository)

        request = AgentNotificationRequest(
            user_id=1,
            session_id="nonexistent",
            content="Test",
        )

        with pytest.raises(NotFoundError):
            await service.receive_agent_notification(request)


class TestGetMessages:
    """Tests for ProactiveAgentService.get_messages method."""

    @pytest.mark.asyncio
    async def test_get_messages_returns_messages(self, mock_repository: MagicMock):
        """Test getting messages for a session."""
        session = MockSession(session_id="test-session", customer_id=1)
        messages = [
            MockMessage(message_id=1, message="Hello"),
            MockMessage(message_id=2, message="Hi there!"),
        ]

        mock_repository.get_session_by_id = AsyncMock(return_value=session)
        mock_repository.get_messages_for_session = AsyncMock(
            return_value=(messages, 2)
        )

        service = ProactiveAgentService(repository=mock_repository)

        result = await service.get_messages(
            session_id="test-session",
            user_id=1,
            limit=50,
        )

        assert len(result["messages"]) == 2
        assert result["total"] == 2
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_messages_unauthorized_user(self, mock_repository: MagicMock):
        """Test that user cannot access another user's session."""
        from core.exceptions import NotFoundError

        session = MockSession(session_id="test-session", customer_id=1)
        mock_repository.get_session_by_id = AsyncMock(return_value=session)

        service = ProactiveAgentService(repository=mock_repository)

        # User 2 trying to access user 1's session
        with pytest.raises(NotFoundError):
            await service.get_messages(
                session_id="test-session",
                user_id=2,
            )
