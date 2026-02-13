"""Helpers for the WebSocket workflow dispatcher."""

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any, Dict

from fastapi import WebSocket

from core.exceptions import ProviderError, ServiceError, ValidationError
from features.audio.service import STTService
from features.chat.service import ChatService
from features.chat.utils.prompt_utils import prompt_preview
from features.semantic_search.prompt_enhancement import (
    enhance_prompt_with_semantic_context,
)

from .websocket_errors import (
    emit_internal_error,
    emit_json_error,
    emit_provider_error,
    emit_validation_error,
)
from .websocket_request import extract_prompt, extract_settings, normalise_request_type
from .websocket_runtime import WorkflowRuntime
from .websocket_session import WorkflowSession
from .websocket_workflow_executor import (
    run_clarification_workflow,
    run_standard_workflow,
)

logger = logging.getLogger(__name__)


async def run_workflow_lifecycle(
    *,
    data: Dict[str, Any],
    session: WorkflowSession,
    websocket: WebSocket,
    service: ChatService,
    stt_service: STTService,
    runtime: WorkflowRuntime,
) -> bool:
    """Run the full workflow lifecycle with error handling."""
    completion_token = runtime.manager.create_completion_token()
    completion_signalled = False
    request_type = normalise_request_type(data)

    try:
        user_settings: Dict[str, Any] = extract_settings(data) or {}
        message_type = str(data.get("type") or "").lower()

        if message_type == "clarification_response":
            await _handle_clarification(data, user_settings, session, service, runtime.manager, completion_token)
            return True

        # Standard workflow
        prompt = extract_prompt(data)
        enhanced_prompt, semantic_metadata = await _enhance_prompt(
            prompt, request_type, session, user_settings, runtime.manager
        )

        workflow = await run_standard_workflow(
            request_type=request_type,
            prompt=enhanced_prompt,
            settings=user_settings,
            customer_id=session.customer_id,
            manager=runtime.manager,
            service=service,
            stt_service=stt_service,
            websocket=websocket,
            completion_token=completion_token,
            data=data,
            prompt_for_preview=prompt,
            session_id=session.session_id,
            workflow_session=session,
            runtime=runtime,
        )

        if not workflow.success:
            return True

        completion_signalled = True
        _update_session_context(session, request_type, workflow, semantic_metadata)
        return True

    except asyncio.CancelledError:
        await _handle_cancellation(runtime, completion_token, session.session_id)
        completion_signalled = True
        return True
    except (ValidationError, ProviderError, ServiceError, json.JSONDecodeError) as exc:
        await _handle_known_errors(exc, runtime.manager, session.session_id)
        return True
    except Exception as exc:
        logger.error("Unexpected WebSocket error: %s", exc, exc_info=True)
        await emit_internal_error(manager=runtime.manager, session_id=session.session_id)
        return True
    finally:
        if not completion_signalled:
            with suppress(Exception):
                await runtime.manager.signal_completion(token=completion_token)
        session.mark_workflow(None)


async def _handle_clarification(data, user_settings, session, service, manager, token):
    clarification = await run_clarification_workflow(
        data=data,
        settings=user_settings,
        customer_id=session.customer_id,
        manager=manager,
        service=service,
        completion_token=token,
    )
    if clarification.success:
        session.context.update({"last_clarification": clarification.context})


async def _enhance_prompt(prompt, request_type, session, user_settings, manager):
    if request_type in {"audio", "audio_direct"}:
        return prompt, None

    enhancement_result = await enhance_prompt_with_semantic_context(
        prompt=prompt,
        customer_id=session.customer_id,
        user_settings=user_settings,
        manager=manager,
        current_session_id=session.session_id,
    )
    return enhancement_result.enhanced_prompt, enhancement_result.metadata


def _update_session_context(session, request_type, workflow, semantic_metadata):
    session.context.update(
        {
            "last_workflow": {
                "request_type": request_type,
                "prompt_preview": prompt_preview(workflow.prompt_for_preview),
                "timings": {k: round(v, 3) for k, v in workflow.timings.items()},
                "semantic_context": semantic_metadata,
            }
        }
    )


async def _handle_cancellation(runtime, token, session_id):
    logger.info("Workflow cancelled by user (session=%s)", session_id)

    # Abort any active OpenClaw stream for this session
    try:
        from features.proactive_agent.openclaw.router import abort_openclaw_stream_by_session
        aborted = await abort_openclaw_stream_by_session(session_id)
        if aborted:
            logger.info("OpenClaw stream aborted for session=%s", session_id[:8] if session_id else "none")
    except Exception as e:
        logger.warning("Failed to abort OpenClaw stream: %s", e)

    await runtime.manager.send_to_queues(
        {"type": "cancelled", "content": "Request cancelled", "session_id": session_id}
    )
    # Send completion events so client dual-flag logic finalizes properly
    await runtime.manager.send_to_queues({"type": "text_completed", "content": ""})
    await runtime.manager.send_to_queues({"type": "tts_not_requested", "content": ""})
    await runtime.manager.signal_completion(token=token)


async def _handle_known_errors(exc, manager, session_id):
    if isinstance(exc, ValidationError):
        await emit_validation_error(manager=manager, session_id=session_id, error=str(exc))
    elif isinstance(exc, (ProviderError, ServiceError)):
        await emit_provider_error(manager=manager, session_id=session_id, error=str(exc))
    elif isinstance(exc, json.JSONDecodeError):
        await emit_json_error(manager=manager, session_id=session_id)
