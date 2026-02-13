"""WebSocket group chat routing integration.

Handles detection and routing of group chat messages to the GroupChatRouter.
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.services.group_router import (
    GroupChatRouter,
    handle_sequential_responses,
    handle_leader_listeners_mode,
    message_queue,
)
from features.chat.services.group_service import GroupService

logger = logging.getLogger(__name__)


def is_group_message(data: Dict[str, Any]) -> bool:
    """Check if message payload is for a group chat."""
    return bool(data.get("group_id"))


def extract_group_id(data: Dict[str, Any]) -> Optional[UUID]:
    """Extract and validate group_id from payload."""
    group_id = data.get("group_id")
    if not group_id:
        return None
    try:
        return UUID(group_id) if isinstance(group_id, str) else group_id
    except (ValueError, TypeError):
        logger.warning(f"Invalid group_id format: {group_id}")
        return None


async def route_group_message(
    *,
    data: Dict[str, Any],
    websocket: WebSocket,
    db: AsyncSession,
    session_id: str,
    user_message_id: int | None = None,
    route_to_agent_fn,
) -> bool:
    """
    Route a message through the group chat system.
    
    Args:
        data: Message payload with group_id, prompt, etc.
        websocket: WebSocket connection for responses
        db: Database session
        session_id: Current session ID
        route_to_agent_fn: Async function to route to individual agents
        
    Returns:
        True if handled successfully, False if not a group message
    """
    group_id = extract_group_id(data)
    if not group_id:
        return False
    
    # Get the group
    service = GroupService(db)
    group = await service.get_group(group_id)
    
    if not group:
        logger.warning(f"Group not found: {group_id}")
        await websocket.send_json({
            "type": "error",
            "content": "Group not found",
            "group_id": str(group_id),
        })
        return True  # Handled (with error)
    
    # Extract message
    prompt = data.get("prompt") or data.get("message") or ""
    if not prompt:
        await websocket.send_json({
            "type": "error",
            "content": "Message required for group chat",
            "group_id": str(group_id),
        })
        return True
    
    # Create router
    router = GroupChatRouter(db)
    
    # Parse @mentions
    mentioned_agents = router.parse_mentions(prompt)
    
    # Determine target agents based on mode
    target_agents = await router.determine_target_agents(group, prompt, mentioned_agents)
    
    if not target_agents:
        await websocket.send_json({
            "type": "error",
            "content": "No agents available to respond",
            "group_id": str(group_id),
        })
        return True
    
    # Set up the message queue
    message_queue.set_pending(group_id, target_agents)

    # All agents route to OpenClaw (synchronous), no SQS request tracking needed
    request_repo = None
    group_request = None

    # Route based on mode
    try:
        if group.mode == "sequential":
            await handle_sequential_responses(
                websocket=websocket,
                db=db,
                group=group,
                user_message=prompt,
                session_id=session_id,
                router=router,
                route_to_agent_fn=route_to_agent_fn,
                group_request=group_request,
                request_repo=request_repo,
            )
        
        elif group.mode == "leader_listeners":
            await handle_leader_listeners_mode(
                websocket=websocket,
                db=db,
                group=group,
                user_message=prompt,
                session_id=session_id,
                router=router,
                route_to_agent_fn=route_to_agent_fn,
                mentioned_agents=mentioned_agents,
                group_request=group_request,
                request_repo=request_repo,
            )
        
        elif group.mode == "explicit":
            # Explicit mode: only respond if mentioned
            if not mentioned_agents:
                # No mentions - leader responds by default
                target_agents = [group.leader_agent]
            
            # Process each target agent
            pending_queued = False
            for agent_name in target_agents:
                if message_queue.is_cancelled(group_id):
                    await websocket.send_json({
                        "type": "queue_cancelled",
                        "group_id": str(group_id),
                        "reason": "User sent new message",
                    })
                    break
                
                # Send typing indicator
                await websocket.send_json({
                    "type": "agent_typing",
                    "group_id": str(group_id),
                    "agent_name": agent_name,
                })
                
                # Get context
                context = await router.get_context_for_agent(
                    group_id, agent_name, session_id, group.context_window_size
                )
                
                # Find member position
                member = next(
                    (m for m in group.members if m.agent_name == agent_name),
                    None
                )
                position = member.position if member else 0
                
                # Format payload
                payload = router.format_context_for_forwarding(
                    prompt, context, group, position
                )
                
                # Route to agent
                try:
                    result = await route_to_agent_fn(agent_name, payload, session_id)
                except Exception as e:
                    logger.error(f"Agent {agent_name} failed: {e}")
                    await websocket.send_json({
                        "type": "agent_error",
                        "group_id": str(group_id),
                        "agent_name": agent_name,
                        "error": str(e),
                    })
                    continue

                if result.queued:
                    pending_queued = True
                    if not request_repo or not group_request or not result.proactive_session_id:
                        logger.error("Queued agent response missing request correlation data")
                        continue
                    await request_repo.create_agent_request(
                        group_request_id=group_request.id,
                        proactive_session_id=result.proactive_session_id,
                        agent_name=agent_name,
                    )
                    continue

                if result.response:
                    # Update last response time
                    await service.update_member_response_time(group_id, agent_name)

                    # Mark done
                    message_queue.mark_agent_done(group_id, agent_name)

                    # Send response
                    await websocket.send_json({
                        "type": "agent_response",
                        "group_id": str(group_id),
                        "agent_name": agent_name,
                        "content": result.response,
                    })

            if not pending_queued:
                message_queue.clear(group_id)
        
        else:
            # Unknown mode - fallback to explicit behavior
            logger.warning(f"Unknown group mode: {group.mode}, falling back to explicit")
            await websocket.send_json({
                "type": "error",
                "content": f"Unknown group mode: {group.mode}",
                "group_id": str(group_id),
            })
        
        return True
        
    except Exception as e:
        logger.error(f"Error routing group message: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "content": f"Error processing group message: {str(e)}",
            "group_id": str(group_id),
        })
        message_queue.clear(group_id)
        return True


async def cancel_group_pending(group_id: UUID) -> bool:
    """
    Cancel pending responses for a group.
    Called when user sends a new message before previous responses complete.
    
    Returns:
        True if there were pending responses to cancel
    """
    if message_queue.get_next_agent(group_id):
        message_queue.cancel_pending(group_id)
        return True
    return False
