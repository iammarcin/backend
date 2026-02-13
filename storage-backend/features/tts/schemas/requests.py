"""Pydantic request models for the TTS feature."""

from __future__ import annotations

from enum import Enum
import json
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TTSAction(str, Enum):
    TTS_NO_STREAM = "tts_no_stream"
    TTS_STREAM = "tts_stream"
    BILLING = "billing"


class TTSUserInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str = Field(..., min_length=1, description="Text to synthesise into speech")


class TTSGeneralSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    return_test_data: bool = Field(
        default=False,
        description="Return canned data instead of contacting providers",
    )
    save_to_s3: bool = Field(
        default=True,
        description="Persist generated audio to S3",
    )


class TTSProviderSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: Optional[str] = Field(default=None, description="Explicit provider override")
    model: Optional[str] = Field(default=None, description="Provider specific model name")
    voice: Optional[str] = Field(default=None, description="Voice identifier or name")
    format: Optional[str] = Field(default=None, description="Audio format such as mp3 or pcm")
    streaming: Optional[bool] = Field(default=None, description="Reserved for future streaming support")
    speed: Optional[float] = Field(default=None, description="Playback speed multiplier")
    instructions: Optional[str] = Field(default=None, description="Additional provider instructions")
    tts_auto_execute: Optional[bool] = Field(
        default=None,
        description="Automatically trigger TTS generation",
    )
    chunk_schedule: Optional[list[int]] = Field(
        default=None,
        description="Optional chunk lengths for streaming providers",
    )
    stability: Optional[float] = Field(default=None, description="ElevenLabs stability value")
    similarity_boost: Optional[float] = Field(
        default=None,
        description="ElevenLabs similarity boost",
    )
    style: Optional[float] = Field(default=None, description="ElevenLabs style exaggeration")
    use_speaker_boost: Optional[bool] = Field(
        default=None,
        description="ElevenLabs speaker boost toggle",
    )

    @field_validator("chunk_schedule", mode="before")
    @classmethod
    def parse_chunk_schedule(
        cls, value: Optional[list[int] | str]
    ) -> Optional[list[int]]:
        if value in (None, ""):
            return None
        if isinstance(value, list):
            if not all(isinstance(item, int) for item in value):
                raise ValueError("chunk_schedule must be a list of integers")
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("chunk_schedule must be JSON encoded list of integers") from exc
            if isinstance(parsed, int):
                return [parsed] * 4
            if isinstance(parsed, list) and len(parsed) == 4 and all(
                isinstance(item, int) for item in parsed
            ):
                return parsed
            raise ValueError("chunk_schedule must be a list of four integers")
        raise ValueError("chunk_schedule must be a list of integers")

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0:
            raise ValueError("speed must be positive")
        return value

    def as_provider_settings(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=False, exclude_none=True)


class TTSUserSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    general: TTSGeneralSettings = Field(default_factory=TTSGeneralSettings)
    tts: TTSProviderSettings = Field(default_factory=TTSProviderSettings)

    def to_provider_payload(self) -> Dict[str, Any]:
        return {"tts": self.tts.as_provider_settings()}


class TTSGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: TTSAction = Field(default=TTSAction.TTS_NO_STREAM)
    user_input: TTSUserInput = Field(...)
    user_settings: TTSUserSettings = Field(default_factory=TTSUserSettings)
    customer_id: int = Field(..., ge=1)
    asset_input: Optional[Union[Dict[str, Any], List[Any]]] = Field(default=None)


__all__ = [
    "TTSAction",
    "TTSGenerateRequest",
    "TTSProviderSettings",
    "TTSUserInput",
    "TTSUserSettings",
]
