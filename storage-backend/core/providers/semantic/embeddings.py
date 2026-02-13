from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any

from openai import AsyncOpenAI

from config.semantic_search.embeddings import (
    DIMENSIONS as DEFAULT_EMBEDDING_DIMENSIONS,
    MODEL as DEFAULT_EMBEDDING_MODEL,
    TIMEOUT as DEFAULT_EMBEDDING_TIMEOUT,
)
from config.api_keys import OPENAI_API_KEY
from core.exceptions import ProviderError

logger = logging.getLogger(__name__)

# LRU cache for embeddings (limit: 1000 queries ≈ ~2MB)
_embedding_cache: OrderedDict[str, list[float]] = OrderedDict()
_cache_max_size = 1000
_cache_hits = 0
_cache_misses = 0


def _evict_if_necessary() -> None:
    """Ensure cache stays within the configured maximum size."""

    global _embedding_cache

    while len(_embedding_cache) > _cache_max_size:
        _embedding_cache.popitem(last=False)
        logger.debug(
            "Embedding cache evicted oldest entry",
            extra={"size": len(_embedding_cache)},
        )


def get_cache_key(text: str, model: str) -> str:
    """Generate deterministic cache key for a text/model pair."""

    content = f"{model}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()


def get_cache_hit_rate() -> float:
    """Return current cache hit rate."""

    total = _cache_hits + _cache_misses
    return _cache_hits / total if total else 0.0


def get_cache_stats() -> dict[str, Any]:
    """Expose cache statistics for diagnostics."""

    return {
        "size": len(_embedding_cache),
        "max_size": _cache_max_size,
        "hits": _cache_hits,
        "misses": _cache_misses,
        "hit_rate": get_cache_hit_rate(),
    }


def clear_embedding_cache() -> None:
    """Clear embedding cache (useful for tests or maintenance)."""

    global _embedding_cache, _cache_hits, _cache_misses
    _embedding_cache.clear()
    _cache_hits = 0
    _cache_misses = 0
    logger.info("Embedding cache cleared")


def cached_embedding(func):
    """Decorator adding simple LRU caching to embedding calls.
    When you call generate_embedding(text):
    │
    ├─ Check: Is this text already in the cache?
    │  ├─ YES → Cache HIT: Return the cached embedding instantly (no API call)
    │  └─ NO  → Cache MISS: Call OpenAI API to generate the embedding
    │
    └─ Store the generated embedding in cache for next time
    """

    @functools.wraps(func)
    async def wrapper(self, text: str, *args, **kwargs):  # type: ignore[override]
        global _cache_hits, _cache_misses

        cache_key = get_cache_key(text, self.model)

        if cache_key in _embedding_cache:
            _cache_hits += 1
            _embedding_cache.move_to_end(cache_key)
            logger.debug(
                "Embedding cache HIT",
                extra={"hit_rate": f"{get_cache_hit_rate():.1%}"},
            )
            return _embedding_cache[cache_key]

        _cache_misses += 1
        logger.debug(
            "Embedding cache miss, generating new embedding",
            extra={"hit_rate": f"{get_cache_hit_rate():.1%}"},
        )

        embedding = await func(self, text, *args, **kwargs)

        _embedding_cache[cache_key] = embedding
        _embedding_cache.move_to_end(cache_key)
        _evict_if_necessary()
        return embedding

    return wrapper


class EmbeddingProvider(ABC):
    """Abstract embedding generator."""

    @abstractmethod
    async def generate(self, text: str) -> list[float]:
        """Generate embedding vector for text."""

    @abstractmethod
    async def generate_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings implementation using the async OpenAI SDK."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        api_key: str = OPENAI_API_KEY,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
        timeout: float | None = None,
    ) -> None:
        if client is None:
            if not api_key:
                raise ValueError("OpenAI API key is required for embeddings")
            client = AsyncOpenAI(api_key=api_key)

        self.client = client
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout or DEFAULT_EMBEDDING_TIMEOUT

        logger.info(
            f"🔍 EMBEDDING PROVIDER INIT: model={model}, dimensions={dimensions}, timeout={self.timeout}"
        )

    @cached_embedding
    async def generate(self, text: str) -> list[float]:
        """Generate an embedding for a single text value."""

        try:
            response = await asyncio.wait_for(
                self.client.embeddings.create(
                    model=self.model,
                    input=text,
                    dimensions=self.dimensions,
                ),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError as exc:
            logger.error(
                "Embedding generation timeout",
                extra={"timeout": self.timeout},
            )
            raise ProviderError(f"Embedding timeout after {self.timeout}s") from exc
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("Failed to generate embedding", exc_info=True)
            raise ProviderError(f"OpenAI embedding failed: {exc}") from exc

        embedding = response.data[0].embedding  # type: ignore[index]
        text_preview = text[:50] + "..." if len(text) > 50 else text
        logger.info(
            f"🔍 EMBEDDING GENERATED: model={self.model}, "
            f"requested_dims={self.dimensions}, actual_length={len(embedding)}, "
            f"query='{text_preview}'"
        )
        return list(embedding)

    async def generate_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts using batched API calls."""

        if not texts:
            return []

        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            try:
                response = await asyncio.wait_for(
                    self.client.embeddings.create(
                        model=self.model,
                        input=batch,
                        dimensions=self.dimensions,
                    ),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError as exc:
                logger.error(
                    "Batch embedding generation timeout",
                    extra={
                        "timeout": self.timeout,
                        "batch": start // batch_size + 1,
                    },
                )
                raise ProviderError(
                    f"Batch embedding timeout after {self.timeout}s"
                ) from exc
            except Exception as exc:  # pragma: no cover - network errors
                logger.error(
                    "Failed to generate batch embeddings",
                    exc_info=True,
                    extra={"batch": start // batch_size + 1},
                )
                raise ProviderError(f"Batch embedding failed: {exc}") from exc

            batch_embeddings = [list(item.embedding) for item in response.data]
            embeddings.extend(batch_embeddings)
            logger.debug(
                "Generated batch embeddings",
                extra={
                    "batch_index": start // batch_size + 1,
                    "batch_size": len(batch_embeddings),
                },
            )

            if start + batch_size < len(texts):
                await asyncio.sleep(0.1)

        logger.info("Generated %s embeddings", len(embeddings))
        return embeddings


__all__ = [
    "EmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "clear_embedding_cache",
    "get_cache_stats",
    "get_cache_hit_rate",
]
