"""Request models for FastAPI endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import AliasChoices, BaseModel, Field, field_validator


class PromptTextItem(BaseModel):
    """Text item in prompt list."""

    type: str = Field(default="text")
    text: str


class PromptImageModeItem(BaseModel):
    """Image mode item in prompt list."""

    type: str = Field(default="image_mode")
    image_mode: str


class PromptImageUrlItem(BaseModel):
    """Image URL item in prompt list."""

    type: str = Field(default="image_url")
    image_url: Union[str, Dict[str, Any]]


class PromptFileUrlItem(BaseModel):
    """File URL item in prompt list."""

    type: str = Field(default="file_url")
    file_url: Union[str, Dict[str, Any]]


PromptItem = Union[PromptTextItem, PromptImageModeItem, PromptImageUrlItem, PromptFileUrlItem]


class RealtimeSettings(BaseModel):
    """Settings forwarded when initialising realtime sessions."""

    model: str = Field(default="gpt-realtime", description="Realtime model identifier")
    voice: Optional[str] = Field(default=None, description="Preferred realtime voice")
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature applied by the realtime provider",
    )
    vad_enabled: bool = Field(default=True, description="Enable server-side VAD")
    enable_audio_input: bool = Field(default=True, description="Accept audio input streams")
    enable_audio_output: bool = Field(default=True, description="Emit audio response streams")
    google_available_voices: List[str] = Field(
        default_factory=lambda: ["Puck", "Charon", "Kore", "Fenrir", "Aoede"],
        alias=AliasChoices("google_available_voices", "googleAvailableVoices"),
        description="Prebuilt Google voices supported by realtime sessions",
    )
    temperature_min: float = Field(
        default=0.1,
        alias=AliasChoices("temperature_min", "temperatureMin"),
        description="Lower bound for realtime temperature",
    )
    temperature_max: float = Field(
        default=1.2,
        alias=AliasChoices("temperature_max", "temperatureMax"),
        description="Upper bound for realtime temperature",
    )
    supported_modalities: List[str] = Field(
        default_factory=lambda: ["text", "audio"],
        alias=AliasChoices("supported_modalities", "supportedModalities"),
        description="Modalities currently supported by realtime providers",
    )

    @field_validator("model")
    @classmethod
    def _validate_model(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("model cannot be empty")
        return value


class ChatRequest(BaseModel):
    """Request payload for chat interactions."""

    prompt: Union[str, List[PromptItem]] = Field(..., description="User message/prompt")
    settings: Dict[str, Any] = Field(default_factory=dict, description="User settings")
    customer_id: int = Field(..., gt=0, description="Customer identifier")
    session_id: Optional[str] = Field(None, description="Optional session identifier")
    stream: bool = Field(False, description="Whether to stream the response")
    realtime: Optional[RealtimeSettings] = Field(
        default=None,
        description="Optional realtime session configuration",
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt(
        cls, value: Union[str, List[PromptItem]]
    ) -> Union[str, List[PromptItem]]:
        if isinstance(value, str):
            if not value or not value.strip():
                raise ValueError("Prompt cannot be empty")
            return value.strip()

        if isinstance(value, list) and value:
            return value

        raise ValueError("Prompt must be a non-empty string or list of items")


class ImageGenerationRequest(BaseModel):
    """Request payload for image generation."""

    prompt: str = Field(..., min_length=1)
    settings: Dict[str, Any] = Field(default_factory=dict)
    customer_id: int = Field(..., gt=0)
    image_url: Optional[str] = None
    message_id: Optional[str] = None
    save_to_db: bool = True
    session_id: Optional[str] = None


class VideoGenerationRequest(BaseModel):
    """Request payload for video generation."""

    prompt: str = Field(..., min_length=1)
    settings: Dict[str, Any] = Field(default_factory=dict)
    customer_id: int = Field(..., gt=0)
    input_image_url: Optional[str] = None
    save_to_db: bool = True
    session_id: Optional[str] = None


class WebSocketMessage(BaseModel):
    """Generic WebSocket message payload."""

    type: str = Field(..., description="Message type: chat, audio, control")
    prompt: Optional[str] = None
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict)
    customer_id: Optional[int] = None
    data: Optional[Any] = None


__all__ = [
    "PromptTextItem",
    "PromptImageModeItem",
    "PromptImageUrlItem",
    "PromptFileUrlItem",
    "PromptItem",
    "RealtimeSettings",
    "ChatRequest",
    "ImageGenerationRequest",
    "VideoGenerationRequest",
    "WebSocketMessage",
]
