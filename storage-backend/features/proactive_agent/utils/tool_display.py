"""Tool display text formatting for proactive agent."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


def format_tool_display_text(
    tool_name: Optional[str],
    tool_input: Optional[Dict[str, Any]],
    is_complete: bool,
) -> str:
    """Format tool event into user-friendly display text for frontend."""
    if not tool_name:
        return "✓ Done" if is_complete else "Working..."

    if tool_name == "Bash":
        return _format_bash_tool(tool_input, is_complete)

    if tool_name == "Read":
        path = (tool_input or {}).get("file_path", "file")
        filename = path.rsplit("/", 1)[-1] if "/" in path else path
        return f"✓ Read {filename}" if is_complete else f"Reading {filename}..."

    if tool_name == "WebSearch":
        query = (tool_input or {}).get("query", "web")
        if len(query) > 30:
            query = query[:27] + "..."
        return f"✓ Searched: {query}" if is_complete else f"Searching: {query}..."

    if tool_name == "WebFetch":
        url = (tool_input or {}).get("url", "")
        domain_match = re.search(r"https?://([^/]+)", url)
        domain = domain_match.group(1) if domain_match else "web"
        return f"✓ Fetched {domain}" if is_complete else f"Fetching {domain}..."

    if tool_name == "Glob":
        pattern = (tool_input or {}).get("pattern", "*")
        return f"✓ Found files: {pattern}" if is_complete else f"Finding: {pattern}..."

    if tool_name == "Grep":
        pattern = (tool_input or {}).get("pattern", "")
        if len(pattern) > 20:
            pattern = pattern[:17] + "..."
        return f"✓ Searched: {pattern}" if is_complete else f"Searching: {pattern}..."

    # Default for other tools
    return f"✓ {tool_name}" if is_complete else f"{tool_name}..."


def _format_bash_tool(
    tool_input: Optional[Dict[str, Any]],
    is_complete: bool,
) -> str:
    """Format Bash tool into display text.

    Claude Code provides both 'command' and 'description' fields.
    Prefer 'description' as it's a human-readable summary.
    """
    inputs = tool_input or {}

    # First, check for description field (Claude Code provides this)
    description = inputs.get("description", "")
    if description:
        # Clean up for display (truncate if too long)
        if len(description) > 40:
            description = description[:37] + "..."
        return f"✓ {description}" if is_complete else f"{description}..."

    # Fall back to parsing command (original logic)
    command = inputs.get("command", "")
    # Extract script name from various formats:
    # ./scripts/check_weather.sh, scripts/foo-bar.sh, /path/to/my_script.sh
    match = re.search(r"([a-zA-Z0-9_-]+)\.sh", command)
    if match:
        script_name = match.group(1)
        # Remove common prefixes like "check_" or "run_"
        display_name = re.sub(r"^(check_|run_|get_|do_)", "", script_name)
        return f"✓ Executed {display_name}" if is_complete else f"Running {display_name}..."
    # Fallback: show first word of command (truncated)
    first_word = command.split()[0] if command.split() else "command"
    if first_word.startswith("./"):
        first_word = first_word[2:]
    if len(first_word) > 20:
        first_word = first_word[:17] + "..."
    return f"✓ Executed {first_word}" if is_complete else f"Running {first_word}..."


__all__ = ["format_tool_display_text"]
