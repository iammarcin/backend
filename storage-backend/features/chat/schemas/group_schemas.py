"""Pydantic schemas for group chat operations."""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class GroupMode(str, Enum):
    SEQUENTIAL = "sequential"
    LEADER_LISTENERS = "leader_listeners"
    EXPLICIT = "explicit"


class GroupMemberCreate(BaseModel):
    agent_name: str
    position: int


class GroupCreate(BaseModel):
    name: Optional[str] = None
    mode: GroupMode
    agents: List[str]  # Agent names in order
    context_window_size: int = Field(default=6, ge=3, le=10)


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    context_window_size: Optional[int] = Field(default=None, ge=3, le=10)


class GroupMembersUpdate(BaseModel):
    add_agents: Optional[List[str]] = None
    remove_agents: Optional[List[str]] = None


class GroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_name: str
    position: int
    last_response_at: Optional[datetime] = None


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: int  # User ID is int, not UUID
    name: Optional[str]
    mode: GroupMode
    leader_agent: str
    context_window_size: int
    members: List[GroupMemberResponse]
    created_at: datetime
    updated_at: datetime


class GroupListResponse(BaseModel):
    groups: List[GroupResponse]
