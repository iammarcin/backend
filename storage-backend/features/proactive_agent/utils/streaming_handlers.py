"""Streaming event handlers for proactive agent.

This module re-exports handlers from submodules for backward compatibility.
"""

from features.proactive_agent.utils.content_handlers import (
    handle_text_chunk,
    handle_thinking_chunk,
)
from features.proactive_agent.utils.lifecycle_handlers import (
    handle_stream_end,
    handle_stream_start,
)
from features.proactive_agent.utils.tool_display import format_tool_display_text
from features.proactive_agent.utils.tool_handlers import (
    handle_tool_result,
    handle_tool_start,
)

__all__ = [
    "format_tool_display_text",
    "handle_stream_start",
    "handle_text_chunk",
    "handle_thinking_chunk",
    "handle_tool_start",
    "handle_tool_result",
    "handle_stream_end",
]
