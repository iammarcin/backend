"""Utilities for semantic search external clients."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

try:
    from qdrant_client import AsyncQdrantClient
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    AsyncQdrantClient = Any  # type: ignore[assignment]
    _IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    _IMPORT_ERROR = None


logger = logging.getLogger(__name__)

_qdrant_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    """Return a cached AsyncQdrantClient with connection pooling."""

    global _qdrant_client

    if _IMPORT_ERROR is not None:
        raise RuntimeError(
            "qdrant_client package is required for semantic search"
        ) from _IMPORT_ERROR

    if _qdrant_client is not None:
        return _qdrant_client

    # Lazy import to avoid circular dependency
    from core.config import settings

    if not settings.qdrant_url:
        raise ValueError("Qdrant URL must be configured")

    logger.info("Initialising Qdrant client with connection pooling")

    _qdrant_client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=settings.semantic_search_timeout,
        prefer_grpc=True,
        grpc_port=6334,
        https=settings.qdrant_url.startswith("https"),
        check_compatibility=False,
    )

    logger.info("Qdrant client initialised")
    return _qdrant_client


async def close_qdrant_client() -> None:
    """Close pooled Qdrant client when shutting down the application."""

    global _qdrant_client

    if _qdrant_client is None:
        return

    logger.info("Closing Qdrant client")
    try:
        # Close with timeout to avoid hanging on pending operations
        await asyncio.wait_for(_qdrant_client.close(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Qdrant client close timed out")
    except Exception as e:
        logger.warning(f"Error closing Qdrant client: {e}")
    finally:
        _qdrant_client = None
        logger.info("Qdrant client closed")


__all__ = ["get_qdrant_client", "close_qdrant_client"]
