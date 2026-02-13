"""Response payloads for the TTS feature."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.pydantic_schemas import ApiResponse


class TTSSuccessMessage(BaseModel):
    """Legacy-compatible message payload for TTS responses."""

    status: str = Field(default="completed", description="Job completion status")
    result: Any = Field(..., description="Primary result such as S3 URL or billing data")


class TTSMetadata(BaseModel):
    """Metadata returned alongside generated audio."""

    model_config = ConfigDict(populate_by_name=True)

    provider: str = Field(..., description="Provider identifier")
    model: str = Field(..., description="Resolved provider model")
    voice: Optional[str] = Field(default=None, description="Voice identifier used for synthesis")
    format: str = Field(..., description="Audio format")
    s3_url: Optional[str] = Field(default=None, alias="s3Url", description="Uploaded S3 URL")
    chunk_count: Optional[int] = Field(default=None, description="Number of text chunks processed")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Additional provider metadata")


class TTSGenerateResponse(ApiResponse[TTSMetadata]):
    """Envelope for the synchronous TTS endpoint."""

    message: TTSSuccessMessage


class TTSBillingResponse(ApiResponse[Dict[str, Any]]):
    """Envelope returned when retrieving ElevenLabs billing information."""

    message: TTSSuccessMessage


__all__ = [
    "TTSBillingResponse",
    "TTSGenerateResponse",
    "TTSMetadata",
    "TTSSuccessMessage",
]
