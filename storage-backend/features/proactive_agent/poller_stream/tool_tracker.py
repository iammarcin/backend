"""Tool use tracker for pairing tool_start with tool_result events."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolInfo:
    """Information about a registered tool use."""
    name: str
    input: dict[str, Any]
    should_skip_markers: bool


class ToolTracker:
    """Tracks active tool uses for pairing tool_start with tool_result."""

    SKIP_MARKER_TOOLS: set[str] = {"Read"}

    def __init__(self) -> None:
        """Initialize empty tracker."""
        self._active_tools: dict[str, ToolInfo] = {}

    def register_tool(self, tool_use_id: str, name: str, input_data: dict[str, Any]) -> None:
        """Register a tool use from assistant message."""
        should_skip = name in self.SKIP_MARKER_TOOLS
        self._active_tools[tool_use_id] = ToolInfo(name, input_data, should_skip)

    def get_tool(self, tool_use_id: str) -> ToolInfo | None:
        """Get tool info by ID. Returns None if not registered."""
        return self._active_tools.get(tool_use_id)

    def complete_tool(self, tool_use_id: str) -> None:
        """Mark tool as completed and remove from active tracking."""
        self._active_tools.pop(tool_use_id, None)

    def get_active_tools(self) -> dict[str, ToolInfo]:
        """Get all currently active (uncompleted) tools."""
        return dict(self._active_tools)

    def clear(self) -> None:
        """Clear all tracked tools."""
        self._active_tools.clear()
