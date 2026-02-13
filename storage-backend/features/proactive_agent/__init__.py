"""Proactive Agent feature module - Sherlock AI assistant."""

from features.proactive_agent.routes import router
from features.proactive_agent.streaming_registry import (
    ProactiveStreamingSession,
    create_forwarder_task,
    get_session,
    register_session,
    remove_session,
)

__all__ = [
    "router",
    "ProactiveStreamingSession",
    "register_session",
    "get_session",
    "remove_session",
    "create_forwarder_task",
]
