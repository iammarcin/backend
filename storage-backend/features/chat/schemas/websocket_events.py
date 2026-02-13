"""WebSocket event schemas for group chat messages."""

from pydantic import BaseModel
from typing import Optional, List, Literal
from uuid import UUID


class GroupMessagePayload(BaseModel):
    """Payload for sending a message in a group chat."""
    content: str
    group_id: UUID
    target_agent: Optional[str] = None  # Single @mention
    target_agents: Optional[List[str]] = None  # Multiple @mentions


class AgentTypingEvent(BaseModel):
    """Event sent when an agent starts typing/processing."""
    type: Literal["agent_typing"] = "agent_typing"
    group_id: str
    agent_name: str
    position: Optional[int] = None  # Position in sequence (for sequential mode)
    total: Optional[int] = None  # Total agents in sequence


class AgentResponseEvent(BaseModel):
    """Event sent when an agent completes their response."""
    type: Literal["agent_response"] = "agent_response"
    group_id: str
    agent_name: str
    content: str
    position: Optional[int] = None  # Position in sequence
    is_last: Optional[bool] = None  # True if this is the last agent in sequence


class QueueCancelledEvent(BaseModel):
    """Event sent when pending agent responses are cancelled."""
    type: Literal["queue_cancelled"] = "queue_cancelled"
    group_id: str
    reason: str


class AgentErrorEvent(BaseModel):
    """Event sent when an agent encounters an error."""
    type: Literal["agent_error"] = "agent_error"
    group_id: str
    agent_name: str
    error: str


class SequenceCompleteEvent(BaseModel):
    """Event sent when a sequential response sequence is complete."""
    type: Literal["sequence_complete"] = "sequence_complete"
    group_id: str
    agents_responded: int


class SequenceInterruptedEvent(BaseModel):
    """Event sent when a sequential response is interrupted by a new user message."""
    type: Literal["sequence_interrupted"] = "sequence_interrupted"
    group_id: str
    completed_agents: List[str]


# ==============================================================================
# Leader + Listeners Mode Events
# ==============================================================================

class ListenerNotificationEvent(BaseModel):
    """Event sent when a listener receives a message notification (not responding)."""
    type: Literal["listener_notification"] = "listener_notification"
    group_id: str
    listener: str
    sender: str  # 'user' or agent name
    respond: bool = False


class ListenerInvokedEvent(BaseModel):
    """Event sent when a listener is invoked by leader or user."""
    type: Literal["listener_invoked"] = "listener_invoked"
    group_id: str
    listener: str
    invoked_by: str  # 'user' or leader agent name
    reason: Optional[str] = None  # Optional reason/context for invocation


class LeaderListenersTypingEvent(AgentTypingEvent):
    """Extended typing event for Leader+Listeners mode."""
    role: Optional[str] = None  # 'leader' or 'listener'
    invoked_by: Optional[str] = None  # Who invoked this agent


class LeaderListenersResponseEvent(AgentResponseEvent):
    """Extended response event for Leader+Listeners mode."""
    role: Optional[str] = None  # 'leader' or 'listener'
    invoked_by: Optional[str] = None  # Who invoked this agent (for listeners)
