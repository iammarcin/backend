"""Provider Registries - Global registries for AI providers."""

from __future__ import annotations

from typing import Dict, Type

from core.providers.base import (
    BaseImageProvider,
    BaseTextProvider,
    BaseVideoProvider,
)
from core.providers.tts_base import BaseTTSProvider

_text_providers: Dict[str, Type[BaseTextProvider]] = {}
_image_providers: Dict[str, Type[BaseImageProvider]] = {}
_video_providers: Dict[str, Type[BaseVideoProvider]] = {}
_tts_providers: Dict[str, Type[BaseTTSProvider]] = {}


def register_text_provider(name: str, provider_class: Type[BaseTextProvider]) -> None:
    """Register a text provider implementation."""
    _text_providers[name] = provider_class


def register_image_provider(name: str, provider_class: Type[BaseImageProvider]) -> None:
    """Register an image provider implementation."""
    _image_providers[name] = provider_class


def register_video_provider(name: str, provider_class: Type[BaseVideoProvider]) -> None:
    """Register a video provider implementation."""
    _video_providers[name] = provider_class


def register_tts_provider(name: str, provider_class: Type[BaseTTSProvider]) -> None:
    """Register a text-to-speech provider implementation."""
    _tts_providers[name] = provider_class
