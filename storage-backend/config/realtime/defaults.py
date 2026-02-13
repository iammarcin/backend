"""Realtime chat configuration defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .providers import google, openai

DEFAULT_PROVIDER = "openai"
DEFAULT_SAMPLE_RATE = openai.DEFAULT_SAMPLE_RATE


@dataclass(slots=True)
class RealtimeSettings:
    """Unified realtime chat settings."""

    provider: str = DEFAULT_PROVIDER
    model: Optional[str] = None
    sample_rate: int = DEFAULT_SAMPLE_RATE
    voice: Optional[str] = None

    def __post_init__(self) -> None:
        if self.model is None:
            if self.provider == "openai":
                self.model = openai.DEFAULT_MODEL
            elif self.provider == "google":
                self.model = google.DEFAULT_MODEL

        if self.voice is None:
            if self.provider == "openai":
                self.voice = openai.DEFAULT_VOICE
            elif self.provider == "google":
                self.voice = google.DEFAULT_VOICE


__all__ = ["DEFAULT_PROVIDER", "DEFAULT_SAMPLE_RATE", "RealtimeSettings"]
