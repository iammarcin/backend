"""Utilities for extracting and stripping thinking tags from content."""

from __future__ import annotations

import re
from typing import Optional

# Pattern to match <thinking>...</thinking> blocks (including multiline)
THINKING_PATTERN = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL)


def extract_thinking_tags(content: str) -> Optional[str]:
    """Extract thinking content from <thinking>...</thinking> blocks.

    Returns the combined thinking content, or None if no thinking blocks found.
    """
    if not content:
        return None
    matches = THINKING_PATTERN.findall(content)
    if not matches:
        return None
    # Combine all thinking blocks with newlines
    return "\n\n".join(match.strip() for match in matches if match.strip())


def strip_thinking_tags(content: str) -> str:
    """Remove <thinking>...</thinking> blocks from content.

    Thinking blocks are sent separately via streaming and should not
    be stored in the final message content.
    """
    if not content:
        return content
    return re.sub(r"<thinking>.*?</thinking>\s*", "", content, flags=re.DOTALL).strip()


__all__ = ["THINKING_PATTERN", "extract_thinking_tags", "strip_thinking_tags"]
