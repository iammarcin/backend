"""Provider Resolvers - Dynamic Resolution of AI Providers at Runtime

This module contains the factory functions that resolve providers from settings.
It uses the registries from factory.py to select the appropriate provider based on model names and settings.
"""

from __future__ import annotations

import logging
from typing import Dict

from config.image.aliases import resolve_image_model_alias
from core.exceptions import ConfigurationError
from core.providers.registry import get_model_config
from core.providers.registries import (
    _image_providers,
    _text_providers,
    _tts_providers,
    _video_providers,
)
from core.providers.tts.utils._elevenlabs_helpers import VOICE_NAME_TO_ID, KNOWN_VOICE_IDS

logger = logging.getLogger(__name__)


def get_text_provider(settings: Dict[str, object]) -> "BaseTextProvider":
    """Return a text provider instance using the model registry for resolution."""

    text_settings = settings.get("text", {}) if settings else {}
    model = str(text_settings.get("model", "gpt-4o-mini"))
    enable_reasoning = bool(text_settings.get("enable_reasoning", False))

    model_config = get_model_config(model, enable_reasoning=enable_reasoning)
    provider_name = model_config.provider_name.lower()

    if provider_name not in _text_providers:
        raise ConfigurationError(
            f"Provider {provider_name} not registered. Available: {list(_text_providers.keys())}",
            key=f"provider.{provider_name}",
        )

    provider_class = _text_providers[provider_name]
    provider = provider_class()
    if hasattr(provider, "set_model_config"):
        provider.set_model_config(model_config)
    return provider


def get_image_provider(settings: Dict[str, object]) -> "BaseImageProvider":
    """Return an image provider instance based on the requested model."""

    image_settings: Dict[str, object] = {}
    if isinstance(settings, dict):
        maybe_image_settings = settings.get("image", {})
        if isinstance(maybe_image_settings, dict):
            image_settings = maybe_image_settings

    requested_model = str(image_settings.get("model", "openai"))
    resolved_model = resolve_image_model_alias(requested_model)
    normalized_model = resolved_model.lower()

    logger.info(
        "Getting image provider for model: %s (requested=%s)",
        normalized_model,
        requested_model,
    )

    if (
        normalized_model.startswith("openai")
        or normalized_model.startswith("dall-e")
        or normalized_model.startswith("gpt-image")
    ):
        provider_name = "openai"
    elif normalized_model.startswith("flux"):
        provider_name = "flux"
    elif (
        normalized_model.startswith("sd")
        or normalized_model.startswith("stability")
        or normalized_model == "core"
    ):
        provider_name = "stability"
    elif normalized_model.startswith("gemini") or normalized_model.startswith("imagen"):
        provider_name = "gemini"
    elif normalized_model.startswith("grok"):
        provider_name = "xai"
    else:
        raise ConfigurationError(
            f"Unknown image model: {requested_model}", key="image.model"
        )

    if provider_name not in _image_providers:
        raise ConfigurationError(
            f"Image provider {provider_name} not registered. Available: {list(_image_providers.keys())}",
            key=f"provider.{provider_name}",
        )

    provider_class = _image_providers[provider_name]
    logger.debug(
        "Resolved image provider instance %s for provider name %s",
        provider_class.__name__,
        provider_name,
    )
    return provider_class()


def _infer_tts_provider_from_model(model: str) -> str:
    """Return a provider name derived from a requested TTS model string."""

    if not model:
        return "openai"

    if model.startswith("eleven") or model.startswith("xi-"):
        return "elevenlabs"
    if "eleven" in model:
        return "elevenlabs"
    return "openai"


def _is_elevenlabs_voice(voice: str) -> bool:
    """Check if a voice is a known ElevenLabs voice.

    This mirrors the legacy behavior from getTTSModelForVoice() which checked
    if the voice name exists in the ElevenLabs available voices list.

    Args:
        voice: Voice name or voice ID to check.

    Returns:
        True if the voice is a known ElevenLabs voice, False otherwise.
    """
    if not voice:
        return False

    # Check by lowercase voice name (as stored in VOICE_NAME_TO_ID)
    lookup_key = voice.lower().strip()
    if lookup_key in VOICE_NAME_TO_ID:
        return True

    # Also check if it's a known ElevenLabs voice ID
    if voice.strip() in KNOWN_VOICE_IDS:
        return True

    return False


def get_tts_provider(settings: Dict[str, object]) -> "BaseTTSProvider":
    """Return a text-to-speech provider instance based on requested settings.

    Provider selection follows this priority order:
    1. Explicit provider name if specified
    2. Voice-based selection (if voice is a known ElevenLabs voice, use ElevenLabs)
    3. Model-based inference (e.g., model contains "eleven" -> ElevenLabs)
    4. Default to OpenAI

    This matches the legacy behavior where voice had precedence over model,
    allowing users to select an OpenAI model but still use ElevenLabs voices.
    """

    tts_settings = settings.get("tts", {}) if settings else {}
    if not isinstance(tts_settings, dict):
        tts_settings = {}

    provider_name = str(tts_settings.get("provider", "")).strip().lower()
    model = str(tts_settings.get("model", "")).strip().lower()
    voice = str(tts_settings.get("voice", "")).strip()

    if not provider_name:
        # Voice-based provider selection takes precedence over model-based
        # This matches legacy behavior from getTTSModelForVoice()
        if _is_elevenlabs_voice(voice):
            provider_name = "elevenlabs"
            logger.debug(
                "TTS provider resolved from voice '%s' -> elevenlabs (voice takes precedence over model '%s')",
                voice,
                model,
            )
        else:
            provider_name = _infer_tts_provider_from_model(model)

    if provider_name not in _tts_providers:
        raise ConfigurationError(
            f"TTS provider {provider_name} not registered. Available: {list(_tts_providers.keys())}",
            key=f"provider.{provider_name}",
        )

    provider_class = _tts_providers[provider_name]
    provider = provider_class()
    logger.debug(
        "Resolved tts provider instance %s for provider name %s",
        provider_class.__name__,
        provider_name,
    )

    if hasattr(provider, "configure"):
        provider.configure(tts_settings)

    return provider


def get_video_provider(settings: Dict[str, object]) -> "BaseVideoProvider":
    """Return a video provider instance based on the requested model."""

    video_settings = settings.get("video", {}) if settings else {}
    model = str(video_settings.get("model", "veo-3.1-fast")).lower()
    logger.info("Getting video provider for model: %s", model)

    if model.startswith("kling"):
        provider_name = "klingai"
    elif model.startswith("veo") or model.startswith("gemini"):
        provider_name = "gemini"
    elif model.startswith("sora") or model.startswith("openai"):
        provider_name = "openai"
    else:
        raise ConfigurationError(f"Unknown video model: {model}", key="video.model")

    if provider_name not in _video_providers:
        raise ConfigurationError(
            f"Video provider {provider_name} not registered. Available: {list(_video_providers.keys())}",
            key=f"provider.{provider_name}",
        )

    provider_class = _video_providers[provider_name]
    logger.debug(
        "Resolved video provider instance %s for provider name %s",
        provider_class.__name__,
        provider_name,
    )
    return provider_class()
