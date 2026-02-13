"""High-level orchestration for chat streaming workflows.

The functions in this module coordinate prompt resolution, provider
interaction, and the emission of downstream events.  Lower-level concerns such
as provider-specific streaming loops and completion bookkeeping live in the
adjacent helper modules so the public APIs remain concise and easy to follow.
"""

from __future__ import annotations
from .sse import stream_response_chunks
from .non_streaming import generate_response

import logging
import time
from typing import Any, Dict, Optional

from core.exceptions import ProviderError, ValidationError
from core.streaming.manager import StreamingManager

from features.chat.repositories.chat_sessions import ChatSessionRepository
from features.chat.utils.prompt_utils import PromptInput, prompt_preview
from features.chat.utils.chat_history_formatter import (
    extract_and_format_chat_history,
    get_provider_name_from_model,
)
from features.tts.service import TTSService

from .collector import collect_streaming_chunks, StreamCollection
from .completions import emit_completion_events
from .context import resolve_prompt_and_provider
from .payload import build_streaming_payload
from .tts_orchestrator import TTSOrchestrator

logger = logging.getLogger(__name__)


async def stream_response(
    *,
    prompt: PromptInput,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    timings: Optional[Dict[str, float]] = None,
    tts_service: TTSService,
    user_input: Optional[Dict[str, Any]] = None,
    runtime=None,
) -> Dict[str, Any]:
    """Stream an AI response and handle downstream artefacts.

    The function resolves the provider configuration, triggers streaming through
    the appropriate helper, and finally emits completion, image, and TTS events.
    Callers receive a dictionary summarising the generated outputs for further
    processing.
    """

    context, provider, resolved_model, temperature, max_tokens = (
        resolve_prompt_and_provider(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            model=model,
        )
    )

    provider_name = getattr(provider, "provider_name", None) or get_provider_name_from_model(
        resolved_model
    )

    await manager.send_to_queues(
        {
            "type": "custom_event",
            "content": {
                "type": "aiTextModelInUse",
                "message": "aiTextModelReceived",
                "aiTextModel": resolved_model,
                "provider": provider_name,
            },
        }
    )
    logger.debug(
        "Notified frontend of model in use: %s (provider: %s)",
        resolved_model,
        provider_name,
    )

    timings = timings or {}
    timings["text_request_sent_time"] = time.time()

    tts_orchestrator = TTSOrchestrator(
        manager=manager,
        tts_service=tts_service,
        settings=settings,
        customer_id=customer_id,
        timings=timings,
    )

    tts_actually_started = await tts_orchestrator.start_tts_streaming()
    if tts_actually_started:
        logger.info("Parallel TTS streaming enabled (customer=%s)", customer_id)
    else:
        # TTS was requested but validation failed - send fallback so client doesn't hang
        tts_settings = settings.get("tts", {}) if isinstance(settings, dict) else {}
        tts_enabled = bool(tts_settings.get("tts_auto_execute"))
        if tts_enabled:
            logger.warning(
                "TTS requested but orchestrator failed to start (customer=%s) - sending fallback",
                customer_id,
            )
            await manager.send_to_queues({"type": "tts_not_requested", "content": ""})

    logger.debug(
        "Prompt preview for customer %s: '%s'",
        customer_id,
        prompt_preview(prompt),
    )

    session_identifier: Optional[str] = None
    if isinstance(user_input, dict):
        session_identifier = user_input.get("session_id")

    try:
        history_payload: Dict[str, Any] = {}
        if isinstance(user_input, dict):
            history_payload = dict(user_input)

        # Use the incoming prompt parameter (which may be enhanced with semantic context)
        # instead of the original prompt from user_input
        history_payload["prompt"] = prompt

        messages = extract_and_format_chat_history(
            user_input=history_payload,
            system_prompt=system_prompt if provider_name != "anthropic" else None,
            provider_name=provider_name,
            model_name=resolved_model,
        )
        if not messages:
            base_message = {"role": "user", "content": context.text_prompt}
            messages = [base_message]
            if system_prompt and provider_name != "anthropic":
                messages.insert(0, {"role": "system", "content": system_prompt})

        collection: StreamCollection
        deep_research_enabled = bool(
            isinstance(settings, dict)
            and settings.get("text", {}).get("deep_research_enabled")
        )

        if deep_research_enabled:
            collection = await collect_streaming_chunks(
                provider=provider,
                manager=manager,
                prompt_text=context.text_prompt,
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                settings=settings,
                timings=timings,
                user_input=user_input,
                messages=messages,
                customer_id=customer_id,
                session_id=session_identifier,
                runtime=runtime,
            )
        else:
            collection = await collect_streaming_chunks(
                provider=provider,
                manager=manager,
                prompt_text=context.text_prompt,
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                settings=settings,
                timings=timings,
                user_input=user_input,
                messages=messages,
                customer_id=customer_id,
                session_id=session_identifier,
            )

        if collection.is_deep_research and collection.deep_research_metadata:
            metadata_session = collection.deep_research_metadata.get("session_id")
            if isinstance(metadata_session, str):
                session_identifier = metadata_session

        full_text_response = "".join(collection.chunks)
        timings["text_response_time"] = time.time()
        logger.info(
            "Streaming response completed (customer=%s, chunks=%s, response_chars=%s)",
            customer_id,
            len(collection.chunks),
            len(full_text_response),
        )

        # claude_session_id is preserved for proactive agent compatibility
        claude_session_id = collection.claude_session_id
        is_deep_research = collection.is_deep_research

        if collection.requires_tool_action:
            logger.info(
                "Deferring completion events until tool call resolves (customer=%s)",
                customer_id,
            )
        else:
            await emit_completion_events(
                manager=manager,
                customer_id=customer_id,
                full_text_response=full_text_response,
                claude_session_id=claude_session_id,
                is_deep_research=is_deep_research,
            )

        if is_deep_research and session_identifier:
            already_tagged = False
            if collection.deep_research_metadata:
                already_tagged = bool(
                    collection.deep_research_metadata.get("notification_tagged")
                )

            if not already_tagged:
                try:
                    from infrastructure.db.mysql import require_main_session_factory, session_scope
                    session_factory = require_main_session_factory()
                    async with session_scope(session_factory) as db_session:
                        repo = ChatSessionRepository(db_session)
                        await repo.add_notification_tag(
                            session_id=session_identifier,
                            customer_id=customer_id,
                        )
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.error("Failed to add notification tag: %s", exc)

        tts_metadata = await tts_orchestrator.wait_for_completion()

        result = await build_streaming_payload(
            collection=collection,
            full_text_response=full_text_response,
            context=context,
            settings=settings,
            customer_id=customer_id,
            manager=manager,
            timings=timings,
            tts_service=tts_service,
            tts_metadata=tts_metadata,
        )
    except ProviderError:
        await tts_orchestrator.cleanup()
        await manager.send_to_queues(
            {"type": "error", "content": "AI provider error", "stage": "text"}
        )
        raise
    except ValidationError:
        await tts_orchestrator.cleanup()
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        await tts_orchestrator.cleanup()
        logger.error("Unexpected error in stream_response: %s", exc, exc_info=True)
        await manager.send_to_queues(
            {
                "type": "error",
                "content": f"Streaming failed: {exc}",
                "stage": "text",
            }
        )
        raise ProviderError(f"Streaming failed: {exc}") from exc
    else:
        await tts_orchestrator.cleanup()
        return result
    # VERY IMPORTANT - here we cannot just do finally: await manager.signal_completion() - because then - depending on case we experience race condition and websockets stream might be closed before completing whole workflow:


__all__ = ["stream_response", "generate_response", "stream_response_chunks"]
