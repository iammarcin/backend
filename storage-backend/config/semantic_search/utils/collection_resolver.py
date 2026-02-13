"""Collection resolution helpers for semantic search."""

from __future__ import annotations

from ..defaults import (
    SEARCH_MODE_HYBRID,
    SEARCH_MODE_KEYWORD,
    SEARCH_MODE_SEMANTIC,
)
from ..qdrant import COLLECTION_HYBRID, COLLECTION_SEMANTIC

SEMANTIC_COLLECTION_MAPPING = {
    SEARCH_MODE_SEMANTIC: COLLECTION_SEMANTIC,
    SEARCH_MODE_HYBRID: COLLECTION_HYBRID,
    SEARCH_MODE_KEYWORD: COLLECTION_HYBRID,
}


def get_collection_for_mode(mode: str) -> str:
    """Return the Qdrant collection name for a given search mode."""

    normalized = (mode or "").strip().lower()
    if normalized in SEMANTIC_COLLECTION_MAPPING:
        return SEMANTIC_COLLECTION_MAPPING[normalized]
    raise ValueError(
        f"Unknown search mode: {mode}. Valid modes: {sorted(SEMANTIC_COLLECTION_MAPPING)}"
    )


__all__ = ["SEMANTIC_COLLECTION_MAPPING", "get_collection_for_mode"]
