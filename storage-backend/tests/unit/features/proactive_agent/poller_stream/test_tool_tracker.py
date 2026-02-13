import pytest
from features.proactive_agent.poller_stream.tool_tracker import (
    ToolTracker, ToolInfo
)


class TestToolTracker:

    def test_register_and_get_tool(self):
        """Register a tool and retrieve it."""
        tracker = ToolTracker()
        tracker.register_tool("toolu_123", "Bash", {"command": "ls -la"})

        info = tracker.get_tool("toolu_123")
        assert info is not None
        assert info.name == "Bash"
        assert info.input == {"command": "ls -la"}
        assert info.should_skip_markers is False

    def test_get_unknown_tool(self):
        """Getting unknown tool returns None."""
        tracker = ToolTracker()
        assert tracker.get_tool("unknown") is None

    def test_complete_tool(self):
        """Completing a tool removes it from tracking."""
        tracker = ToolTracker()
        tracker.register_tool("toolu_123", "Bash", {})

        tracker.complete_tool("toolu_123")

        assert tracker.get_tool("toolu_123") is None

    def test_complete_unknown_tool_no_error(self):
        """Completing unknown tool doesn't raise."""
        tracker = ToolTracker()
        tracker.complete_tool("unknown")  # Should not raise

    def test_read_tool_skips_markers(self):
        """Read tool should skip marker detection."""
        tracker = ToolTracker()
        tracker.register_tool("toolu_456", "Read", {"file_path": "/tmp/file.txt"})

        info = tracker.get_tool("toolu_456")
        assert info.should_skip_markers is True

    def test_bash_tool_does_not_skip_markers(self):
        """Bash tool should NOT skip marker detection."""
        tracker = ToolTracker()
        tracker.register_tool("toolu_789", "Bash", {"command": "echo test"})

        info = tracker.get_tool("toolu_789")
        assert info.should_skip_markers is False

    def test_multiple_tools(self):
        """Track multiple tools simultaneously."""
        tracker = ToolTracker()
        tracker.register_tool("tool_1", "Bash", {"command": "ls"})
        tracker.register_tool("tool_2", "Read", {"file_path": "/x"})
        tracker.register_tool("tool_3", "Skill", {"skill": "chart"})

        assert tracker.get_tool("tool_1").name == "Bash"
        assert tracker.get_tool("tool_2").name == "Read"
        assert tracker.get_tool("tool_3").name == "Skill"

        active = tracker.get_active_tools()
        assert len(active) == 3

    def test_complete_in_any_order(self):
        """Tools can complete in any order."""
        tracker = ToolTracker()
        tracker.register_tool("tool_1", "Bash", {})
        tracker.register_tool("tool_2", "Read", {})
        tracker.register_tool("tool_3", "Skill", {})

        # Complete out of order
        tracker.complete_tool("tool_2")
        tracker.complete_tool("tool_1")
        tracker.complete_tool("tool_3")

        assert len(tracker.get_active_tools()) == 0

    def test_clear(self):
        """Clear removes all tools."""
        tracker = ToolTracker()
        tracker.register_tool("tool_1", "Bash", {})
        tracker.register_tool("tool_2", "Read", {})

        tracker.clear()

        assert len(tracker.get_active_tools()) == 0

    def test_overwrite_existing_tool(self):
        """Registering same ID overwrites."""
        tracker = ToolTracker()
        tracker.register_tool("tool_1", "Bash", {"v": 1})
        tracker.register_tool("tool_1", "Read", {"v": 2})

        info = tracker.get_tool("tool_1")
        assert info.name == "Read"
        assert info.input == {"v": 2}

    def test_empty_input(self):
        """Tool with empty input works."""
        tracker = ToolTracker()
        tracker.register_tool("tool_1", "Bash", {})

        info = tracker.get_tool("tool_1")
        assert info.input == {}

    def test_complex_input(self):
        """Tool with complex nested input works."""
        tracker = ToolTracker()
        complex_input = {
            "command": "echo 'hello'",
            "options": {"timeout": 30, "env": {"FOO": "bar"}},
            "flags": ["--verbose", "--debug"]
        }
        tracker.register_tool("tool_1", "Bash", complex_input)

        info = tracker.get_tool("tool_1")
        assert info.input == complex_input
