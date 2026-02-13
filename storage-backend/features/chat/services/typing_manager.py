"""Typing indicator management for group chats."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class TypingIndicatorManager:
    """
    Manages typing indicator state and emissions for group chats.
    
    Features:
    - Tracks which agents are typing per group
    - Auto-stops typing after timeout (failsafe)
    - Prevents stuck indicators
    """
    
    def __init__(self, timeout_seconds: int = 30):
        self._typing: Dict[str, Dict[str, bool]] = {}  # group_id -> agent -> is_typing
        self._tasks: Dict[str, asyncio.Task] = {}  # group_id:agent -> timeout task
        self._start_times: Dict[str, datetime] = {}  # group_id:agent -> start time
        self.timeout_seconds = timeout_seconds
    
    async def start_typing(
        self,
        websocket,
        group_id: str,
        agent_name: str,
        **extra
    ) -> None:
        """
        Emit typing start event and set auto-stop timeout.
        
        Args:
            websocket: WebSocket connection for sending events
            group_id: Group chat ID
            agent_name: Name of the typing agent
            **extra: Additional fields to include in the event
                - position: Position in sequence
                - total: Total agents in sequence
                - invoked_by: Who invoked this agent
                - role: 'leader' or 'listener'
        """
        key = f"{group_id}:{agent_name}"
        
        # Cancel existing timeout if any
        if key in self._tasks:
            self._tasks[key].cancel()
            try:
                await self._tasks[key]
            except asyncio.CancelledError:
                pass
        
        # Build event payload
        event = {
            "type": "agent_typing",
            "group_id": group_id,
            "agent_name": agent_name,
            **extra
        }
        
        # Emit typing event
        try:
            await websocket.send_json(event)
        except Exception as e:
            logger.warning(f"Failed to send typing event for {agent_name}: {e}")
        
        # Track state
        if group_id not in self._typing:
            self._typing[group_id] = {}
        self._typing[group_id][agent_name] = True
        self._start_times[key] = datetime.utcnow()
        
        # Set auto-stop timeout (failsafe)
        self._tasks[key] = asyncio.create_task(
            self._auto_stop(websocket, group_id, agent_name)
        )
        
        logger.debug(f"Started typing indicator for {agent_name} in group {group_id}")
    
    async def stop_typing(
        self,
        websocket,
        group_id: str,
        agent_name: str
    ) -> None:
        """
        Emit typing stop event and clear state.
        
        Args:
            websocket: WebSocket connection
            group_id: Group chat ID
            agent_name: Name of the agent
        """
        key = f"{group_id}:{agent_name}"
        
        # Cancel timeout task
        if key in self._tasks:
            self._tasks[key].cancel()
            try:
                await self._tasks[key]
            except asyncio.CancelledError:
                pass
            del self._tasks[key]
        
        # Clear start time
        self._start_times.pop(key, None)
        
        # Only emit if was actually typing
        if self._typing.get(group_id, {}).get(agent_name):
            try:
                await websocket.send_json({
                    "type": "agent_typing_stop",
                    "group_id": group_id,
                    "agent_name": agent_name
                })
            except Exception as e:
                logger.warning(f"Failed to send typing stop for {agent_name}: {e}")
            
            self._typing[group_id][agent_name] = False
            logger.debug(f"Stopped typing indicator for {agent_name} in group {group_id}")
    
    async def _auto_stop(
        self,
        websocket,
        group_id: str,
        agent_name: str
    ) -> None:
        """Auto-stop typing after timeout (failsafe for stuck indicators)."""
        try:
            await asyncio.sleep(self.timeout_seconds)
            logger.warning(
                f"Auto-stopping typing for {agent_name} in {group_id} after {self.timeout_seconds}s"
            )
            await self.stop_typing(websocket, group_id, agent_name)
        except asyncio.CancelledError:
            # Task was cancelled (normal stop)
            pass
    
    def is_typing(self, group_id: str, agent_name: str) -> bool:
        """Check if an agent is currently typing."""
        return self._typing.get(group_id, {}).get(agent_name, False)
    
    def get_typing_agents(self, group_id: str) -> List[str]:
        """Get list of currently typing agents in a group."""
        return [
            agent for agent, typing 
            in self._typing.get(group_id, {}).items() 
            if typing
        ]
    
    def get_typing_duration(self, group_id: str, agent_name: str) -> Optional[float]:
        """Get how long an agent has been typing (in seconds)."""
        key = f"{group_id}:{agent_name}"
        start = self._start_times.get(key)
        if start:
            return (datetime.utcnow() - start).total_seconds()
        return None
    
    async def stop_all_in_group(self, websocket, group_id: str) -> None:
        """Stop all typing indicators in a group (e.g., on user interrupt)."""
        agents = self.get_typing_agents(group_id)
        for agent in agents:
            await self.stop_typing(websocket, group_id, agent)
        logger.debug(f"Stopped all typing indicators in group {group_id}")
    
    def clear_group(self, group_id: str) -> None:
        """Clear all state for a group (cleanup)."""
        # Cancel all tasks for this group
        keys_to_remove = [k for k in self._tasks if k.startswith(f"{group_id}:")]
        for key in keys_to_remove:
            self._tasks[key].cancel()
            del self._tasks[key]
        
        # Clear state
        self._typing.pop(group_id, None)
        
        # Clear start times
        keys_to_remove = [k for k in self._start_times if k.startswith(f"{group_id}:")]
        for key in keys_to_remove:
            del self._start_times[key]


# Global singleton instance
typing_manager = TypingIndicatorManager()
