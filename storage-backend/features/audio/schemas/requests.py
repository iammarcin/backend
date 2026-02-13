"""Request models for static transcription workflows."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AudioAction(str, Enum):
    """Supported static speech processing actions."""

    CHAT = "chat"
    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"


class StaticTranscriptionUserInput(BaseModel):
    """User supplied metadata accompanying the audio upload."""

    model_config = ConfigDict(extra="allow")

    prompt: str | None = None
    conversation_id: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    file_path: str | None = None
    file_name: str | None = None


class StaticTranscriptionGeneralSettings(BaseModel):
    """General toggles mirrored from the legacy payload."""

    model_config = ConfigDict(extra="allow")

    return_test_data: bool = False


class StaticTranscriptionSpeechSettings(BaseModel):
    """Speech specific settings forwarded to downstream providers."""

    model_config = ConfigDict(extra="allow")

    model: str | None = None
    language: str | None = None
    temperature: float | None = None
    response_format: str | None = None
    optional_prompt: str | None = None


class StaticTranscriptionUserSettings(BaseModel):
    """Structured representation of the ``user_settings`` payload."""

    model_config = ConfigDict(extra="allow")

    general: StaticTranscriptionGeneralSettings = Field(
        default_factory=StaticTranscriptionGeneralSettings
    )
    speech: StaticTranscriptionSpeechSettings = Field(
        default_factory=StaticTranscriptionSpeechSettings
    )


class StaticTranscriptionRequest(BaseModel):
    """Normalised request consumed by the audio feature."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    action: AudioAction
    category: Literal["speech"]
    customer_id: int = Field(..., ge=1)
    user_input: StaticTranscriptionUserInput = Field(
        default_factory=StaticTranscriptionUserInput
    )
    user_settings: StaticTranscriptionUserSettings = Field(
        default_factory=StaticTranscriptionUserSettings
    )

    @model_validator(mode="before")
    @classmethod
    def _parse_json_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        parsed: Dict[str, Any] = dict(values or {})
        for field in ("user_input", "user_settings"):
            raw_value = parsed.get(field)
            if isinstance(raw_value, (bytes, bytearray)):
                raw_value = raw_value.decode()
            if isinstance(raw_value, str):
                raw_value = raw_value.strip()
                if not raw_value:
                    parsed[field] = {}
                    continue
                try:
                    parsed[field] = json.loads(raw_value)
                except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                    raise ValueError(f"{field} must be valid JSON") from exc
        return parsed

    @field_validator("category", mode="before")
    @classmethod
    def _normalise_category(cls, value: Any) -> str:
        if isinstance(value, str) and value.lower() == "speech":
            return "speech"
        raise ValueError("Static transcription currently supports only the 'speech' category")


__all__ = [
    "AudioAction",
    "StaticTranscriptionGeneralSettings",
    "StaticTranscriptionRequest",
    "StaticTranscriptionSpeechSettings",
    "StaticTranscriptionUserInput",
    "StaticTranscriptionUserSettings",
]
