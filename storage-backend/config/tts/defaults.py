"""Text-to-speech configuration defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .providers import elevenlabs, openai

DEFAULT_PROVIDER = "openai"
DEFAULT_AUDIO_FORMAT = openai.DEFAULT_AUDIO_FORMAT
DEFAULT_QUALITY = "hd"


@dataclass(slots=True)
class TTSSettings:
    """Unified TTS settings."""

    provider: str = DEFAULT_PROVIDER
    model: Optional[str] = None
    voice: Optional[str] = None
    audio_format: str = DEFAULT_AUDIO_FORMAT
    speed: float = openai.DEFAULT_SPEED
    quality: str = DEFAULT_QUALITY

    def __post_init__(self) -> None:
        if self.model is None:
            if self.provider == "openai":
                self.model = openai.DEFAULT_MODEL
            elif self.provider == "elevenlabs":
                self.model = elevenlabs.DEFAULT_MODEL

        if self.voice is None:
            if self.provider == "openai":
                self.voice = openai.DEFAULT_VOICE
            elif self.provider == "elevenlabs":
                self.voice = elevenlabs.DEFAULT_VOICE_ID


VOICE_REGISTRY: Dict[str, str] = dict(elevenlabs.VOICE_NAME_TO_ID)

__all__ = [
    "DEFAULT_PROVIDER",
    "DEFAULT_AUDIO_FORMAT",
    "DEFAULT_QUALITY",
    "TTSSettings",
    "VOICE_REGISTRY",
]
