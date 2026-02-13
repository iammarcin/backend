"""Shared helpers for static speech-to-text transcription workflows.

These utilities isolate reusable data structures and formatting helpers used
by the higher-level orchestration logic in :mod:`static_workflow`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from config.audio import (
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TRANSCRIBE_PROVIDER,
    DEFAULT_TRANSLATE_MODEL,
    DEFAULT_TRANSLATE_PROVIDER,
)
from core.providers.audio.base import SpeechProviderRequest, SpeechTranscriptionResult
from core.providers.audio.config import normalise_gemini_model
from core.streaming.manager import StreamingManager
from core.utils.env import is_production
from features.audio.schemas import (
    AudioAction,
    StaticTranscriptionUserInput,
    StaticTranscriptionUserSettings,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StaticTranscriptionResult:
    """Container for static transcription responses."""

    status: str
    result: str
    action: AudioAction
    provider: str
    filename: str | None = None
    language: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def resolve_filename(
    *,
    filename: str | None,
    file_path: Path | None,
    user_input: StaticTranscriptionUserInput | None,
) -> str:
    """Determine the display name used when reporting transcription progress."""

    if filename:
        return filename
    if user_input and user_input.file_name:
        return user_input.file_name
    if file_path:
        return file_path.name
    return "recording"


def resolve_prompt(
    *,
    user_input: StaticTranscriptionUserInput | None,
    user_settings: StaticTranscriptionUserSettings,
) -> str | None:
    """Return the optional prompt sent to the transcription provider."""

    speech_prompt = user_settings.speech.optional_prompt
    if speech_prompt:
        return speech_prompt
    if user_input and user_input.prompt:
        return user_input.prompt
    return None


def infer_provider(
    model: str | None, *, default: str, action: AudioAction | None = None
) -> str:
    """Best-effort inference of the provider responsible for ``model``.

    For static transcription actions, Deepgram is automatically replaced with a
    Gemini fallback because the Deepgram provider only supports streaming
    transcription.
    """

    model_lower = (model or "").lower()
    inferred = default

    if model_lower.startswith(("gemini", "imagen")):
        inferred = "gemini"
    elif model_lower.startswith(("gpt", "whisper", "openai")):
        inferred = "openai"
    elif model_lower.startswith(("deepgram", "nova")):
        inferred = "deepgram"

    if action in {AudioAction.TRANSCRIBE, AudioAction.TRANSLATE, AudioAction.CHAT}:
        if inferred == "deepgram":
            logger.warning(
                "Model '%s' implies Deepgram provider, but Deepgram doesn't support "
                "static transcription (action=%s). Falling back to Gemini.",
                model,
                action.value if action else "unknown",
            )
            return "gemini"

    return inferred


def build_provider_settings(
    *,
    action: AudioAction,
    user_settings: StaticTranscriptionUserSettings,
) -> Dict[str, Any]:
    """Compose the provider configuration for static transcription calls."""

    speech = user_settings.speech
    default_model = (
        DEFAULT_TRANSLATE_MODEL
        if action is AudioAction.TRANSLATE
        else DEFAULT_TRANSCRIBE_MODEL
    )
    requested_model = speech.model
    model_hint = requested_model or default_model
    default_provider = (
        DEFAULT_TRANSLATE_PROVIDER
        if action is AudioAction.TRANSLATE
        else DEFAULT_TRANSCRIBE_PROVIDER
    )
    provider_name = infer_provider(model_hint, default=default_provider, action=action)
    if provider_name == "gemini":
        normalised_model = normalise_gemini_model(requested_model, production=is_production())
        if normalised_model != (requested_model or model_hint):
            logger.debug(
                "Normalised Gemini model from '%s' to '%s' for static action %s",
                requested_model or model_hint,
                normalised_model,
                action.value,
            )
        model = normalised_model
    else:
        model = model_hint
    return {
        "model": model,
        "provider": provider_name,
        "language": speech.language,
        "temperature": speech.temperature,
        "response_format": speech.response_format,
    }


def build_request_payload(
    *,
    provider_settings: Dict[str, Any],
    resolved_path: Path | None,
    file_bytes: bytes | None,
    filename: str,
    speech_settings: StaticTranscriptionUserSettings,
    content_type: str | None,
    prompt: str | None,
    customer_id: int,
    action: AudioAction,
) -> SpeechProviderRequest:
    """Construct the request payload consumed by the provider implementation."""

    return SpeechProviderRequest(
        file_path=resolved_path,
        file_bytes=file_bytes,
        filename=filename,
        model=provider_settings.get("model"),
        language=speech_settings.speech.language,
        temperature=speech_settings.speech.temperature,
        response_format=speech_settings.speech.response_format,
        prompt=prompt,
        mime_type=content_type,
        metadata={"customer_id": customer_id, "action": action.value},
    )


def build_static_result(
    provider_result: SpeechTranscriptionResult,
    *,
    action: AudioAction,
    filename: str,
    fallback_provider: str,
) -> StaticTranscriptionResult:
    """Wrap provider responses into :class:`StaticTranscriptionResult`."""

    metadata: Dict[str, Any] = dict(provider_result.metadata or {})
    if provider_result.duration_seconds is not None:
        metadata.setdefault("duration_seconds", provider_result.duration_seconds)
    return StaticTranscriptionResult(
        status="completed",
        result=provider_result.text,
        action=action,
        provider=provider_result.provider or fallback_provider,
        filename=filename,
        language=provider_result.language,
        metadata=metadata,
    )


async def emit_completion_event(
    manager: StreamingManager,
    result: StaticTranscriptionResult,
    *,
    transcript_text: str | None = None,
) -> None:
    """Publish a completion event that mirrors the legacy streaming flow."""

    payload = {
        "type": "custom_event",
        "event_type": "transcriptionCompleted",
        "content": {
            "status": result.status,
            "provider": result.provider,
            "filename": result.filename,
            "language": result.language,
            "metadata": result.metadata,
            "transcript": transcript_text or result.result,
        },
    }
    await manager.send_to_queues(payload)


__all__ = [
    "StaticTranscriptionResult",
    "build_provider_settings",
    "build_request_payload",
    "build_static_result",
    "emit_completion_event",
    "infer_provider",
    "resolve_filename",
    "resolve_prompt",
]
