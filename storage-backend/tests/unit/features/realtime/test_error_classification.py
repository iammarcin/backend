"""Tests for realtime error classification helpers."""

from features.realtime.errors import (
    RealtimeErrorSeverity,
    classify_error,
    is_expected_vad_error,
)


def test_empty_buffer_error_is_informational() -> None:
    """Empty buffer error should be treated as informational and non-fatal."""

    classification = classify_error("input_audio_buffer_commit_empty")

    assert classification.severity == RealtimeErrorSeverity.INFORMATIONAL
    assert classification.should_mark_error is False
    assert classification.should_close_session is False


def test_unknown_error_is_fatal() -> None:
    """Unknown errors should default to fatal handling."""

    classification = classify_error("unknown_error_code")

    assert classification.severity == RealtimeErrorSeverity.FATAL
    assert classification.should_mark_error is True
    assert classification.should_close_session is True


def test_is_expected_vad_error() -> None:
    """Empty buffer errors are expected when VAD is enabled."""

    assert is_expected_vad_error("input_audio_buffer_commit_empty", vad_enabled=True)
    assert not is_expected_vad_error(
        "input_audio_buffer_commit_empty", vad_enabled=False
    )
    assert not is_expected_vad_error("other_error", vad_enabled=True)
