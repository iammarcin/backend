"""Static transcription workflow orchestration used by :class:`STTService`.

The workflow coordinates provider selection, metrics reporting, and
completion signalling while delegating smaller formatting tasks to
``static_support``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from core.exceptions import ProviderError, ServiceError
from core.observability import record_transcription_failure, record_transcription_success
from core.providers.audio.factory import get_audio_provider as _get_audio_provider
from core.providers.audio.base import SpeechTranscriptionResult
from core.streaming.manager import StreamingManager
from features.audio.schemas import (
    AudioAction,
    StaticTranscriptionUserInput,
    StaticTranscriptionUserSettings,
)
from features.audio.static_support import (
    StaticTranscriptionResult,
    build_provider_settings,
    build_request_payload,
    build_static_result,
    emit_completion_event,
    resolve_filename,
    resolve_prompt,
)

logger = logging.getLogger(__name__)


async def execute_static_transcription(
    *,
    action: AudioAction,
    customer_id: int,
    file_path: Path | str | None,
    filename: str | None,
    file_bytes: bytes | None,
    content_type: str | None,
    user_input: StaticTranscriptionUserInput | None,
    user_settings: StaticTranscriptionUserSettings,
    manager: StreamingManager | None,
    completion_token: str | None = None,
    provider_factory: Callable[[Dict[str, Any], str], Any] | None = None,
    transcript_rewriter: Callable[[str, Mapping[str, Any] | None], str] | None = None,
) -> StaticTranscriptionResult:
    """Run the full static transcription workflow and return the result."""

    resolved_path = Path(file_path) if file_path else None
    label = resolve_filename(
        filename=filename,
        file_path=resolved_path,
        user_input=user_input,
    )

    completion_signalled = False
    try:
        if user_settings.general.return_test_data:
            transcript = f"Test transcript for customer {customer_id} using {action.value}."
            result = StaticTranscriptionResult(
                status="completed",
                result=transcript,
                action=action,
                provider="test-data",
                filename=label,
                language=user_settings.speech.language,
                metadata={"mode": "test"},
            )
            if manager is not None:
                await emit_completion_event(manager, result)
                if completion_token is not None:
                    await manager.signal_completion(token=completion_token)
                completion_signalled = True
            return result

        provider_settings = build_provider_settings(action=action, user_settings=user_settings)
        prompt = resolve_prompt(user_input=user_input, user_settings=user_settings)
        factory = provider_factory or _get_audio_provider
        provider = factory({"audio": provider_settings}, action=action.value)

        request_payload = build_request_payload(
            provider_settings=provider_settings,
            resolved_path=resolved_path,
            file_bytes=file_bytes,
            filename=label,
            speech_settings=user_settings,
            content_type=content_type,
            prompt=prompt,
            customer_id=customer_id,
            action=action,
        )

        if manager is not None:
            await manager.send_to_queues(
                {
                    "type": "custom_event",
                    "event_type": "transcriptionStarted",
                    "content": {
                        "customer_id": customer_id,
                        "filename": label,
                        "provider": provider_settings.get("provider"),
                        "action": action.value,
                    },
                }
            )

        start_time = time.perf_counter()
        try:
            if action is AudioAction.TRANSLATE:
                provider_result = await provider.translate_file(request_payload)
            else:
                provider_result = await provider.transcribe_file(request_payload)
        except ProviderError as exc:
            elapsed = time.perf_counter() - start_time
            record_transcription_failure(
                provider=exc.provider or provider_settings.get("provider"),
                model=provider_settings.get("model"),
                action=action.value,
                customer_id=customer_id,
                filename=label,
                elapsed_seconds=elapsed,
                error=str(exc),
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Static transcription failed: %s", exc, exc_info=True)
            elapsed = time.perf_counter() - start_time
            record_transcription_failure(
                provider=provider_settings.get("provider"),
                model=provider_settings.get("model"),
                action=action.value,
                customer_id=customer_id,
                filename=label,
                elapsed_seconds=elapsed,
                error=str(exc),
            )
            raise ServiceError(f"Static transcription failed: {exc}") from exc

        rewrite_context: Mapping[str, Any] = {
            "provider": provider_result.provider or provider_settings.get("provider"),
            "model": provider_settings.get("model"),
            "action": action.value,
            "customer_id": customer_id,
            "mode": "static",
        }

        if transcript_rewriter is not None:
            rewritten_text = transcript_rewriter(provider_result.text, rewrite_context)
            if rewritten_text != provider_result.text:
                provider_result = SpeechTranscriptionResult(
                    text=rewritten_text,
                    provider=provider_result.provider,
                    language=provider_result.language,
                    duration_seconds=provider_result.duration_seconds,
                    metadata=provider_result.metadata,
                )

        result = build_static_result(
            provider_result,
            action=action,
            filename=label,
            fallback_provider=provider_settings.get("provider", "unknown"),
        )

        elapsed = time.perf_counter() - start_time
        record_transcription_success(
            provider=result.provider,
            model=provider_settings.get("model"),
            action=action.value,
            customer_id=customer_id,
            filename=label,
            duration_seconds=provider_result.duration_seconds,
            elapsed_seconds=elapsed,
            language=result.language,
            metadata=provider_result.metadata,
        )

        if manager is not None:
            await emit_completion_event(
                manager,
                result,
                transcript_text=provider_result.text,
            )
            if completion_token is not None:
                await manager.signal_completion(token=completion_token)
            completion_signalled = True

        return result
    finally:
        if (
            manager is not None
            and completion_token is not None
            and not completion_signalled
        ):
            await manager.signal_completion(token=completion_token)


__all__ = ["execute_static_transcription", "StaticTranscriptionResult"]
