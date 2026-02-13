"""Group chat routing logic for multi-agent conversations."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
import re
import logging
import asyncio

from features.chat.db_models import ChatGroup, ChatGroupMember, ChatMessage
from features.chat.group_request_models import GroupChatRequest
from features.chat.repositories.group_request_repository import GroupChatRequestRepository
from features.chat.services.group_service import GroupService

logger = logging.getLogger(__name__)


# ==============================================================================
# Error Handling
# ==============================================================================

class AgentError(Exception):
    """Exception for agent-specific errors with rich metadata."""
    
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    CONTEXT_TOO_LARGE = "context_too_large"
    UNKNOWN = "unknown"
    
    def __init__(
        self,
        agent_name: str,
        message: str,
        code: str = "unknown",
        retryable: bool = True
    ):
        self.agent_name = agent_name
        self.message = message
        self.code = code
        self.retryable = retryable
        super().__init__(message)


async def emit_agent_error(
    websocket,
    group_id: UUID,
    agent_name: str,
    error: str,
    error_code: str = "unknown",
    retryable: bool = True
):
    """Emit agent error event to client with rich metadata."""
    await websocket.send_json({
        "type": "agent_error",
        "group_id": str(group_id),
        "agent_name": agent_name,
        "error": error,
        "error_code": error_code,
        "retryable": retryable
    })


async def route_to_agent_with_error_handling(
    websocket,
    agent_name: str,
    payload: dict,
    session_id: UUID,
    group_id: UUID,
    route_to_agent_fn,
    timeout: int = 60
) -> Optional[str]:
    """
    Route to agent with proper error handling and rich error events.
    
    Args:
        websocket: WebSocket connection for error emission
        agent_name: Target agent name
        payload: Message payload
        session_id: Session ID
        group_id: Group ID for error events
        route_to_agent_fn: Async function to actually route to agent
        timeout: Timeout in seconds
    
    Returns:
        Agent response string or None if error
    """
    try:
        response = await asyncio.wait_for(
            route_to_agent_fn(agent_name, payload, session_id),
            timeout=timeout
        )
        
        if not response:
            raise AgentError(
                agent_name,
                "Empty response from agent",
                AgentError.UNKNOWN,
                retryable=True
            )
        
        return response
        
    except asyncio.TimeoutError:
        await emit_agent_error(
            websocket, group_id, agent_name,
            "Agent took too long to respond",
            AgentError.TIMEOUT,
            retryable=True
        )
        return None
        
    except ConnectionError:
        await emit_agent_error(
            websocket, group_id, agent_name,
            "Agent is currently unavailable",
            AgentError.UNAVAILABLE,
            retryable=True
        )
        return None
        
    except AgentError as e:
        await emit_agent_error(
            websocket, group_id, agent_name,
            e.message, e.code, e.retryable
        )
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error from {agent_name}: {e}")
        await emit_agent_error(
            websocket, group_id, agent_name,
            "Unexpected error occurred",
            AgentError.UNKNOWN,
            retryable=False
        )
        return None


class GroupChatRouter:
    """Routes messages in group chats based on mode and @mentions."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.group_service = GroupService(db)
    
    async def determine_target_agents(
        self,
        group: ChatGroup,
        message: str,
        mentioned_agents: List[str]
    ) -> List[str]:
        """
        Determine which agents should respond based on mode and @mentions.
        Returns list of agent names in order they should respond.
        """
        members = sorted(group.members, key=lambda m: m.position)
        all_agents = [m.agent_name for m in members]
        
        if group.mode == "explicit":
            if mentioned_agents:
                # Only mentioned agents respond, in mention order
                return [a for a in mentioned_agents if a in all_agents]
            else:
                # No mention → leader responds
                return [group.leader_agent]
        
        elif group.mode == "leader_listeners":
            # Leader always responds first
            targets = [group.leader_agent]
            # Add any explicitly mentioned non-leaders
            for agent in mentioned_agents:
                if agent in all_agents and agent != group.leader_agent:
                    targets.append(agent)
            return targets
        
        elif group.mode == "sequential":
            # All agents respond in position order
            return all_agents
        
        return [group.leader_agent]  # Fallback
    
    def parse_mentions(self, message: str) -> List[str]:
        """Extract @mentioned agent names from message."""
        # Match @AgentName (case-insensitive)
        pattern = r'@(\w+)'
        matches = re.findall(pattern, message)
        return [m.lower() for m in matches]
    
    async def get_context_for_agent(
        self,
        group_id: UUID,
        agent_name: str,
        session_id: str,
        max_messages: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Get context messages for an agent.
        Only includes messages since their last response (or up to max if first turn).
        """
        # Get agent's last response time
        member_result = await self.db.execute(
            select(ChatGroupMember)
            .where(ChatGroupMember.group_id == group_id)
            .where(ChatGroupMember.agent_name == agent_name)
        )
        member = member_result.scalar_one_or_none()
        
        # Build query for messages
        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
        )
        
        if member and member.last_response_at:
            # Only messages since last response
            query = query.where(ChatMessage.created_at > member.last_response_at)
        
        query = query.limit(max_messages)
        
        result = await self.db.execute(query)
        messages = list(result.scalars().all())
        messages.reverse()  # Chronological order
        
        # Format for agent
        # Map sender to role: 'user' or 'assistant'
        context = []
        for msg in messages:
            role = "user" if msg.sender.lower() == "user" else "assistant"
            ctx = {
                "role": role,
                "content": msg.message or "",
                "timestamp": msg.created_at.isoformat() if msg.created_at else None
            }
            if msg.responding_agent:
                ctx["agent"] = msg.responding_agent
            context.append(ctx)
        
        return context
    
    def format_context_for_forwarding(
        self,
        user_message: str,
        context: List[Dict[str, Any]],
        group: ChatGroup,
        agent_position: int
    ) -> Dict[str, Any]:
        """Format the full payload for forwarding to an agent."""
        return {
            "user_message": user_message,
            "context": context,
            "group_metadata": {
                "mode": group.mode,
                "agents": [m.agent_name for m in sorted(group.members, key=lambda x: x.position)],
                "your_position": agent_position,
                "leader": group.leader_agent,
                "group_id": str(group.id),
                "group_name": group.name
            }
        }


class MessageQueue:
    """Manages pending agent responses and user message precedence."""
    
    def __init__(self):
        self._pending: Dict[UUID, List[str]] = {}  # group_id -> [agent_names]
        self._cancelled: Dict[UUID, bool] = {}
    
    def set_pending(self, group_id: UUID, agents: List[str]):
        """Set the queue of agents that need to respond."""
        self._pending[group_id] = agents.copy()
        self._cancelled[group_id] = False

    def add_pending(self, group_id: UUID, agent_name: str) -> None:
        """Add a single agent to the pending queue if not already present."""
        if group_id not in self._pending:
            self._pending[group_id] = []
        if agent_name not in self._pending[group_id]:
            self._pending[group_id].append(agent_name)
        if group_id not in self._cancelled:
            self._cancelled[group_id] = False
    
    def get_next_agent(self, group_id: UUID) -> Optional[str]:
        """Get next agent that should respond."""
        if self._cancelled.get(group_id):
            return None
        agents = self._pending.get(group_id, [])
        return agents[0] if agents else None
    
    def mark_agent_done(self, group_id: UUID, agent_name: str):
        """Remove agent from pending queue after they respond."""
        if group_id in self._pending and agent_name in self._pending[group_id]:
            self._pending[group_id].remove(agent_name)
    
    def cancel_pending(self, group_id: UUID):
        """Cancel all pending responses (user sent new message)."""
        self._cancelled[group_id] = True
        self._pending[group_id] = []
    
    def is_cancelled(self, group_id: UUID) -> bool:
        return self._cancelled.get(group_id, False)
    
    def clear(self, group_id: UUID):
        """Clear queue after all responses done."""
        self._pending.pop(group_id, None)
        self._cancelled.pop(group_id, None)


def create_sequential_system_hint(position: int, total: int, previous_agents: List[str]) -> str:
    """Create a system hint for sequential mode context."""
    if position == 0:
        return f"You are responding first in a sequence of {total} agents."
    else:
        prev = ", ".join(previous_agents)
        return (
            f"You are agent {position + 1} of {total} in a sequential response. "
            f"Previous agents who responded: {prev}. "
            f"Build on their responses where appropriate, but add your unique perspective."
        )


# ==============================================================================
# Leader + Listeners Mode Functions
# ==============================================================================

def create_leader_system_hint(listeners: List[str]) -> str:
    """Create system hint for leader in Leader+Listeners mode."""
    if not listeners:
        return "You are the LEADER in this group. You respond to every message."
    listener_str = ", ".join(listeners)
    return (
        f"You are the LEADER in this group. You respond to every message. "
        f"Listeners present: {listener_str}. "
        f"If you need a listener's input, you can invoke them by saying "
        f"'Let me ask [name]...' or '@[name], what do you think?'"
    )


def create_listener_system_hint(leader: str, is_invoked: bool = False, invoked_by: str = None) -> str:
    """Create system hint for listener agent."""
    if is_invoked:
        invoker = invoked_by or leader
        return (
            f"You are a LISTENER who has been invoked by {invoker}. "
            f"Respond to their question/request. "
            f"Keep your response focused on what was asked."
        )
    return (
        f"You are a LISTENER in this group. {leader} is the leader. "
        f"You only respond when directly @mentioned or invoked by the leader."
    )


def detect_listener_invocation(content: str, listeners: List[str]) -> List[str]:
    """
    Detect if leader is invoking a listener in their response.
    
    Patterns detected:
    - "Let me ask X", "Let's ask X"
    - "X, what do you think"
    - "X, can you..."
    - "Invoking X", "Asking X"
    - "@X" (mention syntax)
    
    Args:
        content: Leader's response text
        listeners: List of listener agent names
    
    Returns:
        List of invoked listener names (original case)
    """
    if not listeners:
        return []
    
    invoked = []
    content_lower = content.lower()
    listeners_lower = {l.lower(): l for l in listeners}
    
    # Natural language invocation patterns
    patterns = [
        r"let me ask (\w+)",
        r"let's ask (\w+)",
        r"(\w+),?\s+what do you think",
        r"(\w+),?\s+can you",
        r"(\w+),?\s+would you",
        r"(\w+),?\s+could you",
        r"invoking (\w+)",
        r"asking (\w+)",
        r"i'll ask (\w+)",
        r"let me check with (\w+)",
        r"(\w+),?\s+please",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content_lower)
        for match in matches:
            if match in listeners_lower:
                invoked.append(listeners_lower[match])
    
    # Also check for @mentions in leader's response
    mention_pattern = r'@(\w+)'
    mentions = re.findall(mention_pattern, content_lower)
    for mention in mentions:
        if mention in listeners_lower and listeners_lower[mention] not in invoked:
            invoked.append(listeners_lower[mention])
    
    return list(set(invoked))


async def notify_listeners(
    group: ChatGroup,
    message: str,
    sender: str,
    websocket=None
):
    """
    Notify listeners about a message in the group (for context building).
    
    Listeners don't respond, just update their context awareness.
    This is primarily for logging/context tracking purposes.
    
    Args:
        group: The chat group
        message: The message content
        sender: Who sent it ('user' or agent name)
        websocket: Optional websocket for sending notifications
    """
    leader = group.leader_agent
    listeners = [m.agent_name for m in group.members if m.agent_name != leader]
    
    logger.debug(f"Notifying listeners {listeners} about message from {sender}")
    
    # For now, this is primarily tracking/logging
    # In future, could send to agent sessions for context building
    if websocket:
        for listener in listeners:
            await websocket.send_json({
                "type": "listener_notification",
                "group_id": str(group.id),
                "listener": listener,
                "sender": sender,
                "respond": False  # Don't respond, just noting
            })


async def handle_leader_listeners_mode(
    websocket,
    db: AsyncSession,
    group: ChatGroup,
    user_message: str,
    session_id: UUID,
    router: GroupChatRouter,
    route_to_agent_fn,
    mentioned_agents: List[str] = None,
    group_request: GroupChatRequest | None = None,
    request_repo: GroupChatRequestRepository | None = None,
) -> List[Dict[str, Any]]:
    """
    Handle message flow in Leader+Listeners mode.
    
    Flow:
    1. Leader always responds first
    2. If user @mentioned listeners, they respond after leader
    3. If leader invokes listeners in their response, they respond
    4. Listeners receive context but don't respond otherwise
    
    Args:
        websocket: WebSocket connection
        db: Database session
        group: Chat group
        user_message: User's message
        session_id: Session ID
        router: GroupChatRouter instance
        route_to_agent_fn: Async function to route to agent
        mentioned_agents: List of @mentioned agents from user message
    
    Returns:
        List of response dicts [{agent, content}, ...]
    """
    mentioned_agents = mentioned_agents or []
    service = GroupService(db)
    members = sorted(group.members, key=lambda m: m.position)
    listeners = [m.agent_name for m in members if m.agent_name != group.leader_agent]
    responses = []
    pending_queued = False
    
    # 1. Leader always responds first
    await websocket.send_json({
        "type": "agent_typing",
        "group_id": str(group.id),
        "agent_name": group.leader_agent,
        "role": "leader"
    })
    
    # Get context for leader
    leader_context = await router.get_context_for_agent(
        group.id, group.leader_agent, session_id, group.context_window_size
    )
    
    # Find leader member for position
    leader_member = next(m for m in members if m.agent_name == group.leader_agent)
    
    # Format payload with leader hint
    leader_payload = router.format_context_for_forwarding(
        user_message, leader_context, group, leader_member.position
    )
    leader_payload["group_metadata"]["role"] = "leader"
    leader_payload["group_metadata"]["accumulated_context"] = []
    leader_payload["group_metadata"]["system_hint"] = create_leader_system_hint(listeners)

    # Look up existing proactive session for Claude SDK session reuse
    if request_repo:
        existing_session = await request_repo.get_latest_agent_session(
            group.id, group.leader_agent
        )
        if existing_session:
            leader_payload["group_metadata"]["proactive_session_id"] = existing_session

    # Get leader response
    try:
        leader_result = await route_to_agent_fn(group.leader_agent, leader_payload, session_id)
    except Exception as e:
        logger.error(f"Leader {group.leader_agent} failed: {e}")
        await websocket.send_json({
            "type": "agent_error",
            "group_id": str(group.id),
            "agent_name": group.leader_agent,
            "error": str(e)
        })
        return responses
    
    if leader_result.queued:
        pending_queued = True
        if request_repo and group_request and leader_result.proactive_session_id:
            await request_repo.create_agent_request(
                group_request_id=group_request.id,
                proactive_session_id=leader_result.proactive_session_id,
                agent_name=group.leader_agent,
            )
        else:
            logger.error("Queued leader response missing request correlation data")
        return responses

    leader_response = leader_result.response

    if leader_response:
        # Update leader's last response time
        service = GroupService(db)
        await service.update_member_response_time(group.id, group.leader_agent)
        
        responses.append({
            "agent": group.leader_agent,
            "content": leader_response,
            "role": "leader"
        })
        
        await websocket.send_json({
            "type": "agent_response",
            "group_id": str(group.id),
            "agent_name": group.leader_agent,
            "content": leader_response,
            "role": "leader"
        })
        
        # Notify listeners about leader's response
        await notify_listeners(group, leader_response, group.leader_agent, websocket)
    
    # 2. Determine which listeners should respond
    listeners_to_invoke = []
    
    # First: explicitly mentioned by user
    for agent in mentioned_agents:
        if agent in listeners and agent not in listeners_to_invoke:
            listeners_to_invoke.append(agent)
    
    # Second: invoked by leader in their response
    if leader_response:
        invoked = detect_listener_invocation(leader_response, listeners)
        for agent in invoked:
            if agent not in listeners_to_invoke:
                listeners_to_invoke.append(agent)
    
    # 3. Get responses from invoked listeners
    for listener in listeners_to_invoke:
        if message_queue.is_cancelled(group.id):
            await websocket.send_json({
                "type": "queue_cancelled",
                "group_id": str(group.id),
                "reason": "User sent new message"
            })
            break
        
        # Determine who invoked this listener
        invoked_by = None
        if listener in mentioned_agents:
            invoked_by = "user"
        elif listener in detect_listener_invocation(leader_response or "", listeners):
            invoked_by = group.leader_agent
        
        await websocket.send_json({
            "type": "agent_typing",
            "group_id": str(group.id),
            "agent_name": listener,
            "role": "listener",
            "invoked_by": invoked_by
        })
        
        # Get context for listener (DB history for session memory)
        listener_context = await router.get_context_for_agent(
            group.id, listener, session_id, group.context_window_size
        )

        # Find listener member
        listener_member = next(m for m in members if m.agent_name == listener)

        # Format payload — DB context for reference, leader response as delta
        listener_payload = router.format_context_for_forwarding(
            user_message, listener_context, group, listener_member.position
        )

        # Delta-only: pass leader's response as accumulated_context
        listener_accumulated = []
        if leader_response:
            listener_accumulated.append({
                "role": "assistant",
                "agent": group.leader_agent,
                "content": leader_response,
                "timestamp": datetime.utcnow().isoformat()
            })
        listener_payload["group_metadata"]["accumulated_context"] = listener_accumulated
        listener_payload["group_metadata"]["role"] = "listener"
        listener_payload["group_metadata"]["invoked_by"] = invoked_by
        listener_payload["group_metadata"]["system_hint"] = create_listener_system_hint(
            group.leader_agent, is_invoked=True, invoked_by=invoked_by
        )

        # Look up existing proactive session for Claude SDK session reuse
        if request_repo:
            existing_session = await request_repo.get_latest_agent_session(
                group.id, listener
            )
            if existing_session:
                listener_payload["group_metadata"]["proactive_session_id"] = existing_session

        # Get listener response
        try:
            listener_result = await route_to_agent_fn(listener, listener_payload, session_id)
        except Exception as e:
            logger.error(f"Listener {listener} failed: {e}")
            await websocket.send_json({
                "type": "agent_error",
                "group_id": str(group.id),
                "agent_name": listener,
                "error": str(e)
            })
            continue

        if listener_result.queued:
            pending_queued = True
            if request_repo and group_request and listener_result.proactive_session_id:
                await request_repo.create_agent_request(
                    group_request_id=group_request.id,
                    proactive_session_id=listener_result.proactive_session_id,
                    agent_name=listener,
                )
            else:
                logger.error("Queued listener response missing request correlation data")
            continue

        listener_response = listener_result.response

        if listener_response:
            # Update listener's last response time
            await service.update_member_response_time(group.id, listener)
            
            responses.append({
                "agent": listener,
                "content": listener_response,
                "role": "listener",
                "invoked_by": invoked_by
            })
            
            await websocket.send_json({
                "type": "agent_response",
                "group_id": str(group.id),
                "agent_name": listener,
                "content": listener_response,
                "role": "listener",
                "invoked_by": invoked_by
            })
    
    if not pending_queued:
        message_queue.clear(group.id)
    return responses


async def handle_sequential_responses(
    websocket,
    db: AsyncSession,
    group: ChatGroup,
    user_message: str,
    session_id: UUID,
    router: GroupChatRouter,
    route_to_agent_fn,
    group_request: GroupChatRequest | None = None,
    request_repo: GroupChatRequestRepository | None = None,
):
    """
    Process all agents in sequence for sequential mode.
    
    Args:
        websocket: The WebSocket connection
        db: Database session
        group: The chat group
        user_message: The user's message
        session_id: Current session ID
        router: GroupChatRouter instance
        route_to_agent_fn: Async function to route message to an agent
    """
    members = sorted(group.members, key=lambda m: m.position)
    accumulated_context = []
    
    for member in members:
        agent_name = member.agent_name
        
        if message_queue.is_cancelled(group.id):
            await websocket.send_json({
                "type": "sequence_interrupted",
                "group_id": str(group.id),
                "completed_agents": [m.agent_name for m in members[:member.position]]
            })
            break
        
        # Send typing indicator
        await websocket.send_json({
            "type": "agent_typing",
            "group_id": str(group.id),
            "agent_name": agent_name,
            "position": member.position,
            "total": len(members)
        })
        
        # Build context (DB history for session memory, not sent in message)
        context = await router.get_context_for_agent(
            group.id, agent_name, session_id, group.context_window_size
        )

        # Format payload — DB context stays in payload["context"] for reference,
        # but only accumulated_context (this round) goes into the message text.
        payload = router.format_context_for_forwarding(
            user_message, context, group, member.position
        )

        # Delta-only: pass this-round responses separately for message formatting
        payload["group_metadata"]["accumulated_context"] = list(accumulated_context)
        payload["group_metadata"]["previous_responses_this_round"] = len(accumulated_context)
        
        # Get system hint for sequential positioning
        previous_agents = [m.agent_name for m in members[:member.position]]
        system_hint = create_sequential_system_hint(member.position, len(members), previous_agents)
        payload["group_metadata"]["sequential_hint"] = system_hint

        # Look up existing proactive session for Claude SDK session reuse
        if request_repo:
            existing_session = await request_repo.get_latest_agent_session(
                group.id, agent_name
            )
            if existing_session:
                payload["group_metadata"]["proactive_session_id"] = existing_session

        # Route to agent
        try:
            result = await route_to_agent_fn(agent_name, payload, session_id)
        except Exception as e:
            result = None
            await websocket.send_json({
                "type": "agent_error",
                "group_id": str(group.id),
                "agent_name": agent_name,
                "error": str(e)
            })

        if result and result.queued:
            if request_repo and group_request and result.proactive_session_id:
                await request_repo.create_agent_request(
                    group_request_id=group_request.id,
                    proactive_session_id=result.proactive_session_id,
                    agent_name=agent_name,
                )
                await request_repo.update_request(
                    group_request,
                    next_agent_index=member.position + 1,
                )
            else:
                logger.error("Queued sequential response missing request correlation data")
            return

        response = result.response if result else None

        if response:
            # Add to accumulated context for next agents
            accumulated_context.append({
                "role": "assistant",
                "agent": agent_name,
                "content": response,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Update last response time
            service = GroupService(db)
            await service.update_member_response_time(group.id, agent_name)
            
            # Mark done
            message_queue.mark_agent_done(group.id, agent_name)
            
            # Send response
            await websocket.send_json({
                "type": "agent_response",
                "group_id": str(group.id),
                "agent_name": agent_name,
                "content": response,
                "position": member.position,
                "is_last": member.position == len(members) - 1
            })
        else:
            # Agent failed to respond
            await websocket.send_json({
                "type": "agent_error",
                "group_id": str(group.id),
                "agent_name": agent_name,
                "error": "Failed to get response"
            })
    
    # Sequence complete
    await websocket.send_json({
        "type": "sequence_complete",
        "group_id": str(group.id),
        "agents_responded": len(accumulated_context)
    })

    message_queue.clear(group.id)


# Global instance (or inject via dependency)
message_queue = MessageQueue()
