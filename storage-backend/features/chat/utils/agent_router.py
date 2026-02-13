"""Agent routing utility for multi-agent group chats.

Routes all agent messages to OpenClaw Gateway unconditionally.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def format_group_message(
    agent_name: str,
    user_message: str,
    group_metadata: Dict[str, Any],
) -> str:
    """
    Build the full message for a group chat agent with delta-only context.

    Only includes accumulated_context from the current round (other agents'
    responses this turn), NOT full DB history.  OpenClaw maintains its own
    session memory, so repeating old messages is wasteful.

    Produces:
    1. Group context hint (role, mode, participants, position)
    2. Sequential hint if present
    3. Transcript of this-round agent responses (from accumulated_context)
    4. The current user message
    5. Turn prompt for non-first agents with prior responses
    """
    mode = group_metadata.get("mode", "unknown")
    agents = group_metadata.get("agents", [])
    position = group_metadata.get("your_position", 0)

    others = ", ".join(a for a in agents if a.lower() != agent_name.lower())
    context_hint = (
        f"[You are {agent_name} in a group chat. "
        f"Mode: {mode}. "
        f"Other participants: {others}. "
        f"Your speaking position: {position}]"
    )

    parts: list[str] = [context_hint]

    sequential_hint = group_metadata.get("sequential_hint")
    if sequential_hint:
        parts.append(sequential_hint)

    # Use only this-round accumulated responses (delta), not full DB history
    accumulated = group_metadata.get("accumulated_context", [])
    agent_responses = [m for m in accumulated if m.get("role") == "assistant" and m.get("agent")]

    if agent_responses:
        transcript_lines = ["Other agents this round:", ""]
        for msg in agent_responses:
            transcript_lines.append(f"{msg['agent']} responded:\n{msg.get('content', '')}")
            transcript_lines.append("")
        parts.append("\n".join(transcript_lines).rstrip())

    # Always include the current user message
    if agent_responses and position > 0:
        parts.append(f"User said:\n{user_message}")
        parts.append("Now it's your turn to respond.")
    else:
        parts.append(user_message)

    return "\n\n".join(parts)


@dataclass(frozen=True)
class AgentRouteResult:
    response: Optional[str]
    queued: bool
    proactive_session_id: Optional[str] = None


async def route_to_openclaw_agent(
    agent_name: str,
    message: str,
    context: list,
    session_id: str,
    user_id: int,
    group_metadata: Optional[Dict[str, Any]] = None,
    timeout_seconds: float = 120.0,
) -> str:
    """
    Route message to OpenClaw-based agent and collect response.
    
    Uses the OpenClaw streaming adapter but collects text chunks
    into a complete response string.
    
    Args:
        agent_name: Name of the agent (e.g., "sherlock")
        message: User message to send
        context: List of previous messages for context
        session_id: Session ID for the conversation
        user_id: User ID
        group_metadata: Optional group context info
        timeout_seconds: Maximum time to wait for response
        
    Returns:
        Complete response string from the agent
        
    Raises:
        Exception: If OpenClaw is unavailable or request fails
    """
    from features.proactive_agent.openclaw.config import is_openclaw_enabled
    from features.proactive_agent.openclaw.session import get_openclaw_session_manager
    
    if not is_openclaw_enabled():
        raise RuntimeError("OpenClaw is not enabled on this server")
    
    logger.info(
        "Routing to OpenClaw agent: agent=%s, user=%s, session=%s",
        agent_name,
        user_id,
        session_id[:8] if session_id else "none",
    )
    
    # Prepare message with group context
    if group_metadata:
        formatted_message = format_group_message(agent_name, message, group_metadata)
    else:
        formatted_message = message
    
    # Get OpenClaw adapter
    session_manager = await get_openclaw_session_manager()
    adapter = await session_manager.get_adapter()
    
    # Create response collector
    response_chunks: list[str] = []
    response_complete = asyncio.Event()
    response_error: Optional[str] = None
    
    async def on_stream_start(session_id: str) -> None:
        logger.debug("OpenClaw stream started for agent %s", agent_name)
    
    async def on_text_chunk(text: str) -> None:
        response_chunks.append(text)
    
    async def on_stream_end(session_id: str, message_id: str, final_text: str) -> None:
        # final_text is the COMPLETE accumulated response - use it as authoritative
        # Clear chunks and use final_text since it's the full response
        if final_text:
            response_chunks.clear()
            response_chunks.append(final_text)
        response_complete.set()
    
    async def on_error(error_msg: str) -> None:
        nonlocal response_error
        response_error = error_msg
        response_complete.set()
    
    # Build session key for OpenClaw
    # Use a group-specific session key to isolate group context
    session_key = f"agent:{agent_name}:{session_id}"
    
    try:
        run_id = await adapter.send_message(
            user_id=user_id,
            session_id=session_id,
            session_key=session_key,
            message=formatted_message,
            on_stream_start=on_stream_start,
            on_text_chunk=on_text_chunk,
            on_stream_end=on_stream_end,
            on_error=on_error,
        )
        
        # Wait for response with timeout
        try:
            await asyncio.wait_for(response_complete.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.error("OpenClaw response timeout for agent %s after %ss", agent_name, timeout_seconds)
            # Try to abort the stream
            try:
                await adapter.abort(run_id)
            except Exception:
                pass
            raise TimeoutError(f"Agent {agent_name} response timed out after {timeout_seconds}s")
        
        if response_error:
            raise RuntimeError(f"Agent {agent_name} error: {response_error}")
        
        # Combine collected chunks
        full_response = "".join(response_chunks)
        
        if not full_response:
            logger.warning("Empty response from OpenClaw agent %s", agent_name)
            return f"[{agent_name} had no response]"
        
        logger.info(
            "OpenClaw agent %s responded: %d chars",
            agent_name,
            len(full_response),
        )
        return full_response
        
    except Exception as e:
        logger.error("OpenClaw routing failed for %s: %s", agent_name, e)
        raise


async def route_to_agent(
    agent_name: str,
    payload: Dict[str, Any],
    session_id: str,
    user_id: int,
) -> AgentRouteResult:
    """
    Route message to agent via OpenClaw Gateway.

    This is the main entry point for group chat routing.
    All agents route to OpenClaw unconditionally.

    Args:
        agent_name: Name of target agent (sherlock, bugsy, etc.)
        payload: Message payload with:
            - user_message: The message text
            - context: List of previous messages
            - group_metadata: Group info (mode, agents, position)
        session_id: Current session ID
        user_id: Current user ID

    Returns:
        AgentRouteResult with the agent's response

    Raises:
        Exception: If routing fails
    """
    # Extract payload fields
    user_message = payload.get("user_message", "")
    context = payload.get("context", [])
    group_metadata = payload.get("group_metadata", {})

    logger.info("Routing to OpenClaw agent: %s", agent_name)
    response = await route_to_openclaw_agent(
        agent_name=agent_name,
        message=user_message,
        context=context,
        session_id=session_id,
        user_id=user_id,
        group_metadata=group_metadata,
    )
    return AgentRouteResult(response=response, queued=False, proactive_session_id=None)
