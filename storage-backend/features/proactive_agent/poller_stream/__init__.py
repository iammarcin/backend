"""Poller stream handling components for Sherlock True Dumb Pipe architecture."""

from .error_mapper import ERROR_MESSAGES, get_user_friendly_error
from .event_emitter import EventEmitter, StreamSession
from .heartbeat_emitter import HeartbeatEmitter
from .marker_detector import DetectedMarker, MarkerDetector, MarkerResult, MarkerType
from .ndjson_parser import EventType, NDJSONLineParser, ParsedEvent
from .schemas import CompleteMessage, ErrorMessage, InitMessage
from .special_event_handlers import (
    handle_chart_event,
    handle_component_update_event,
    handle_research_event,
    handle_scene_event,
)
from .stream_session import PollerStreamSession
from .thinking_parser import ChunkType, ParsedChunk, ThinkingParser
from .tool_tracker import ToolInfo, ToolTracker
from .websocket_handler import router as poller_stream_router

__all__ = [
    # Error Mapping
    "ERROR_MESSAGES",
    "get_user_friendly_error",
    # Event Emission
    "EventEmitter",
    "HeartbeatEmitter",
    "StreamSession",
    # Special Event Handlers
    "handle_chart_event",
    "handle_component_update_event",
    "handle_research_event",
    "handle_scene_event",
    # Parsers
    "ChunkType",
    "DetectedMarker",
    "EventType",
    "MarkerDetector",
    "MarkerResult",
    "MarkerType",
    "NDJSONLineParser",
    "ParsedChunk",
    "ParsedEvent",
    "ThinkingParser",
    "ToolInfo",
    "ToolTracker",
    # Schemas
    "CompleteMessage",
    "ErrorMessage",
    "InitMessage",
    # WebSocket
    "PollerStreamSession",
    "poller_stream_router",
]
