"""Tests for Sherlock offline sync handling in audio transcribe endpoint.

These tests focus on unit testing the _handle_offline_sherlock_sync helper function
which routes offline messages to OpenClaw Gateway.
"""

import pytest
from unittest.mock import patch, AsyncMock


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestHandleOfflineSherlockSync:
    """Tests for the _handle_offline_sherlock_sync helper function."""

    async def test_builds_batch_header_for_middle_message(self):
        """Test batch header construction for middle message in batch."""
        from features.audio.routes import _handle_offline_sherlock_sync

        metadata = {
            "ai_character_name": "sherlock",
            "session_id": "existing-session-123",
            "batch_index": 2,
            "batch_total": 3,
            "recorded_at": "2025-12-21 14:30"
        }

        with patch(
            "features.audio.routes.is_openclaw_enabled", return_value=True
        ), patch(
            "features.audio.routes.send_message_to_openclaw",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = {"session_id": "existing-session-123"}

            result = await _handle_offline_sherlock_sync(
                transcription="Hello world",
                metadata=metadata,
                user_id=1,
            )

            assert result == "existing-session-123"

            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args[1]

            # Check that batch header is in the content
            assert "2/3" in call_kwargs["message"]
            assert "More offline messages are queued" in call_kwargs["message"]
            assert call_kwargs["ai_character_name"] == "sherlock"
            assert call_kwargs["session_id"] == "existing-session-123"

    async def test_builds_batch_header_for_last_message(self):
        """Test batch header construction for last message in batch."""
        from features.audio.routes import _handle_offline_sherlock_sync

        metadata = {
            "ai_character_name": "sherlock",
            "session_id": None,  # New session
            "batch_index": 3,
            "batch_total": 3,
            "recorded_at": "2025-12-21 14:30"
        }

        with patch(
            "features.audio.routes.is_openclaw_enabled", return_value=True
        ), patch(
            "features.audio.routes.send_message_to_openclaw",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = {"session_id": "new-session"}

            result = await _handle_offline_sherlock_sync(
                transcription="Final message",
                metadata=metadata,
                user_id=1,
            )

            assert result == "new-session"

            call_kwargs = mock_send.call_args[1]
            assert "3/3" in call_kwargs["message"]
            assert "last offline message" in call_kwargs["message"]

    async def test_builds_single_message_header(self):
        """Test header construction for single offline message."""
        from features.audio.routes import _handle_offline_sherlock_sync

        metadata = {
            "ai_character_name": "bugsy",
            "session_id": "session-abc",
            "batch_index": 1,
            "batch_total": 1,
            "recorded_at": "2025-12-21 10:00"
        }

        with patch(
            "features.audio.routes.is_openclaw_enabled", return_value=True
        ), patch(
            "features.audio.routes.send_message_to_openclaw",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = {"session_id": "session-abc"}

            result = await _handle_offline_sherlock_sync(
                transcription="Single offline message",
                metadata=metadata,
                user_id=1,
            )

            assert result == "session-abc"

            call_kwargs = mock_send.call_args[1]
            assert "Recorded while offline" in call_kwargs["message"]
            assert "2025-12-21 10:00" in call_kwargs["message"]
            assert call_kwargs["ai_character_name"] == "bugsy"

    async def test_raises_when_openclaw_disabled(self):
        """Test that offline sync raises when OpenClaw is disabled."""
        from features.audio.routes import _handle_offline_sherlock_sync

        metadata = {
            "ai_character_name": "sherlock",
            "session_id": "sess-1",
            "batch_index": 1,
            "batch_total": 1,
            "recorded_at": "now"
        }

        with patch(
            "features.audio.routes.is_openclaw_enabled", return_value=False
        ):
            with pytest.raises(RuntimeError, match="OpenClaw is not enabled"):
                await _handle_offline_sherlock_sync(
                    transcription="Test",
                    metadata=metadata,
                    user_id=1,
                )
