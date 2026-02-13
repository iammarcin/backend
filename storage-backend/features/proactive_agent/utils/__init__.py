"""Utility modules for proactive agent feature.

M4 Cleanup Note: try_websocket_push_thinking is no longer exported as it was
only used by the legacy message_handler.receive_thinking method. The function
definition remains in websocket_push.py for reference.
"""

from features.proactive_agent.utils.thinking_tags import (
    THINKING_PATTERN,
    extract_thinking_tags,
    strip_thinking_tags,
)
from features.proactive_agent.utils.websocket_push import (
    try_websocket_push,
)
from features.proactive_agent.utils.tts_session import (
    complete_tts_session,
    cancel_tts_session,
    start_tts_session,
)
from features.proactive_agent.utils.streaming_handlers import (
    handle_stream_start,
    handle_text_chunk,
    handle_thinking_chunk,
    handle_tool_start,
    handle_tool_result,
    handle_stream_end,
)

__all__ = [
    # Thinking tags
    "THINKING_PATTERN",
    "extract_thinking_tags",
    "strip_thinking_tags",
    # WebSocket push
    "try_websocket_push",
    # TTS session
    "start_tts_session",
    "complete_tts_session",
    "cancel_tts_session",
    # Streaming handlers
    "handle_stream_start",
    "handle_text_chunk",
    "handle_thinking_chunk",
    "handle_tool_start",
    "handle_tool_result",
    "handle_stream_end",
]
