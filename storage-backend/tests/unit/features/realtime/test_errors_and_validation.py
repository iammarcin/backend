"""Unit tests covering realtime error helpers and audio validation."""

from __future__ import annotations

import struct

import pytest

from features.realtime.errors import (
    internal_error,
    rate_limit_error,
    translation_failed_error,
)
from features.realtime.validation import AudioValidationError, validate_audio_format


def test_error_payload_messages() -> None:
    """Realtime error helpers should expose user friendly messaging."""

    error = rate_limit_error(retry_after=15)
    payload = error.to_client_payload()

    assert payload["type"] == "realtime.error"
    assert "15 seconds" in payload["message"]
    assert payload["recoverable"] is True

    translation_error = translation_failed_error("upstream outage")
    log_message = translation_error.to_log_message()
    assert "translation_failed" in log_message
    assert "upstream outage" in log_message

    exception_error = internal_error(ValueError("database unavailable"))
    assert "unexpected error" in exception_error.user_message.lower()
    assert exception_error.code.value == "internal_error"


def test_audio_validation_rules() -> None:
    """PCM16 validation should reject malformed payloads."""

    valid_audio = struct.pack("h", 1) * (24_000 + 10)
    validate_audio_format(valid_audio)

    with pytest.raises(AudioValidationError):
        validate_audio_format(b"")

    with pytest.raises(AudioValidationError):
        validate_audio_format(b"\x00\x01" * 10)

    with pytest.raises(AudioValidationError):
        validate_audio_format(b"\x00" * 101)

    silent_payload = b"\x00\x00" * 24_000
    with pytest.raises(AudioValidationError):
        validate_audio_format(silent_payload)

    clipped_payload = struct.pack("h", 32767) * 24_000
    with pytest.raises(AudioValidationError):
        validate_audio_format(clipped_payload)

    with pytest.raises(AudioValidationError):
        validate_audio_format(valid_audio, expected_format="mp3")

