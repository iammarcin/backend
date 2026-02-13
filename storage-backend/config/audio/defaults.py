"""Audio/STT configuration defaults."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


from .models import GEMINI_SPEECH_MODEL_ALIASES
from .providers import deepgram, gemini as gemini_config
from .utils import normalise_gemini_model
from core.utils.env import is_production

logger = logging.getLogger(__name__)

# Global audio defaults (previously in core.config)
DEFAULT_TRANSCRIBE_MODEL = "gemini-2.5-flash"
DEFAULT_TRANSLATE_MODEL = "gemini-2.5-flash"
DEFAULT_TRANSCRIBE_PROVIDER = "gemini"
DEFAULT_TRANSLATE_PROVIDER = "gemini"

# Model aliases (migrated from features/audio/settings.py)
DEEPGRAM_STREAMING_MODELS = {
    "nova-3",
    "nova-3-general",
    "nova-2",
    "nova-2-general",
    "nova-2-conversationalai",
    "nova-2-voicemail",
    "nova-2-phonecall",
    "deepgram-nova-3",
    "deepgram-nova-2",
}

DEEPGRAM_MODEL_ALIASES: Dict[str, str] = {
    "deepgram-nova-3": "nova-3",
    "deepgram-nova-2": "nova-2",
}

OPENAI_SPEECH_MODEL_ALIASES: Dict[str, str] = {
    "gpt-4o-transcribe": "gpt-4o-audio-preview",
    "whisper-1": "whisper-1",
}


def _deepgram_alias_lookup(model_name: str) -> Optional[str]:
    """Resolve Deepgram alias names."""

    alias = DEEPGRAM_MODEL_ALIASES.get(model_name)
    if alias:
        return alias
    if model_name.startswith("deepgram-"):
        stripped = model_name.replace("deepgram-", "", 1)
        if stripped in DEEPGRAM_STREAMING_MODELS:
            return stripped
    if model_name in DEEPGRAM_STREAMING_MODELS:
        return model_name
    return None


def normalise_deepgram_model(candidate: str | None) -> str:
    """Resolve Deepgram model aliases and fall back to defaults if unsupported."""

    if candidate is None:
        return deepgram.DEFAULT_MODEL

    model_name = str(candidate).strip().lower()
    if not model_name:
        return deepgram.DEFAULT_MODEL

    resolved = _deepgram_alias_lookup(model_name)
    if resolved:
        return resolved

    logger.debug(
        "Unsupported Deepgram model '%s' supplied; using fallback '%s'",
        model_name,
        deepgram.DEFAULT_MODEL,
    )
    return deepgram.DEFAULT_MODEL


def _get_openai_streaming_models():
    # Lazy import to avoid circular dependency with audio providers
    from config.audio.providers.openai import STREAMING_TRANSCRIPTION_MODEL_NAMES
    return set(STREAMING_TRANSCRIPTION_MODEL_NAMES)

# Make this a lazy property to avoid circular imports
_OPENAI_STREAMING_MODELS = None

def get_openai_streaming_models():
    global _OPENAI_STREAMING_MODELS
    if _OPENAI_STREAMING_MODELS is None:
        _OPENAI_STREAMING_MODELS = _get_openai_streaming_models()
    return _OPENAI_STREAMING_MODELS

# Make STREAMING_AVAILABLE_MODELS lazy to avoid circular imports
_STREAMING_AVAILABLE_MODELS = None

def get_streaming_available_models():
    """Get all available streaming models (lazy evaluation to avoid circular imports)."""
    global _STREAMING_AVAILABLE_MODELS
    if _STREAMING_AVAILABLE_MODELS is None:
        _STREAMING_AVAILABLE_MODELS = (
            set(DEEPGRAM_STREAMING_MODELS)
            | set(DEEPGRAM_MODEL_ALIASES.keys())
            | {model.lower() for model in GEMINI_SPEECH_MODEL_ALIASES.keys()}
            | get_openai_streaming_models()
        )
    return _STREAMING_AVAILABLE_MODELS



@dataclass(slots=True)
class StreamingProviderSettings:
    """Centralised configuration for streaming audio transcription providers."""

    model: str = deepgram.DEFAULT_MODEL
    language: str = deepgram.DEFAULT_LANGUAGE
    encoding: str = "linear16"
    sample_rate: int = gemini_config.DEFAULT_SAMPLE_RATE
    recording_sample_rate: int = gemini_config.DEFAULT_RECORDING_RATE
    channels: int = 1
    punctuate: bool = True
    interim_results: bool = False
    numerals: bool = True
    profanity_filter: bool = False
    provider: str = field(default="deepgram", init=False)
    buffer_duration_seconds: float = gemini_config.DEFAULT_BUFFER_DURATION
    optional_prompt: str | None = None

    def update_from_payload(self, settings_dict: Mapping[str, Any] | None) -> None:
        """Apply overrides from incoming payload dictionaries."""

        if not isinstance(settings_dict, Mapping):
            logger.warning("Invalid STT settings payload received: %s", settings_dict)
            return

        speech_settings = settings_dict.get("speech")
        payload: Mapping[str, Any]
        if isinstance(speech_settings, Mapping):
            payload = speech_settings
        else:
            payload = settings_dict

        self.sample_rate = int(payload.get("sample_rate", self.sample_rate))
        self.recording_sample_rate = int(
            payload.get("recording_sample_rate", self.recording_sample_rate)
        )
        self.language = str(payload.get("language", self.language))
        self.encoding = str(payload.get("encoding", self.encoding))
        self.channels = int(payload.get("channels", self.channels))
        self.punctuate = bool(payload.get("punctuate", self.punctuate))
        self.interim_results = bool(payload.get("interim_results", self.interim_results))
        self.numerals = bool(payload.get("numerals", self.numerals))
        self.profanity_filter = bool(payload.get("profanity_filter", self.profanity_filter))

        buffer_override = payload.get("buffer_duration_seconds")
        if buffer_override is None and "bufferDurationSeconds" in payload:
            buffer_override = payload.get("bufferDurationSeconds")
        if buffer_override is not None:
            try:
                self.buffer_duration_seconds = float(buffer_override)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid buffer duration '%s', keeping %s",
                    buffer_override,
                    self.buffer_duration_seconds,
                )

        optional_prompt_value = payload.get("optional_prompt")
        if optional_prompt_value is None and "optionalPrompt" in payload:
            optional_prompt_value = payload.get("optionalPrompt")
        if optional_prompt_value is not None:
            self.optional_prompt = str(optional_prompt_value) or None

        provider_hint = payload.get("provider")
        if provider_hint:
            provider_candidate = (
                str(provider_hint).strip().lower().replace("-", "_")
            )
            if provider_candidate in {"gemini", "gemini_streaming"}:
                self.provider = "gemini"
            elif provider_candidate:
                self.provider = provider_candidate

        provided_model = payload.get("model")
        if provided_model:
            cleaned_parts = [
                part
                for part in str(provided_model).replace("_", "-").split("-")
                if part and part.lower() != "stt"
            ]
            model_name = "-".join(cleaned_parts)
            model_lower = model_name.lower()

            if model_lower.startswith("gemini"):
                resolved_model = normalise_gemini_model(model_name, production=is_production())
                if resolved_model != self.model:
                    logger.debug(
                        "Configured Gemini streaming model '%s' (resolved from '%s')",
                        resolved_model,
                        provided_model,
                    )
                self.model = resolved_model
                self.provider = "gemini"
            elif model_lower in get_openai_streaming_models():
                if model_lower != self.model:
                    logger.debug(
                        "Configured OpenAI streaming model '%s' (resolved from '%s')",
                        model_lower,
                        provided_model,
                    )
                self.model = model_lower
                self.provider = "openai"
            elif model_lower.startswith("deepgram") or model_name in DEEPGRAM_STREAMING_MODELS:
                resolved_model = normalise_deepgram_model(model_name)
                if resolved_model != self.model:
                    logger.debug(
                        "Configured Deepgram streaming model '%s' (resolved from '%s')",
                        resolved_model,
                        provided_model,
                    )
                self.model = resolved_model
                self.provider = "deepgram"
            else:
                logger.warning(
                    "Unknown streaming model '%s', falling back to %s",
                    model_name,
                    self.model,
                )

        logger.info(
            "Configured STT settings (model=%s, language=%s, sample_rate=%s, recording_rate=%s, interim_results=%s)",
            self.model,
            self.language,
            self.sample_rate,
            self.recording_sample_rate,
            self.interim_results,
        )

    def to_provider_dict(self) -> Dict[str, Any]:
        """Return the provider configuration for streaming APIs."""

        payload: Dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "language": self.language,
            "encoding": self.encoding,
            "sample_rate": self.sample_rate,
            "recording_sample_rate": self.recording_sample_rate,
            "channels": self.channels,
            "punctuate": self.punctuate,
            "interim_results": self.interim_results,
            "numerals": self.numerals,
            "profanity_filter": self.profanity_filter,
        }
        if self.provider == "gemini":
            payload["buffer_duration_seconds"] = self.buffer_duration_seconds
            if self.optional_prompt:
                payload["optional_prompt"] = self.optional_prompt
        return payload


def is_openai_streaming_model(model: str) -> bool:
    """Return True when ``model`` is registered as an OpenAI transcription model."""

    from config.audio.providers.openai import STREAMING_TRANSCRIPTION_MODEL_NAMES
    return str(model).strip().lower() in STREAMING_TRANSCRIPTION_MODEL_NAMES


__all__ = [
    "DEFAULT_TRANSCRIBE_MODEL",
    "DEFAULT_TRANSLATE_MODEL",
    "DEFAULT_TRANSCRIBE_PROVIDER",
    "DEFAULT_TRANSLATE_PROVIDER",
    "DEEPGRAM_MODEL_ALIASES",
    "GEMINI_SPEECH_MODEL_ALIASES",
    "OPENAI_SPEECH_MODEL_ALIASES",
    "StreamingProviderSettings",
    "is_openai_streaming_model",
    "normalise_deepgram_model",
]
