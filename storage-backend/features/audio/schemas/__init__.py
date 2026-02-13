"""Pydantic schemas for the audio feature."""

from .requests import (
    AudioAction,
    StaticTranscriptionRequest,
    StaticTranscriptionUserInput,
    StaticTranscriptionUserSettings,
)
from .responses import StaticTranscriptionResponse

__all__ = [
    "AudioAction",
    "StaticTranscriptionRequest",
    "StaticTranscriptionResponse",
    "StaticTranscriptionUserInput",
    "StaticTranscriptionUserSettings",
]
