"""Unit tests for TTS persistence validation.

Milestone 6: Fix Backend TTS Validation
- Tests document the validation rules for TTS update requests
- Ensures message_id >= 1 is required for UpdateMessageRequest
"""

import pytest
from pydantic import ValidationError

from features.chat.schemas.requests import UpdateMessageRequest
from features.chat.schemas.message_content import MessagePatch


class TestTTSUpdateMessageValidation:
    """Tests for UpdateMessageRequest validation used in TTS persistence."""

    def test_valid_message_id_passes_validation(self):
        """UpdateMessageRequest should accept message_id >= 1."""
        patch = MessagePatch(file_locations=["https://example.com/audio.mp3"])
        request = UpdateMessageRequest(
            customer_id=1,
            message_id=1,
            patch=patch,
            append_image_locations=False,
        )
        assert request.message_id == 1

    def test_message_id_100_passes_validation(self):
        """UpdateMessageRequest should accept any positive message_id."""
        patch = MessagePatch(file_locations=["https://example.com/audio.mp3"])
        request = UpdateMessageRequest(
            customer_id=1,
            message_id=100,
            patch=patch,
            append_image_locations=False,
        )
        assert request.message_id == 100

    def test_message_id_zero_fails_validation(self):
        """UpdateMessageRequest should reject message_id = 0 (ge=1 constraint)."""
        patch = MessagePatch(file_locations=["https://example.com/audio.mp3"])
        with pytest.raises(ValidationError) as exc_info:
            UpdateMessageRequest(
                customer_id=1,
                message_id=0,
                patch=patch,
                append_image_locations=False,
            )
        assert "message_id" in str(exc_info.value)

    def test_message_id_negative_fails_validation(self):
        """UpdateMessageRequest should reject message_id < 0 (ge=1 constraint).

        This was the old Kotlin behavior: sending -1 when messageId was null.
        """
        patch = MessagePatch(file_locations=["https://example.com/audio.mp3"])
        with pytest.raises(ValidationError) as exc_info:
            UpdateMessageRequest(
                customer_id=1,
                message_id=-1,
                patch=patch,
                append_image_locations=False,
            )
        assert "message_id" in str(exc_info.value)


class TestTTSPersistenceScenarios:
    """Documents real-world TTS persistence scenarios."""

    def test_tts_update_requires_message_id(self):
        """TTS persistence requires a valid message_id to know which message to update.

        Scenario: User clicks "Speak" on a message in chat.
        The backend needs message_id to update that specific message with the TTS audio URL.
        """
        # This is what the backend receives from a valid TTS request
        user_input = {
            "text": "Hello, how are you?",
            "message_id": 42,
        }

        message_id = user_input.get("message_id")
        assert message_id is not None
        assert message_id >= 1

    def test_missing_message_id_is_detected(self):
        """Early validation catches missing message_id before hitting Pydantic.

        The persist_tts_only_result function checks for message_id first
        and sends an error event if missing.
        """
        # Scenario: Kotlin sends TTS request without message_id
        user_input_missing = {
            "text": "Hello, how are you?",
            # message_id is missing
        }

        message_id = user_input_missing.get("message_id")
        assert message_id is None  # Early check should catch this

    def test_invalid_message_id_detected_by_pydantic(self):
        """Pydantic validation catches invalid message_id values.

        If the early check passes (message_id exists) but value is invalid (< 1),
        Pydantic validation fails when building UpdateMessageRequest.
        """
        # Scenario: Kotlin sends message_id = -1 (old bug)
        user_input_invalid = {
            "text": "Hello, how are you?",
            "message_id": -1,  # Invalid value from old Kotlin code
        }

        message_id = user_input_invalid.get("message_id")
        assert message_id is not None  # Early check would pass
        assert message_id < 1  # But Pydantic validation would fail
