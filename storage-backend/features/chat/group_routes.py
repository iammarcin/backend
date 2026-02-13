"""REST API endpoints for group chat management."""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.auth import AuthContext, require_auth_context
from features.chat.dependencies import get_chat_session
from features.chat.services.group_service import GroupService
from features.chat.schemas.group_schemas import (
    GroupCreate,
    GroupUpdate,
    GroupMembersUpdate,
    GroupResponse,
    GroupListResponse,
    GroupMode,
)
from features.chat.db_models import ChatSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


class ConvertToGroupRequest(BaseModel):
    """Request schema for converting individual chat to group."""
    agents: List[str]  # New agents to add (original is auto-included)
    mode: GroupMode = GroupMode.EXPLICIT
    name: Optional[str] = None
    context_window_size: int = Field(default=6, ge=3, le=10)


@router.post("", response_model=GroupResponse)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_chat_session),
    auth: AuthContext = Depends(require_auth_context),
):
    """Create a new group chat."""
    if len(data.agents) < 2:
        raise HTTPException(status_code=400, detail="Group must have at least 2 agents")

    user_id = auth["customer_id"]
    service = GroupService(db)
    try:
        group = await service.create_group(user_id, data)
        logger.info(f"Created group {group.id} for user {user_id} with agents {data.agents}")
        return group
    except Exception as e:
        logger.error(f"Failed to create group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=GroupListResponse)
async def list_groups(
    db: AsyncSession = Depends(get_chat_session),
    auth: AuthContext = Depends(require_auth_context),
):
    """List all group chats for current user."""
    user_id = auth["customer_id"]
    service = GroupService(db)
    try:
        groups = await service.list_groups(user_id)
        return GroupListResponse(groups=groups)
    except Exception as e:
        logger.error(f"Failed to list groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_chat_session),
    auth: AuthContext = Depends(require_auth_context),
):
    """Get group details."""
    user_id = auth["customer_id"]
    service = GroupService(db)
    try:
        group = await service.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if group.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        return group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: UUID,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_chat_session),
    auth: AuthContext = Depends(require_auth_context),
):
    """Update group settings (name, context_window_size only)."""
    user_id = auth["customer_id"]
    service = GroupService(db)
    try:
        group = await service.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if group.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        updated = await service.update_group(group_id, data)
        logger.info(f"Updated group {group_id}")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{group_id}/members", response_model=GroupResponse)
async def update_group_members(
    group_id: UUID,
    data: GroupMembersUpdate,
    db: AsyncSession = Depends(get_chat_session),
    auth: AuthContext = Depends(require_auth_context),
):
    """Add or remove group members while preserving order."""
    user_id = auth["customer_id"]
    service = GroupService(db)
    try:
        group = await service.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if group.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        updated = await service.update_group_members(
            group_id,
            add_agents=data.add_agents,
            remove_agents=data.remove_agents,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Group not found")
        logger.info(
            "Updated group members for %s (added=%s removed=%s)",
            group_id,
            data.add_agents,
            data.remove_agents,
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update group members for {group_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{group_id}")
async def delete_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_chat_session),
    auth: AuthContext = Depends(require_auth_context),
):
    """Delete a group chat."""
    user_id = auth["customer_id"]
    service = GroupService(db)
    try:
        group = await service.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if group.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        await service.delete_group(group_id)
        logger.info(f"Deleted group {group_id}")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{group_id}/messages")
async def get_group_messages(
    group_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_chat_session),
    auth: AuthContext = Depends(require_auth_context),
):
    """Get messages for a group chat."""
    from sqlalchemy import select
    from features.chat.db_models import ChatSession, ChatMessage
    
    user_id = auth["customer_id"]
    service = GroupService(db)
    
    try:
        # Verify access to group
        group = await service.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if group.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Find session for this group
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.group_id == group_id)
            .where(ChatSession.customer_id == user_id)
            .limit(1)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return {"messages": [], "total": 0}
        
        # Get messages for this session
        from sqlalchemy import func
        
        # Count total
        count_result = await db.execute(
            select(func.count()).select_from(ChatMessage)
            .where(ChatMessage.session_id == session.session_id)
        )
        total = count_result.scalar() or 0
        
        # Get messages
        msg_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        messages = msg_result.scalars().all()
        
        return {
            "messages": [
                {
                    "id": str(m.message_id),
                    "role": "user" if m.sender == "User" else "assistant",
                    "content": m.message,
                    "agent_name": m.responding_agent or m.ai_character_name,
                    "timestamp": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
            "total": total,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get messages for group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/convert-to-group", response_model=GroupResponse)
async def convert_session_to_group(
    session_id: str,
    data: ConvertToGroupRequest,
    db: AsyncSession = Depends(get_chat_session),
    auth: AuthContext = Depends(require_auth_context),
):
    """
    Convert an individual chat session to a group chat.
    
    - Creates a new group with the original agent + new agents
    - Links the existing session to the group
    - Existing messages are preserved and become group history
    """
    user_id = auth["customer_id"]
    
    try:
        # Get existing session
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.session_id == session_id)
            .where(ChatSession.customer_id == user_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session.group_id:
            raise HTTPException(status_code=400, detail="Session is already a group")
        
        # Get original agent from session (default to sherlock)
        original_agent = session.ai_character_name or "sherlock"
        
        # Ensure original agent is included and deduplicate
        agents = list(dict.fromkeys([original_agent] + data.agents))
        if len(agents) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 agents for a group")
        
        # Create group via service
        service = GroupService(db)
        group_data = GroupCreate(
            name=data.name,
            mode=data.mode,
            agents=agents,
            context_window_size=data.context_window_size,
        )
        group = await service.create_group(user_id, group_data)
        
        # Link session to group
        session.group_id = group.id
        await db.commit()
        
        logger.info(f"Converted session {session_id} to group {group.id} for user {user_id}")
        return group
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to convert session {session_id} to group: {e}")
        raise HTTPException(status_code=500, detail=str(e))
