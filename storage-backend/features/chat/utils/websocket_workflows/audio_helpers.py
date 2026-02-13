"""Helper functions for audio workflow processing.

This module contains helper functions extracted from the main audio workflow:
- Transcription handling
- Early exit condition checking
- Standard workflow processing
- Prompt merging
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.exceptions import ServiceError
from core.streaming.manager import StreamingManager
from features.audio.service import STTService
from features.chat.service import ChatService
from features.chat.utils.prompt_utils import PromptInput
from features.chat.utils.system_prompt import resolve_system_prompt
from features.semantic_search.prompt_enhancement import (
    enhance_prompt_with_semantic_context,
)

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

logger = logging.getLogger(__name__)


async def transcribe_audio(
    stt_service: STTService,
    audio_source: Any,
    manager: StreamingManager,
    mode: str,
) -> str:
    """Transcribe audio stream.

    Args:
        stt_service: Speech-to-text service
        audio_source: Audio source iterator
        manager: Streaming manager for error events
        mode: Transcription mode

    Returns:
        Transcribed text

    Raises:
        ServiceError: If transcription fails
    """
    try:
        return await stt_service.transcribe_stream(
            audio_source=audio_source,
            manager=manager,
            mode=mode,
        )
    except ServiceError:
        await manager.send_to_queues(
            {"type": "error", "content": "Transcription failed", "stage": "stt"}
        )
        raise


async def handle_empty_transcription(
    customer_id: int,
    mode: str,
    timings: Dict[str, float],
    manager: StreamingManager,
) -> Dict[str, Any]:
    """Handle case when transcription is empty.

    Args:
        customer_id: Customer ID for logging
        mode: Transcription mode
        timings: Timing dict with stt timestamps
        manager: Streaming manager for error events

    Returns:
        Error response dict
    """
    logger.warning(
        "Transcription completed but produced no text (customer=%s, mode=%s, duration=%.2fs)",
        customer_id,
        mode,
        timings["stt_response_time"] - timings["stt_request_sent_time"],
    )
    await manager.send_to_queues(
        {
            "type": "error",
            "content": "No speech detected in recording. Please try again.",
            "stage": "transcription",
        }
    )
    return {
        "success": False,
        "error": "empty_transcript",
        "user_transcript": "",
    }


async def send_transcription_complete(
    manager: StreamingManager,
    transcription: str,
    user_input: Optional[Dict[str, Any]],
    runtime: Optional["WorkflowRuntime"],
) -> None:
    """Send transcription complete event.

    Args:
        manager: Streaming manager
        transcription: Transcribed text
        user_input: User input dict (may contain recording_id)
        runtime: Workflow runtime (may contain recording_id)
    """
    recording_id = None
    if runtime is not None:
        recording_id = runtime.get_recording_id()
    if recording_id is None:
        recording_id = (user_input or {}).get("recording_id")

    await manager.send_to_queues(
        {
            "type": "transcription_complete",
            "content": transcription,
            "recording_id": recording_id,
        }
    )


def check_early_exit(
    settings: Dict[str, Any],
    customer_id: int,
    transcription: str,
) -> Optional[Dict[str, Any]]:
    """Check for early exit conditions (bug report, auto_response disabled).

    Args:
        settings: User settings
        customer_id: Customer ID for logging
        transcription: Transcribed text

    Returns:
        Response dict if early exit, None otherwise
    """
    # Check if this is a bug report
    is_bug_report = settings.get("text", {}).get("bug_report", False)
    if is_bug_report:
        logger.info(
            "Bug report mode detected - skipping text generation (customer=%s)",
            customer_id,
        )
        return {
            "success": True,
            "bug_report": True,
            "user_transcript": transcription,
        }

    # Check if auto_response is disabled
    auto_response = settings.get("general", {}).get("auto_response", True)
    if not auto_response:
        logger.info(
            "Auto-response disabled - saving message without AI response (customer=%s)",
            customer_id,
        )
        return {
            "success": True,
            "user_transcript": transcription,
        }

    return None


async def handle_standard_workflow(
    *,
    prompt: PromptInput,
    transcription: str,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    service: ChatService,
    timings: Dict[str, float],
    user_input: Optional[Dict[str, Any]],
    session_id: Optional[str],
) -> Dict[str, Any]:
    """Handle standard audio workflow with text generation.

    Args:
        prompt: Original prompt
        transcription: Transcribed text
        settings: User settings
        customer_id: Customer ID
        manager: Streaming manager
        service: Chat service
        timings: Timing dict
        user_input: User input dict
        session_id: Session ID

    Returns:
        Response payload dict
    """
    merged_prompt = merge_transcription_with_prompt(prompt, transcription)

    if user_input is not None:
        user_input["prompt"] = merged_prompt
        logger.debug(
            "Updated user_input['prompt'] with merged transcription for customer %s",
            customer_id,
        )

    # Perform semantic search
    enhancement_result = await enhance_prompt_with_semantic_context(
        prompt=merged_prompt,
        customer_id=customer_id,
        user_settings=settings,
        manager=manager,
        current_session_id=session_id,
    )

    if enhancement_result.context_added:
        logger.info(
            "Audio prompt enhanced with %s semantic results (%s tokens)",
            enhancement_result.result_count,
            enhancement_result.tokens_used,
        )
        merged_prompt = enhancement_result.enhanced_prompt
    elif enhancement_result.error:
        logger.warning(
            "Semantic search failed for audio workflow (customer=%s): %s",
            customer_id,
            enhancement_result.error,
        )

    system_prompt = resolve_system_prompt(settings)

    response_payload = await service.stream_response(
        prompt=merged_prompt,
        settings=settings,
        customer_id=customer_id,
        manager=manager,
        system_prompt=system_prompt,
        timings=timings,
        user_input=user_input,
    )

    if transcription:
        response_payload.setdefault("user_transcript", transcription)

    return response_payload


def merge_transcription_with_prompt(
    prompt: PromptInput, transcription: str
) -> PromptInput:
    """Insert transcription text into structured prompt payload.

    Args:
        prompt: Original prompt (string or list)
        transcription: Transcribed text to insert

    Returns:
        Merged prompt with transcription
    """
    transcription = (transcription or "").strip()
    if not transcription:
        return prompt

    if isinstance(prompt, list):
        items: List[Any] = []
        items.append({"type": "text", "text": transcription})

        for item in prompt:
            if hasattr(item, "model_dump"):
                item_data = item.model_dump()
            else:
                item_data = item

            if not isinstance(item_data, dict):
                continue

            if item_data.get("type") == "text":
                continue
            items.append(item_data)

        return items

    return transcription
