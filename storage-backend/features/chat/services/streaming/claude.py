"""Helpers for Claude-related metadata in completion events.

Note: The original sidecar-specific functionality has been removed.
This module now only provides metadata building for completion events.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_completion_metadata(
    claude_session_id: Optional[str],
    claude_code_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Compose metadata payload for completion events.

    This metadata structure is used by proactive agent flows (Sherlock/Bugsy)
    to track session continuity.
    """

    metadata: Dict[str, Any] = {}
    if claude_session_id:
        metadata["claude_session_id"] = claude_session_id
    if claude_code_data:
        metadata["claude_code_data"] = claude_code_data
    return metadata


__all__ = ["build_completion_metadata"]
