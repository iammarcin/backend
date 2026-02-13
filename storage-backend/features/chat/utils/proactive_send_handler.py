"""Send message handler for proactive WebSocket connections.

Routes all messages to OpenClaw Gateway unconditionally.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import WebSocket

from .proactive_utils import (
    log_message_payload,
    resolve_session_id,
    parse_attachments,
    save_user_message,
)

logger = logging.getLogger(__name__)


async def handle_send_message(
    websocket: WebSocket,
    user_id: int,
    session_id: str,
    message: Dict[str, Any],
) -> None:
    """Handle send_message request from client.

    Client sends: {"type": "send_message", "content": "...", "source": "text"}
    Server responds: {"type": "message_sent", "db_message_id": "...", "session_id": "..."}
    On error: {"type": "send_error", "error": "..."}

    All messages route to OpenClaw Gateway unconditionally.

    Group routing:
    - If group_id is present, route through group chat system instead
    """
    # DEBUG: Log session IDs for troubleshooting
    msg_session_id = message.get("session_id")
    logger.info(
        "[SESSION DEBUG] handle_send_message: ws_url_session=%s, msg_session=%s, has_session_key=%s, group_id=%s",
        session_id[:8] if session_id else "none",
        msg_session_id[:8] if msg_session_id else "none",
        "session_id" in message,
        message.get("group_id", "none")[:8] if message.get("group_id") else "none",
    )
    log_message_payload(message, session_id)
    
    # Check for group chat - route through group system instead of direct agent routing
    group_id = message.get("group_id")
    if group_id:
        logger.info("Group message detected, routing through group system: group_id=%s", group_id[:8])
        await _route_to_group(
            websocket=websocket,
            user_id=user_id,
            session_id=session_id,
            message=message,
        )
        return

    content = message.get("content", "").strip()
    if not content:
        await websocket.send_json({"type": "send_error", "error": "Content required"})
        return

    source_str = message.get("source", "text")
    settings = message.get("settings") or {}
    ai_character_name = (
        message.get("ai_character_name")
        or settings.get("text", {}).get("ai_character")
        or "sherlock"
    )
    tts_settings = message.get("tts_settings")
    attachments = parse_attachments(message.get("attachments") or {})

    # Determine effective session_id
    effective_session_id = resolve_session_id(message, session_id)

    try:
        await _route_to_openclaw(
            websocket=websocket,
            user_id=user_id,
            session_id=effective_session_id or session_id,
            content=content,
            source_str=source_str,
            ai_character_name=ai_character_name,
            tts_settings=tts_settings,
            attachments=attachments,
        )
    except Exception as exc:
        logger.error("Failed to send message via WebSocket: %s", exc, exc_info=True)
        await websocket.send_json({"type": "send_error", "error": str(exc)})


async def _route_to_openclaw(
    *,
    websocket: WebSocket,
    user_id: int,
    session_id: str,
    content: str,
    source_str: str,
    ai_character_name: str,
    tts_settings: Dict[str, Any] | None,
    attachments: list[Dict[str, Any]],
) -> None:
    """Route message to OpenClaw Gateway."""
    from features.proactive_agent.openclaw.config import is_openclaw_enabled
    from features.proactive_agent.openclaw.router import send_message_to_openclaw

    if not is_openclaw_enabled():
        logger.error("OpenClaw routing requested but OPENCLAW_ENABLED=false")
        await websocket.send_json({
            "type": "send_error",
            "error": "OpenClaw is not enabled on this server",
        })
        return

    logger.info(
        "Routing to OpenClaw: user=%s, session=%s, character=%s",
        user_id,
        session_id[:8] if session_id else "new",
        ai_character_name,
    )

    # Save user message to database BEFORE sending to OpenClaw
    user_message = await save_user_message(
        user_id=user_id,
        session_id=session_id,
        content=content,
        source_str=source_str,
        ai_character_name=ai_character_name,
        attachments=attachments,
    )

    result = await send_message_to_openclaw(
        user_id=user_id,
        session_id=session_id,
        message=content,
        ai_character_name=ai_character_name,
        tts_settings=tts_settings,
        attachments=attachments or None,
    )

    await websocket.send_json({
        "type": "message_sent",
        "message_id": user_message.message_id if user_message else result.get("run_id", ""),
        "session_id": session_id,
        "queued": False,
        "openclaw": True,
    })


async def _route_to_group(
    *,
    websocket: WebSocket,
    user_id: int,
    session_id: str,
    message: Dict[str, Any],
) -> None:
    """Route message through group chat system.
    
    Delegates to websocket_group_routing which handles:
    - Agent selection based on mode
    - @mention parsing
    - Response collection from agents
    
    Also persists user and agent messages to database.
    """
    from features.chat.utils.websocket_group_routing import route_group_message
    from features.chat.utils.agent_router import route_to_agent as real_route_to_agent
    from features.proactive_agent.dependencies import get_db_session_direct
    from features.chat.services.group_service import GroupService
    from features.chat.db_models import ChatMessage, ChatSession
    from uuid import UUID, uuid4
    from sqlalchemy import select
    
    group_id = message.get("group_id")
    content = message.get("content", "").strip()
    
    if not content:
        await websocket.send_json({"type": "send_error", "error": "Content required"})
        return
    
    try:
        async with get_db_session_direct() as db:
            # Get or create a session for this group
            group_uuid = UUID(group_id) if isinstance(group_id, str) else group_id
            
            # Check if a session exists for this group
            result = await db.execute(
                select(ChatSession)
                .where(ChatSession.group_id == group_uuid)
                .where(ChatSession.customer_id == user_id)
                .limit(1)
            )
            group_session = result.scalar_one_or_none()
            
            if not group_session:
                # Create a NEW session for this group (with unique ID)
                group_service = GroupService(db)
                group = await group_service.get_group(group_uuid)
                group_name = group.name if group else "Group Chat"
                new_session_id = str(uuid4())
                
                group_session = ChatSession(
                    session_id=new_session_id,  # Generate new unique ID
                    customer_id=user_id,
                    session_name=f"Group: {group_name}",
                    group_id=group_uuid,
                    ai_character_name="group",
                )
                db.add(group_session)
                await db.flush()
                logger.info("Created group session: %s for group %s", new_session_id, group_id)
            
            effective_session_id = group_session.session_id
            
            # Save user message to database
            user_msg = ChatMessage(
                session_id=effective_session_id,
                customer_id=user_id,
                sender="User",
                message=content,
                ai_character_name="group",
            )
            db.add(user_msg)
            await db.flush()
            user_message_id = user_msg.message_id
            logger.info("Saved group user message: %s", user_message_id)

            # Commit user message before any agent routing to keep transactions short-lived.
            await db.commit()
            
            # Build data payload for group routing
            data = {
                "group_id": group_id,
                "prompt": content,
                "message": content,
            }
            
            async def route_to_agent(agent_name: str, payload: dict, sess_id: str):
                """Wrapper to route to individual agents and save response."""
                logger.info("Group routing to agent: %s", agent_name)
                result = await real_route_to_agent(
                    agent_name=agent_name,
                    payload=payload,
                    session_id=sess_id,
                    user_id=user_id,
                )
                
                # Save agent response to database
                if result.response:
                    agent_msg = ChatMessage(
                        session_id=effective_session_id,
                        customer_id=user_id,
                        sender="AI",
                        message=result.response,
                        ai_character_name=agent_name,
                        responding_agent=agent_name,
                    )
                    db.add(agent_msg)
                    await db.flush()
                    logger.info("Saved group agent response from %s: msg_id=%s", agent_name, agent_msg.message_id)
                
                return result
            
            handled = await route_group_message(
                data=data,
                websocket=websocket,
                db=db,
                session_id=effective_session_id,
                user_message_id=user_message_id,
                route_to_agent_fn=route_to_agent,
            )
            
            await db.commit()
            
            if handled:
                # Send confirmation that group message was processed
                await websocket.send_json({
                    "type": "message_sent",
                    "group_id": group_id,
                    "session_id": effective_session_id,
                    "message_id": user_message_id,
                    "queued": False,
                    "group": True,
                })
            else:
                await websocket.send_json({
                    "type": "send_error",
                    "error": "Failed to route group message",
                    "group_id": group_id,
                })
                
    except Exception as exc:
        logger.error("Group routing failed: %s", exc, exc_info=True)
        await websocket.send_json({
            "type": "send_error",
            "error": f"Group chat error: {str(exc)}",
            "group_id": group_id,
        })
