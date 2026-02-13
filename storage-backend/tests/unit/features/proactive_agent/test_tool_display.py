"""Unit tests for tool display text formatting."""

from __future__ import annotations

import pytest

from features.proactive_agent.utils.tool_display import format_tool_display_text


class TestFormatToolDisplayText:
    """Test main format function."""

    def test_no_tool_name_working(self) -> None:
        result = format_tool_display_text(None, None, is_complete=False)
        assert result == "Working..."

    def test_no_tool_name_done(self) -> None:
        result = format_tool_display_text(None, None, is_complete=True)
        assert result == "✓ Done"

    def test_unknown_tool_in_progress(self) -> None:
        result = format_tool_display_text("CustomTool", {}, is_complete=False)
        assert result == "CustomTool..."

    def test_unknown_tool_complete(self) -> None:
        result = format_tool_display_text("CustomTool", {}, is_complete=True)
        assert result == "✓ CustomTool"


class TestBashToolDisplay:
    """Test Bash tool display text generation."""

    def test_bash_with_description_in_progress(self) -> None:
        """Description field from Claude Code should be used."""
        result = format_tool_display_text(
            "Bash",
            {"command": "echo hello", "description": "Print greeting"},
            is_complete=False,
        )
        assert result == "Print greeting..."

    def test_bash_with_description_complete(self) -> None:
        result = format_tool_display_text(
            "Bash",
            {"command": "echo hello", "description": "Print greeting"},
            is_complete=True,
        )
        assert result == "✓ Print greeting"

    def test_bash_with_long_description_truncates(self) -> None:
        """Long descriptions should be truncated."""
        result = format_tool_display_text(
            "Bash",
            {"description": "This is a very long description that should be truncated for display"},
            is_complete=False,
        )
        assert len(result) <= 44  # 40 chars + "..."
        assert result.endswith("...")

    def test_bash_with_script_fallback(self) -> None:
        """When no description, extract script name from command."""
        result = format_tool_display_text(
            "Bash",
            {"command": "./scripts/check_weather.sh --location NYC"},
            is_complete=False,
        )
        assert result == "Running weather..."

    def test_bash_with_script_complete(self) -> None:
        result = format_tool_display_text(
            "Bash",
            {"command": "./scripts/generate_chart.sh --type line"},
            is_complete=True,
        )
        assert result == "✓ Executed generate_chart"

    def test_bash_removes_common_prefixes(self) -> None:
        """check_, run_, get_, do_ prefixes should be stripped."""
        result = format_tool_display_text(
            "Bash",
            {"command": "./scripts/run_tests.sh"},
            is_complete=False,
        )
        assert result == "Running tests..."

    def test_bash_empty_input_in_progress(self) -> None:
        """Empty input (early tool_start) falls back to 'command'."""
        result = format_tool_display_text("Bash", {}, is_complete=False)
        assert result == "Running command..."

    def test_bash_empty_input_complete(self) -> None:
        result = format_tool_display_text("Bash", {}, is_complete=True)
        assert result == "✓ Executed command"

    def test_bash_null_input(self) -> None:
        result = format_tool_display_text("Bash", None, is_complete=False)
        assert result == "Running command..."

    def test_bash_simple_command(self) -> None:
        """Non-script commands use first word."""
        result = format_tool_display_text(
            "Bash",
            {"command": "pytest tests/"},
            is_complete=False,
        )
        assert result == "Running pytest..."

    def test_bash_long_command_truncates(self) -> None:
        result = format_tool_display_text(
            "Bash",
            {"command": "verylongcommandnamethatexceedstwentycharacters --option value"},
            is_complete=False,
        )
        assert "..." in result


class TestReadToolDisplay:
    """Test Read tool display."""

    def test_read_with_path(self) -> None:
        result = format_tool_display_text(
            "Read",
            {"file_path": "/home/user/project/main.py"},
            is_complete=False,
        )
        assert result == "Reading main.py..."

    def test_read_complete(self) -> None:
        result = format_tool_display_text(
            "Read",
            {"file_path": "/home/user/project/main.py"},
            is_complete=True,
        )
        assert result == "✓ Read main.py"


class TestWebSearchToolDisplay:
    """Test WebSearch tool display."""

    def test_web_search_in_progress(self) -> None:
        result = format_tool_display_text(
            "WebSearch",
            {"query": "latest AI news"},
            is_complete=False,
        )
        assert result == "Searching: latest AI news..."

    def test_web_search_long_query_truncates(self) -> None:
        result = format_tool_display_text(
            "WebSearch",
            {"query": "This is a very long search query that should be truncated"},
            is_complete=False,
        )
        assert "..." in result
        assert len(result.replace("Searching: ", "").replace("...", "")) <= 30


class TestWebFetchToolDisplay:
    """Test WebFetch tool display."""

    def test_web_fetch_extracts_domain(self) -> None:
        result = format_tool_display_text(
            "WebFetch",
            {"url": "https://example.com/path/to/page"},
            is_complete=False,
        )
        assert result == "Fetching example.com..."


class TestGlobToolDisplay:
    """Test Glob tool display."""

    def test_glob_in_progress(self) -> None:
        result = format_tool_display_text(
            "Glob",
            {"pattern": "**/*.py"},
            is_complete=False,
        )
        assert result == "Finding: **/*.py..."


class TestGrepToolDisplay:
    """Test Grep tool display."""

    def test_grep_in_progress(self) -> None:
        result = format_tool_display_text(
            "Grep",
            {"pattern": "def main"},
            is_complete=False,
        )
        assert result == "Searching: def main..."

    def test_grep_long_pattern_truncates(self) -> None:
        result = format_tool_display_text(
            "Grep",
            {"pattern": "some very long search pattern that exceeds limit"},
            is_complete=False,
        )
        assert "..." in result
