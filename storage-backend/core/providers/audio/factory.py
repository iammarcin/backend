"""Audio provider factory registration and resolution."""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Type

from core.exceptions import ConfigurationError

from .base import BaseAudioProvider

logger = logging.getLogger(__name__)


_audio_providers: Dict[str, Type[BaseAudioProvider]] = {}


def register_audio_provider(name: str, provider_class: Type[BaseAudioProvider]) -> None:
    """Register an audio provider implementation."""

    _audio_providers[name] = provider_class
    logger.debug("Registered audio provider: %s", name)


def _resolve_provider_name(
    audio_settings: Mapping[str, Any],
    *,
    action: str | None,
) -> str:
    provider = (
        str(audio_settings.get("provider", "") or "").strip().lower().replace("-", "_")
    )
    if provider:
        if provider in {"gemini", "gemini_streaming"} and action in {"stream", "realtime"}:
            return "gemini_streaming"
        if provider == "openai" and action in {"stream", "realtime"}:
            return "openai_streaming"
        return provider

    model_hint = str(audio_settings.get("model", "") or "").strip().lower()
    if model_hint:
        if model_hint.startswith("gemini"):
            if action in {"stream", "realtime"}:
                return "gemini_streaming"
            return "gemini"
        if model_hint.startswith("imagen"):
            return "gemini"
        if model_hint.startswith(("gpt-4o-transcribe", "gpt-4o-mini-transcribe")):
            if action in {"stream", "realtime"}:
                return "openai_streaming"
            return "openai"
        if model_hint.startswith(("gpt", "whisper", "openai")):
            if action in {"stream", "realtime"}:
                return "openai_streaming"
            return "openai"
        if model_hint.startswith("deepgram") or model_hint.startswith("nova"):
            return "deepgram"

    if action == "translate":
        return "gemini"
    if action == "stream" or action == "realtime":
        return "deepgram"
    return "gemini"


def get_audio_provider(
    settings: Mapping[str, Any] | None = None,
    *,
    action: str | None = None,
) -> BaseAudioProvider:
    """Resolve an audio provider instance based on the supplied settings."""

    audio_settings: Mapping[str, Any] = settings.get("audio", {}) if settings else {}
    provider_name = _resolve_provider_name(audio_settings, action=action)

    if provider_name not in _audio_providers:
        raise ConfigurationError(
            f"Audio provider {provider_name} not registered. Available: {list(_audio_providers.keys())}",
            key=f"audio.provider.{provider_name}",
        )

    provider_class = _audio_providers[provider_name]
    provider = provider_class()
    provider.configure(audio_settings)
    if action in {"stream", "realtime"}:
        logger.info(
            "Resolved streaming audio provider %s (model=%s)",
            provider.name,
            audio_settings.get("model"),
        )
    logger.debug(
        "Resolved audio provider %s for name %s", provider_class.__name__, provider_name
    )
    return provider


__all__ = ["get_audio_provider", "register_audio_provider"]

