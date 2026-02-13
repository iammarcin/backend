"""Unit tests for proactive agent schemas.

M4 Cleanup Note: Tests for ThinkingRequest, StreamingChunkRequest, and
StreamingEventType have been removed as they were for legacy HTTP streaming
endpoints. The schema definitions remain in request.py for reference but are
no longer exported from the schemas package.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from features.proactive_agent.schemas import (
    Attachment,
    AttachmentType,
    AgentNotificationRequest,
    MessageDirection,
    MessageSource,
    SendMessageRequest,
)


class TestMessageSource:
    """Tests for MessageSource enum."""

    def test_valid_sources(self):
        """Test all valid message sources."""
        assert MessageSource.TEXT == "text"
        assert MessageSource.AUDIO_TRANSCRIPTION == "audio_transcription"
        assert MessageSource.HEARTBEAT == "heartbeat"

    def test_enum_values_count(self):
        """Verify expected number of source types."""
        assert len(MessageSource) == 3


class TestMessageDirection:
    """Tests for MessageDirection enum."""

    def test_valid_directions(self):
        """Test all valid message directions."""
        assert MessageDirection.USER_TO_AGENT == "user_to_agent"
        assert MessageDirection.AGENT_TO_USER == "agent_to_user"
        assert MessageDirection.HEARTBEAT == "heartbeat"


class TestSendMessageRequest:
    """Tests for SendMessageRequest schema."""

    def test_valid_minimal_request(self):
        """Test request with only required field."""
        request = SendMessageRequest(content="Hello Sherlock!")
        assert request.content == "Hello Sherlock!"
        assert request.source == MessageSource.TEXT
        assert request.ai_character_name == "sherlock"
        assert request.session_id is None

    def test_valid_full_request(self):
        """Test request with all fields."""
        request = SendMessageRequest(
            content="Test message",
            session_id="abc-123",
            source=MessageSource.AUDIO_TRANSCRIPTION,
            ai_character_name="bugsy",
            tts_settings={
                "voice": "sherlock",
                "model": "eleven_monolingual_v1",
                "tts_auto_execute": True,
            },
        )
        assert request.content == "Test message"
        assert request.session_id == "abc-123"
        assert request.source == MessageSource.AUDIO_TRANSCRIPTION
        assert request.ai_character_name == "bugsy"
        assert request.tts_settings is not None

    def test_empty_content_rejected(self):
        """Test that empty content is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(content="")
        assert "string_too_short" in str(exc_info.value).lower()

    def test_content_max_length(self):
        """Test content max length validation."""
        long_content = "x" * 30001
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(content=long_content)
        assert "string_too_long" in str(exc_info.value).lower()

    def test_content_at_max_length(self):
        """Test content exactly at max length is accepted."""
        max_content = "x" * 30000
        request = SendMessageRequest(content=max_content)
        assert len(request.content) == 30000

    def test_valid_attachments(self):
        """Test attachments are accepted and parsed."""
        attachments = [
            Attachment(type=AttachmentType.IMAGE, url="https://s3.test/image.png", filename="image.png"),
            Attachment(type=AttachmentType.DOCUMENT, url="https://s3.test/doc.pdf", filename="doc.pdf"),
        ]
        request = SendMessageRequest(content="With files", attachments=attachments)
        assert request.attachments is not None
        assert len(request.attachments) == 2
        assert request.attachments[0].type == AttachmentType.IMAGE

    def test_attachments_max_limit(self):
        """Test that more than five attachments is rejected."""
        attachments = [
            Attachment(type=AttachmentType.IMAGE, url=f"https://s3.test/{idx}.png", filename=f"{idx}.png")
            for idx in range(6)
        ]
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(content="Too many", attachments=attachments)
        assert "no more than 5 attachments allowed" in str(exc_info.value).lower()


class TestAgentNotificationRequest:
    """Tests for AgentNotificationRequest schema."""

    def test_valid_minimal_request(self):
        """Test request with only required fields."""
        request = AgentNotificationRequest(
            user_id=1,
            session_id="abc-123",
            content="Elementary, my dear Watson.",
        )
        assert request.user_id == 1
        assert request.session_id == "abc-123"
        assert request.direction == MessageDirection.AGENT_TO_USER
        assert request.source == MessageSource.HEARTBEAT
        assert request.is_heartbeat_ok is False
        assert request.ai_character_name == "sherlock"

    def test_valid_full_request(self):
        """Test request with all fields."""
        request = AgentNotificationRequest(
            user_id=42,
            session_id="session-xyz",
            content="Test notification",
            direction=MessageDirection.HEARTBEAT,
            source=MessageSource.TEXT,
            is_heartbeat_ok=True,
            ai_character_name="bugsy",
        )
        assert request.user_id == 42
        assert request.direction == MessageDirection.HEARTBEAT
        assert request.is_heartbeat_ok is True

    def test_empty_content_rejected(self):
        """Test that empty content is rejected."""
        with pytest.raises(ValidationError):
            AgentNotificationRequest(
                user_id=1,
                session_id="abc",
                content="",
            )

    def test_missing_user_id_rejected(self):
        """Test that missing user_id is rejected."""
        with pytest.raises(ValidationError):
            AgentNotificationRequest(
                session_id="abc",
                content="test",
            )

    def test_missing_session_id_rejected(self):
        """Test that missing session_id is rejected."""
        with pytest.raises(ValidationError):
            AgentNotificationRequest(
                user_id=1,
                content="test",
            )
