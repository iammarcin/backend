"""Response models for static transcription workflows."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .requests import AudioAction


class StaticTranscriptionResponse(BaseModel):
    """Envelope returned by the static transcription REST endpoint."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    status: str = Field(default="completed", description="Processing status")
    result: str = Field(description="Transcript or translation text")
    action: AudioAction = Field(description="Action executed for the recording")
    provider: str | None = Field(
        default=None, description="Provider identifier once integrations are wired"
    )
    filename: str | None = Field(default=None, alias="fileName")
    language: str | None = Field(default=None, description="Detected or target language")


__all__ = ["StaticTranscriptionResponse"]
