"""Structured error helpers for realtime websocket flows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RealtimeErrorSeverity(str, Enum):
    """Severity levels for realtime provider errors."""

    INFORMATIONAL = "informational"
    RECOVERABLE = "recoverable"
    FATAL = "fatal"


@dataclass(slots=True)
class RealtimeErrorClassification:
    """Classification metadata describing how to handle provider errors."""

    severity: RealtimeErrorSeverity
    should_mark_error: bool
    should_close_session: bool
    log_level: str


class RealtimeErrorCode(str, Enum):
    """Enumeration of realtime specific error categories."""

    # Connection errors
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_TIMEOUT = "connection_timeout"
    AUTHENTICATION_FAILED = "authentication_failed"

    # Audio errors
    AUDIO_FORMAT_INVALID = "audio_format_invalid"
    AUDIO_TOO_LARGE = "audio_too_large"
    AUDIO_UPLOAD_FAILED = "audio_upload_failed"

    # Provider errors
    PROVIDER_RATE_LIMIT = "provider_rate_limit"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"

    # Validation errors
    INVALID_MESSAGE_FORMAT = "invalid_message_format"
    INVALID_SETTINGS = "invalid_settings"

    # Processing errors
    TRANSCRIPTION_FAILED = "transcription_failed"
    TRANSLATION_FAILED = "translation_failed"
    PERSISTENCE_FAILED = "persistence_failed"

    # Internal errors
    INTERNAL_ERROR = "internal_error"


@dataclass(slots=True)
class RealtimeError:
    """Structured realtime error with end-user and developer messaging."""

    code: RealtimeErrorCode
    user_message: str
    developer_message: str
    recoverable: bool = True
    details: dict | None = None

    def to_client_payload(self) -> dict[str, object]:
        """Return JSON serialisable payload for websocket clients."""

        return {
            "type": "realtime.error",
            "code": self.code.value,
            "message": self.user_message,
            "recoverable": self.recoverable,
            "details": self.details or {},
        }

    def to_log_message(self) -> str:
        """Return a concise developer facing log entry."""

        suffix = f", details={self.details}" if self.details else ""
        return f"[{self.code.value}] {self.developer_message}{suffix}"


ERROR_CLASSIFICATIONS: dict[str, RealtimeErrorClassification] = {
    "input_audio_buffer_commit_empty": RealtimeErrorClassification(
        severity=RealtimeErrorSeverity.INFORMATIONAL,
        should_mark_error=False,
        should_close_session=False,
        log_level="warning",
    ),
    "rate_limit_exceeded": RealtimeErrorClassification(
        severity=RealtimeErrorSeverity.RECOVERABLE,
        should_mark_error=True,
        should_close_session=True,
        log_level="error",
    ),
    "invalid_api_key": RealtimeErrorClassification(
        severity=RealtimeErrorSeverity.FATAL,
        should_mark_error=True,
        should_close_session=True,
        log_level="error",
    ),
    "model_not_found": RealtimeErrorClassification(
        severity=RealtimeErrorSeverity.FATAL,
        should_mark_error=True,
        should_close_session=True,
        log_level="error",
    ),
}


DEFAULT_ERROR_CLASSIFICATION = RealtimeErrorClassification(
    severity=RealtimeErrorSeverity.FATAL,
    should_mark_error=True,
    should_close_session=True,
    log_level="error",
)


def classify_error(error_code: str | None) -> RealtimeErrorClassification:
    """Return the classification metadata for a provider error."""

    if not error_code:
        return DEFAULT_ERROR_CLASSIFICATION
    return ERROR_CLASSIFICATIONS.get(error_code, DEFAULT_ERROR_CLASSIFICATION)


def is_expected_vad_error(error_code: str | None, vad_enabled: bool) -> bool:
    """Return ``True`` when the error is expected under VAD mode."""

    return vad_enabled and error_code == "input_audio_buffer_commit_empty"


def connection_failed_error(reason: str) -> RealtimeError:
    """Return error representing a provider connection failure."""

    return RealtimeError(
        code=RealtimeErrorCode.CONNECTION_FAILED,
        user_message="Unable to connect to voice service. Please try again shortly.",
        developer_message=f"Failed to establish provider connection: {reason}",
        recoverable=True,
        details={"reason": reason},
    )


def audio_format_error(format_info: str) -> RealtimeError:
    """Return error describing invalid audio format or payload."""

    return RealtimeError(
        code=RealtimeErrorCode.AUDIO_FORMAT_INVALID,
        user_message="Audio format not supported. Please check your microphone settings.",
        developer_message=f"Received invalid audio format: {format_info}",
        recoverable=True,
        details={"format": format_info},
    )


def audio_upload_failed_error(reason: str) -> RealtimeError:
    """Return error emitted when audio persistence fails."""

    return RealtimeError(
        code=RealtimeErrorCode.AUDIO_UPLOAD_FAILED,
        user_message="Could not upload audio recording. Please retry your message.",
        developer_message=f"Realtime audio upload failed: {reason}",
        recoverable=True,
        details={"reason": reason},
    )


def rate_limit_error(retry_after: int | None = None) -> RealtimeError:
    """Return error for provider rate limiting events."""

    if retry_after:
        user_message = f"Too many requests. Please wait {retry_after} seconds and try again."
    else:
        user_message = "Too many requests. Please wait a moment and try again."

    return RealtimeError(
        code=RealtimeErrorCode.PROVIDER_RATE_LIMIT,
        user_message=user_message,
        developer_message=f"Provider rate limit exceeded (retry_after={retry_after})",
        recoverable=True,
        details={"retry_after": retry_after} if retry_after else None,
    )


def provider_failure_error(reason: str) -> RealtimeError:
    """Return error for generic provider failures surfaced to clients."""

    return RealtimeError(
        code=RealtimeErrorCode.PROVIDER_UNAVAILABLE,
        user_message="Voice service is currently unavailable. Please try again soon.",
        developer_message=f"Realtime provider error: {reason}",
        recoverable=True,
        details={"reason": reason},
    )


def invalid_message_error(reason: str) -> RealtimeError:
    """Return error when client payloads fail validation."""

    return RealtimeError(
        code=RealtimeErrorCode.INVALID_MESSAGE_FORMAT,
        user_message="Message format not accepted. Please update your client and retry.",
        developer_message=f"Invalid realtime client payload: {reason}",
        recoverable=True,
        details={"reason": reason},
    )


def transcription_failed_error(reason: str) -> RealtimeError:
    """Return error for STT transcription failures."""

    return RealtimeError(
        code=RealtimeErrorCode.TRANSCRIPTION_FAILED,
        user_message="Could not understand audio. Please try speaking more clearly.",
        developer_message=f"Transcription failed: {reason}",
        recoverable=True,
        details={"reason": reason},
    )


def translation_failed_error(reason: str) -> RealtimeError:
    """Return warning style error when translation cannot be completed."""

    return RealtimeError(
        code=RealtimeErrorCode.TRANSLATION_FAILED,
        user_message="Translation service unavailable. Showing original response.",
        developer_message=f"Translation failed: {reason}",
        recoverable=True,
        details={"reason": reason},
    )


def persistence_failed_error(reason: str) -> RealtimeError:
    """Return error when database persistence fails."""

    return RealtimeError(
        code=RealtimeErrorCode.PERSISTENCE_FAILED,
        user_message="Generated response could not be saved. Please try again.",
        developer_message=f"Failed to persist realtime turn: {reason}",
        recoverable=False,
        details={"reason": reason},
    )


def internal_error(exception: Exception) -> RealtimeError:
    """Return error wrapper for unexpected exceptions."""

    exc_type = type(exception).__name__
    return RealtimeError(
        code=RealtimeErrorCode.INTERNAL_ERROR,
        user_message="An unexpected error occurred. Please try again.",
        developer_message=f"Internal error: {exc_type}: {exception}",
        recoverable=True,
        details={"exception_type": exc_type},
    )


__all__ = [
    "RealtimeErrorClassification",
    "RealtimeError",
    "RealtimeErrorCode",
    "RealtimeErrorSeverity",
    "audio_format_error",
    "audio_upload_failed_error",
    "classify_error",
    "connection_failed_error",
    "internal_error",
    "invalid_message_error",
    "is_expected_vad_error",
    "persistence_failed_error",
    "provider_failure_error",
    "rate_limit_error",
    "transcription_failed_error",
    "translation_failed_error",
]

