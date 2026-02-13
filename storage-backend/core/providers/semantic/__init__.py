"""Semantic search provider package."""

from __future__ import annotations

from .batch_embeddings import BatchEmbeddingProvider, BatchRequest, BatchResult
from .base import BaseSemanticProvider
from .embeddings import EmbeddingProvider, OpenAIEmbeddingProvider
from .factory import get_semantic_provider, register_semantic_provider
from .schemas import SearchRequest, SearchResult

try:  # pragma: no cover - optional dependency wiring
    from .qdrant import QdrantSemanticProvider
except ModuleNotFoundError:
    QdrantSemanticProvider = None  # type: ignore[assignment]
    _QDRANT_AVAILABLE = False
else:
    _QDRANT_AVAILABLE = True

__all__ = [
    "BatchEmbeddingProvider",
    "BatchRequest",
    "BatchResult",
    "BaseSemanticProvider",
    "EmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "SearchRequest",
    "SearchResult",
    "get_semantic_provider",
    "register_semantic_provider",
]

if _QDRANT_AVAILABLE:
    __all__.append("QdrantSemanticProvider")
