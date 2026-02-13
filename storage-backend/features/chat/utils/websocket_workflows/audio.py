"""Audio + transcription websocket workflow handlers."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from fastapi import WebSocket

from core.streaming.manager import StreamingManager
from features.audio.service import STTService
from features.chat.service import ChatService
from features.chat.utils.prompt_utils import PromptInput

from .audio_helpers import (
    check_early_exit,
    handle_empty_transcription,
    merge_transcription_with_prompt,
    send_transcription_complete,
    transcribe_audio,
)
from .audio_routing import route_to_openclaw

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

logger = logging.getLogger(__name__)


async def handle_audio_workflow(
    *,
    websocket: WebSocket,
    prompt: PromptInput,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    service: ChatService,
    stt_service: STTService,
    timings: Dict[str, float],
    completion_token: str | None = None,
    user_input: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    runtime: "WorkflowRuntime | None" = None,
) -> Dict[str, Any]:
    """Handle audio -> transcription -> text workflow.

    This is the main entry point for audio workflows. It:
    1. Transcribes audio from the websocket
    2. Routes to OpenClaw Gateway unconditionally
    3. Returns the workflow result

    Args:
        websocket: WebSocket connection for audio data
        prompt: Original prompt (may contain attachments)
        settings: User settings
        customer_id: Customer ID
        manager: Streaming manager for events
        service: Chat service for text generation
        stt_service: Speech-to-text service
        timings: Dict for timing measurements
        completion_token: Token for signaling completion
        user_input: User input payload
        session_id: Session ID
        runtime: Workflow runtime

    Returns:
        Workflow result dict
    """
    stt_service.configure(settings)
    audio_source = stt_service.websocket_audio_source(websocket, runtime=runtime)

    mode = str(settings.get("speech", {}).get("mode", "non-realtime"))
    timings["stt_request_sent_time"] = time.time()

    logger.info("Audio workflow configured (customer=%s, mode=%s)", customer_id, mode)

    try:
        # Transcribe audio
        transcription = await transcribe_audio(stt_service, audio_source, manager, mode)
        timings["stt_response_time"] = time.time()

        # Validate transcription
        if not (transcription or "").strip():
            return await handle_empty_transcription(customer_id, mode, timings, manager)

        logger.info(
            "Transcription completed for customer %s (chars=%s)",
            customer_id,
            len(transcription),
        )

        # Resolve routing context
        from features.chat.utils.history_metadata import _resolve_ai_character_name

        ai_character_name = _resolve_ai_character_name(user_input or {}, settings)

        if runtime is not None:
            runtime.allow_disconnect()

        # Send transcription complete event
        await send_transcription_complete(manager, transcription, user_input, runtime)

        # Check early exit conditions
        early_exit = check_early_exit(settings, customer_id, transcription)
        if early_exit is not None:
            return early_exit

        logger.info(
            "Audio routing to OpenClaw (customer=%s, character=%s)",
            customer_id,
            ai_character_name,
        )

        # Route to OpenClaw unconditionally
        return await route_to_openclaw(
            transcription=transcription,
            customer_id=customer_id,
            settings=settings,
            ai_character_name=ai_character_name,
            user_input=user_input,
            session_id=session_id,
            manager=manager,
        )

    finally:
        if completion_token is not None:
            await manager.send_to_queues({"type": "text_completed", "content": ""})
            await manager.send_to_queues({"type": "tts_not_requested", "content": ""})
            await manager.signal_completion(token=completion_token)


__all__ = ["handle_audio_workflow", "merge_transcription_with_prompt"]
