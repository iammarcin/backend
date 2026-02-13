"""Standard workflow executor for WebSocket dispatcher.

Handles text, audio, audio_direct, and TTS workflows based on the incoming
request type.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from core.streaming.manager import StreamingManager
from features.audio.service import STTService
from features.chat.service import ChatService
from features.chat.utils.history_persistence_bug_report import persist_bug_report
from features.chat.utils.websocket_workflows import (
    handle_audio_direct_workflow,
    handle_audio_workflow,
    handle_text_workflow,
    handle_tts_workflow,
)


logger = logging.getLogger(__name__)


@dataclass
class StandardWorkflowOutcome:
    """Result container for text/audio workflows."""

    success: bool
    result: Dict[str, Any]
    timings: Dict[str, float]
    prompt_for_preview: Optional[Any]
    chart_payloads: List[Dict[str, Any]] = field(default_factory=list)


def _resolve_chart_payloads(result: Any) -> List[Dict[str, Any]]:
    """Normalize chart payloads from workflow result dictionaries."""
    if not isinstance(result, dict):
        return []
    payloads = result.get("chart_payloads")
    if isinstance(payloads, list):
        return [payload for payload in payloads if isinstance(payload, dict)]
    return []


async def run_standard_workflow(
    *,
    request_type: str,
    prompt: Any,
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    service: ChatService,
    stt_service: STTService,
    websocket: WebSocket,
    completion_token: str,
    data: Dict[str, Any],
    prompt_for_preview: Any | None = None,
    session_id: Optional[str] = None,
    workflow_session: Optional[Any] = None,
    runtime=None,
) -> StandardWorkflowOutcome:
    """Execute text or audio workflows based on the incoming payload."""

    preview_payload = prompt if prompt_for_preview is None else prompt_for_preview
    timings: Dict[str, float] = {}
    timings["start_time"] = time.time()

    user_input = data.get("user_input") or {}

    logger_args = {
        "prompt_present": bool(prompt),
        "history_size": len(user_input.get("chat_history", []))
        if isinstance(user_input.get("chat_history"), list)
        else 0,
    }

    logger.debug(
        "Standard workflow received payload (prompt_present=%s, chat_history_size=%s)",
        logger_args["prompt_present"],
        logger_args["history_size"],
    )

    cancelled = False

    try:
        result = None  # Initialize to avoid UnboundLocalError in finally block
        if request_type == "audio" and not prompt:
            prompt = []

        if request_type == "audio":
            result = await handle_audio_workflow(
                websocket=websocket,
                prompt=prompt,
                settings=settings,
                customer_id=customer_id,
                manager=manager,
                service=service,
                stt_service=stt_service,
                timings=timings,
                user_input=user_input,
                session_id=session_id,
                runtime=runtime,
            )
            return StandardWorkflowOutcome(
                success=True,
                result=result,
                timings=timings,
                prompt_for_preview=preview_payload,
                chart_payloads=_resolve_chart_payloads(result),
            )

        if request_type == "audio_direct":
            result = await handle_audio_direct_workflow(
                websocket=websocket,
                prompt=prompt,
                settings=settings,
                customer_id=customer_id,
                manager=manager,
                service=service,
                timings=timings,
                user_input=user_input,
                runtime=runtime,
            )
            return StandardWorkflowOutcome(
                success=result.get("success", True),
                result=result,
                timings=timings,
                prompt_for_preview=preview_payload,
                chart_payloads=_resolve_chart_payloads(result),
            )

        if request_type == "tts":
            result = await handle_tts_workflow(
                prompt=prompt,
                settings=settings,
                customer_id=customer_id,
                manager=manager,
                timings=timings,
                runtime=runtime,
            )
            return StandardWorkflowOutcome(
                success=True,
                result=result,
                timings=timings,
                prompt_for_preview=preview_payload,
                chart_payloads=_resolve_chart_payloads(result),
            )

        result = await handle_text_workflow(
            prompt=prompt,
            settings=settings,
            customer_id=customer_id,
            manager=manager,
            service=service,
            timings=timings,
            user_input=user_input,
            runtime=runtime,
        )

        return StandardWorkflowOutcome(
            success=True,
            result=result,
            timings=timings,
            prompt_for_preview=preview_payload,
            chart_payloads=_resolve_chart_payloads(result),
        )
    except asyncio.CancelledError:
        logger.info(
            "Standard workflow cancelled (request_type=%s, customer=%s)",
            request_type,
            customer_id,
        )
        cancelled = True
        raise
    finally:
        if not cancelled:
            await _handle_workflow_completion(
                result=result,
                workflow_session=workflow_session,
                websocket=websocket,
                data=data,
                settings=settings,
                customer_id=customer_id,
                manager=manager,
                timings=timings,
                preview_payload=preview_payload,
                request_type=request_type,
            )

            await manager.signal_completion(token=completion_token)


async def _handle_workflow_completion(
    *,
    result: Any,
    workflow_session: Any,
    websocket: WebSocket,
    data: Dict[str, Any],
    settings: Dict[str, Any],
    customer_id: int,
    manager: StreamingManager,
    timings: Dict[str, float],
    preview_payload: Any,
    request_type: str,
) -> None:
    """Handle post-workflow completion tasks including persistence and events."""
    # Check if this is a bug report - skip persistence if so
    is_bug_report = isinstance(result, dict) and result.get("bug_report", False)

    # Check if this is a Claude Code character audio workflow - skip persistence
    # (message already saved via proactive agent service, AI response comes via poller)
    is_claude_code_queued = isinstance(result, dict) and result.get("claude_code_queued", False)
    # Check if this is an OpenClaw workflow - skip persistence
    # (messages saved in proactive agent flow)
    is_openclaw = isinstance(result, dict) and result.get("openclaw", False)

    if (
        result is not None
        and workflow_session is not None
        and not is_bug_report
        and not is_claude_code_queued
        and not is_openclaw
    ):
        from .history_persistence_core import persist_workflow_result

        await persist_workflow_result(
            websocket=websocket,
            session=workflow_session,
            request_data=data,
            settings=settings,
            workflow=StandardWorkflowOutcome(
                success=True,
                result=result if isinstance(result, dict) else {},
                timings=timings,
                prompt_for_preview=preview_payload,
                chart_payloads=_resolve_chart_payloads(result),
            ),
            customer_id=customer_id,
            manager=manager,
        )
    elif is_bug_report:
        logger.info(
            "Bug report mode - persisting to dedicated bugsy session (customer=%s)",
            customer_id,
        )
        # Persist bug report to dedicated bugsy session
        transcription = result.get("user_transcript", "")
        if transcription:
            await persist_bug_report(
                customer_id=customer_id,
                transcription=transcription,
            )
    elif is_claude_code_queued:
        logger.info(
            "Claude Code audio workflow - skipping persistence (message queued to SQS, customer=%s)",
            customer_id,
        )
        # Send distinct event so React knows to wait for response via proactive-agent WebSocket
        # Include session_id and character name so frontend can connect to correct WebSocket
        await manager.send_to_queues({
            "type": "claude_code_queued",
            "content": {
                "session_id": result.get("session_id"),
                "ai_character_name": result.get("ai_character_name"),
                "message": "Message queued for processing. Response will arrive via WebSocket.",
            },
        })
        # Skip text_completed - response will come via proactive-agent WebSocket streaming
        return

    if request_type == "tts":
        pass
    else:
        requires_tool_action = False
        if result is not None and isinstance(result, dict):
            requires_tool_action = bool(result.get("requires_tool_action"))

        if requires_tool_action:
            logger.info(
                "Skipping text_completed because tool action is pending (customer=%s)",
                customer_id,
            )
        else:
            await manager.send_to_queues({"type": "text_completed", "content": ""})

            tts_enabled = settings.get("tts", {}).get("tts_auto_execute", False)
            if not tts_enabled:
                await manager.send_to_queues({"type": "tts_not_requested", "content": ""})
