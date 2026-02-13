"""Schema helpers for semantic search feature."""

from __future__ import annotations

from enum import Enum


class SemanticSearchMode(str, Enum):
    """Supported semantic search modes."""

    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    KEYWORD = "keyword"
    SESSION_SEMANTIC = "session_semantic"
    SESSION_HYBRID = "session_hybrid"
    MULTI_TIER = "multi_tier"


__all__ = ["SemanticSearchMode"]
