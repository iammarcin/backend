"""Embedding configuration for semantic search."""

from __future__ import annotations

import os

MODEL = os.getenv("SEMANTIC_EMBEDDING_MODEL", "text-embedding-3-small")
DIMENSIONS = int(os.getenv("SEMANTIC_EMBEDDING_DIMENSIONS", "384"))
TIMEOUT = float(os.getenv("SEMANTIC_EMBEDDING_TIMEOUT", "5.0"))

__all__ = ["MODEL", "DIMENSIONS", "TIMEOUT"]
