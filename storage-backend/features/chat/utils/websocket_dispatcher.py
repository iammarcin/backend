"""Coordinate WebSocket workflow execution for chat sessions."""

import logging
from contextlib import suppress
from typing import Any, Dict

from fastapi import WebSocket

from features.audio.service import STTService
from features.chat.service import ChatService

from .dispatcher_helpers import run_workflow_lifecycle
from .websocket_request import normalise_request_type, extract_prompt
from .websocket_runtime import WorkflowRuntime, create_workflow_runtime
from .websocket_session import WorkflowSession
from .websocket_group_routing import is_group_message, route_group_message

logger = logging.getLogger(__name__)


async def dispatch_workflow(
    *,
    data: Dict[str, Any],
    session: WorkflowSession,
    websocket: WebSocket,
    service: ChatService,
    stt_service: STTService,
    runtime: WorkflowRuntime | None = None,
) -> bool:
    """Route an inbound payload to the appropriate workflow handler."""
    session.customer_id = int(data.get("customer_id") or session.customer_id or 0)
    if runtime is None:
        runtime = await create_workflow_runtime(session_id=session.session_id, websocket=websocket)
    
    # Check for group chat message first
    if is_group_message(data):
        return await _handle_group_message(
            data=data,
            session=session,
            websocket=websocket,
            service=service,
            runtime=runtime,
        )
    
    request_type = normalise_request_type(data)

    prompt = extract_prompt(data)
    message_type = str(data.get("type") or "").lower()
    skip_prompt_validation = request_type in {"audio", "audio_direct", "realtime"}
    if not message_type == "clarification_response" and not skip_prompt_validation and not prompt:
        await runtime.manager.send_to_queues(
            {"type": "error", "content": "Prompt required", "stage": "validation"}
        )
        completion_token = runtime.manager.create_completion_token()
        await runtime.manager.signal_completion(token=completion_token)
        return True

    with suppress(Exception):
        await websocket.send_json(
            {
                "type": "working",
                "session_id": session.session_id,
                "content": {"request_type": request_type},
            }
        )

    session.mark_workflow(request_type)

    return await run_workflow_lifecycle(
        data=data,
        session=session,
        websocket=websocket,
        service=service,
        stt_service=stt_service,
        runtime=runtime,
    )


async def _handle_group_message(
    *,
    data: Dict[str, Any],
    session: WorkflowSession,
    websocket: WebSocket,
    service: ChatService,
    runtime: WorkflowRuntime,
) -> bool:
    """Handle group chat message routing.
    
    Routes messages to the appropriate agents based on group configuration.
    Uses real agent routing (OpenClaw/Claude SDK) instead of placeholders.
    """
    from features.proactive_agent.dependencies import get_db_session_direct
    from features.chat.utils.agent_router import AgentRouteResult, route_to_agent as real_route_to_agent

    # Get user_id from session (needed for agent routing)
    user_id = session.customer_id or 0

    try:
        async with get_db_session_direct() as db:
            async def route_to_agent(agent_name: str, payload: dict, session_id: str):
                """
                Route message to a specific agent using real routing.

                Delegates to agent_router which handles:
                - OpenClaw agents (Sherlock) → OpenClaw Gateway
                - Claude SDK agents (Bugsy, etc.) → SQS enqueue (event-driven completion)
                """
                logger.info(
                    "Routing group message to agent: %s (user=%s, session=%s)",
                    agent_name,
                    user_id,
                    session_id[:8] if session_id else "none",
                )

                try:
                    return await real_route_to_agent(
                        agent_name=agent_name,
                        payload=payload,
                        session_id=session_id,
                        user_id=user_id,
                    )
                except NotImplementedError as e:
                    # Agent type not supported in group chat yet
                    logger.warning("Agent %s not supported in groups: %s", agent_name, e)
                    return AgentRouteResult(
                        response=f"[{agent_name} is not available for group chat yet]",
                        queued=False,
                    )
                except Exception as e:
                    logger.error("Agent routing failed for %s: %s", agent_name, e, exc_info=True)
                    raise

            handled = await route_group_message(
                data=data,
                websocket=websocket,
                db=db,
                session_id=session.session_id,
                user_message_id=None,
                route_to_agent_fn=route_to_agent,
            )
            return handled
    except Exception as e:
        logger.error(f"Error handling group message: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "content": f"Group chat error: {str(e)}",
        })
        return True
