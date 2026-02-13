"""Factory helpers for semantic search providers."""

from __future__ import annotations

import logging
from typing import Dict, Type

from openai import AsyncOpenAI

from config.semantic_search import defaults as semantic_defaults
from config.semantic_search.embeddings import (
    DIMENSIONS as SEMANTIC_EMBEDDING_DIMENSIONS,
    MODEL as SEMANTIC_EMBEDDING_MODEL,
    TIMEOUT as SEMANTIC_EMBEDDING_TIMEOUT,
)
from config.semantic_search.qdrant import COLLECTION_NAME as QDRANT_COLLECTION_NAME
from core.clients.ai import ai_clients
from core.clients.semantic import get_qdrant_client
from config.api_keys import OPENAI_API_KEY

from .base import BaseSemanticProvider
from .bm25 import BM25SparseVectorProvider
from .multi_collection_provider import MultiCollectionSemanticProvider
from .embeddings import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


_PROVIDER_REGISTRY: Dict[str, Type[BaseSemanticProvider]] = {}
_PROVIDER_CACHE: Dict[str, BaseSemanticProvider] = {}


def register_semantic_provider(name: str, provider_class: Type[BaseSemanticProvider]) -> None:
    """Register a semantic provider implementation."""
    normalised = name.lower()
    _PROVIDER_REGISTRY[normalised] = provider_class
    logger.debug("Registered semantic provider", extra={"provider_name": normalised, "class": provider_class.__name__})


def get_semantic_provider(provider_name: str = "qdrant") -> BaseSemanticProvider:
    """Get a semantic search provider instance."""
    normalised = provider_name.lower()

    if normalised in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[normalised]

    if normalised not in _PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown semantic provider: {provider_name}. Available: {list(_PROVIDER_REGISTRY.keys())}"
        )

    provider_class = _PROVIDER_REGISTRY[normalised]

    openai_client = ai_clients.get("openai_async")
    client_instance = openai_client if isinstance(openai_client, AsyncOpenAI) else None

    logger.info(
        f"🔍 SEMANTIC SEARCH CONFIG: model={SEMANTIC_EMBEDDING_MODEL}, "
        f"dimensions={SEMANTIC_EMBEDDING_DIMENSIONS}, timeout={SEMANTIC_EMBEDDING_TIMEOUT}"
    )

    embedding_provider = OpenAIEmbeddingProvider(
        client=client_instance,
        api_key=OPENAI_API_KEY,
        model=SEMANTIC_EMBEDDING_MODEL,
        dimensions=SEMANTIC_EMBEDDING_DIMENSIONS,
        timeout=SEMANTIC_EMBEDDING_TIMEOUT,
    )

    # Create sparse vector provider
    sparse_provider = BM25SparseVectorProvider(
        k1=1.2,  # Can make configurable
        b=0.75,
    )

    if normalised == "qdrant":
        base_provider = provider_class(
            client=get_qdrant_client(),
            collection_name=QDRANT_COLLECTION_NAME,
            embedding_provider=embedding_provider,
            sparse_provider=sparse_provider,  # New
            timeout=semantic_defaults.SEARCH_TIMEOUT,
        )
        provider = MultiCollectionSemanticProvider(base_provider)
    else:  # pragma: no cover - future providers
        raise NotImplementedError(f"Provider {provider_name} initialisation not implemented")

    _PROVIDER_CACHE[normalised] = provider
    logger.info("Created semantic provider", extra={"provider_name": normalised})
    return provider


__all__ = ["get_semantic_provider", "register_semantic_provider"]
