"""Pydantic schemas shared across realtime feature components."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Mapping, Optional

from pydantic import AliasChoices, BaseModel, Field, field_serializer, field_validator

from .settings_parser import build_settings_from_user_settings

_MODEL_ALIASES: dict[str, str] = {
    "openai-realtime": "gpt-realtime",
    "realtime": "gpt-realtime",
    "realtime-mini": "gpt-realtime-mini",
    "gpt-4o-realtime": "gpt-realtime",
    "gpt-realtime-preview": "gpt-realtime",
    "gpt-4o-realtime-preview": "gpt-realtime",
}


class RealtimeSessionSettings(BaseModel):
    """User configurable settings for realtime provider sessions."""

    model: str = Field(default="gpt-realtime", description="Requested realtime model identifier")
    voice: Optional[str] = Field(
        default=None,
        description="Preferred voice to use for speech synthesis when supported",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature forwarded to the provider",
    )
    vad_enabled: bool = Field(
        default=True,
        description="Whether server-side voice activity detection should run",
    )
    enable_audio_input: bool = Field(
        default=True,
        description="Flag indicating audio input streams should be accepted",
    )
    enable_audio_output: bool = Field(
        default=True,
        description="Flag indicating audio response streams should be emitted",
    )
    tts_auto_execute: bool = Field(
        default=False,
        alias="ttsAutoExecute",
        validation_alias=AliasChoices("tts_auto_execute", "ttsAutoExecute"),
        serialization_alias="ttsAutoExecute",
        description="Whether the provider should prioritise audio output over text",
    )
    live_translation: bool = Field(
        default=False,
        alias="liveTranslation",
        validation_alias=AliasChoices("live_translation", "liveTranslation"),
        serialization_alias="liveTranslation",
        description="Enable live translation via auxiliary transcription services",
    )
    translation_language: Optional[str] = Field(
        default=None,
        alias="translationLanguage",
        validation_alias=AliasChoices("translation_language", "translationLanguage"),
        serialization_alias="translationLanguage",
        description="Target language when live translation is enabled",
    )
    return_test_data: bool = Field(
        default=False,
        alias="returnTestData",
        validation_alias=AliasChoices("return_test_data", "returnTestData"),
        serialization_alias="returnTestData",
        description="Whether the backend should bypass providers and emit deterministic payloads",
    )
    session_name: Optional[str] = Field(
        default=None,
        description="Optional friendly session name persisted with chat history",
    )
    instructions: Optional[str] = Field(
        default=None,
        description="System instructions/prompt for the AI character",
    )

    @field_validator("model")
    @classmethod
    def _normalise_model(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("model cannot be empty")
        alias = _MODEL_ALIASES.get(value.lower())
        if alias:
            return alias
        return value

    @classmethod
    def from_user_settings(
        cls,
        user_settings: Mapping[str, object] | None,
        *,
        defaults: "RealtimeSessionSettings" | None = None,
    ) -> "RealtimeSessionSettings":
        """Return settings derived from a ``user_settings`` style payload."""

        settings = build_settings_from_user_settings(cls, user_settings, defaults=defaults)

        if not isinstance(user_settings, Mapping):
            return settings

        nested_model = _extract_nested_model(user_settings)
        if nested_model:
            merged_settings = settings.model_dump()
            merged_settings["model"] = nested_model
            settings = cls.model_validate(merged_settings)

        return settings

    def _audio_requested(self) -> bool:
        """Return ``True`` when audio should be requested from providers."""

        return self.enable_audio_output and self.tts_auto_execute

    def modalities(self) -> list[str]:
        """Return the list of output modalities requested by the client."""

        if self._audio_requested():
            # Providers only allow a single modality; audio responses include transcripts.
            return ["audio"]
        return ["text"]

    def to_provider_payload(self) -> dict[str, object]:
        """Return a mapping forwarded to realtime provider implementations."""

        payload: dict[str, object] = {
            "model": self.model,
            "voice": self.voice,
            "temperature": self.temperature,
            "vad_enabled": self.vad_enabled,
            "enable_audio_input": self.enable_audio_input,
            "enable_audio_output": self._audio_requested(),
            "tts_auto_execute": self.tts_auto_execute,
            "live_translation": self.live_translation,
            "translation_language": self.translation_language,
        }
        if self.instructions:
            payload["instructions"] = self.instructions
        return payload

    def requires_text_output(self) -> bool:
        """Return True when textual responses are expected for the turn."""

        return not self._audio_requested()


class RealtimeSessionSnapshot(BaseModel):
    """Minimal snapshot describing the active realtime session."""

    session_id: str = Field(..., description="Unique identifier for the websocket session")
    customer_id: int = Field(..., ge=1, description="Authenticated customer identifier")
    turn_id: Optional[str] = Field(
        default=None, description="Current conversational turn identifier if active"
    )


class EventCategory(str, Enum):
    """Broad categories describing realtime websocket events."""

    LIFECYCLE = "lifecycle"
    PERSISTENCE = "persistence"
    CONTROL = "control"


class BaseRealtimeEvent(BaseModel):
    """Base schema applied to realtime websocket events."""

    message_type: str = Field(alias="type")
    session_id: str
    category: EventCategory
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the event was emitted.",
    )

    model_config = {
        "populate_by_name": True,
    }

    @field_serializer("timestamp")
    def _serialise_timestamp(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()


class TurnCompletedEvent(BaseRealtimeEvent):
    """Turn completed and ready for persistence."""

    message_type: Literal["turn.completed"] = Field(
        default="turn.completed", alias="type"
    )
    category: Literal[EventCategory.LIFECYCLE] = EventCategory.LIFECYCLE
    turn_number: int
    audio_filename: str | None = Field(
        default=None, description="Derived filename for the next turn"
    )
    user_transcript: str = Field(
        default="", description="User transcript captured for the completed turn"
    )
    ai_transcript: str = Field(
        default="", description="Assistant transcript generated for the turn"
    )
    has_audio: bool = Field(default=False, description="Whether audio output was produced")
    duration_ms: float | None = Field(
        default=None, description="Duration of the completed turn in milliseconds"
    )


class TurnPersistedEvent(BaseRealtimeEvent):
    """Turn content persisted to database and storage."""

    message_type: Literal["turn.persisted"] = Field(
        default="turn.persisted", alias="type"
    )
    category: Literal[EventCategory.PERSISTENCE] = EventCategory.PERSISTENCE
    turn_number: int
    user_message_id: str
    ai_message_id: str
    audio_url: str | None = Field(
        default=None, description="S3 URL of persisted audio when available"
    )


class RealtimeErrorEvent(BaseRealtimeEvent):
    """Structured realtime error emitted to websocket clients."""

    message_type: Literal["realtime.error"] = Field(
        default="realtime.error", alias="type"
    )
    category: Literal[EventCategory.CONTROL] = EventCategory.CONTROL
    code: str
    message: str
    recoverable: bool = Field(default=True)
    details: dict[str, object] = Field(default_factory=dict)
    turn_number: int | None = Field(
        default=None, description="Turn number associated with the error if known"
    )


class SessionClosedEvent(BaseRealtimeEvent):
    """Realtime session closed."""

    message_type: Literal["session.closed"] = Field(
        default="session.closed", alias="type"
    )
    category: Literal[EventCategory.LIFECYCLE] = EventCategory.LIFECYCLE
    total_turns: int
    total_duration_ms: float


class RealtimeHandshakeMessage(BaseModel):
    """Initial handshake payload returned when the websocket is accepted."""

    message_type: Literal["websocket_ready"] = Field(default="websocket_ready", alias="type")
    session: RealtimeSessionSnapshot
    settings: RealtimeSessionSettings

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


__all__ = [
    "BaseRealtimeEvent",
    "EventCategory",
    "RealtimeHandshakeMessage",
    "RealtimeSessionSettings",
    "RealtimeSessionSnapshot",
    "SessionClosedEvent",
    "TurnCompletedEvent",
    "TurnPersistedEvent",
    "RealtimeErrorEvent",
]


def _extract_nested_model(source: Mapping[str, object]) -> str | None:
    """Extract model override from nested user settings payload.

    Uses canonical snake_case keys only (realtime, text).
    """
    for key in ("realtime", "text"):
        nested = source.get(key)
        if isinstance(nested, Mapping):
            candidate = nested.get("model")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None
