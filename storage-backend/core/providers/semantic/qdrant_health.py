"""Health check helpers for the Qdrant semantic provider."""

from __future__ import annotations

import asyncio
import time
from typing import Any, TYPE_CHECKING


if TYPE_CHECKING:  # pragma: no cover - typing only
    from qdrant_client import AsyncQdrantClient

    from .circuit_breaker import CircuitBreaker
    from .embeddings import EmbeddingProvider


async def run_health_check(
    *,
    client: "AsyncQdrantClient",
    collection_name: str,
    embedding_provider: "EmbeddingProvider",
    circuit_breaker: "CircuitBreaker",
) -> dict[str, Any]:
    """Run comprehensive provider health check."""

    health = {
        "healthy": False,
        "components": {
            "qdrant": {"status": "unknown"},
            "embeddings": {"status": "unknown"},
            "circuit_breaker": {"status": "unknown"},
        },
        "latency_ms": 0.0,
    }

    start_time = time.time()

    try:
        try:
            collection_info = await asyncio.wait_for(
                client.get_collection(collection_name),
                timeout=5.0,
            )
            health["components"]["qdrant"] = {
                "status": "healthy",
                "points_count": getattr(collection_info, "points_count", None),
                "vectors_count": getattr(collection_info, "vectors_count", None),
            }
        except Exception as exc:
            health["components"]["qdrant"] = {
                "status": "unhealthy",
                "error": str(exc),
            }

        try:
            test_embedding = await asyncio.wait_for(
                embedding_provider.generate("semantic health check"),
                timeout=5.0,
            )
            health["components"]["embeddings"] = {
                "status": "healthy",
                "dimensions": len(test_embedding),
            }
        except Exception as exc:
            health["components"]["embeddings"] = {
                "status": "unhealthy",
                "error": str(exc),
            }

        breaker_status = "healthy" if circuit_breaker.can_attempt() else "open"
        health["components"]["circuit_breaker"] = {
            "status": breaker_status,
            "failure_count": circuit_breaker.failure_count,
        }

        health["healthy"] = all(
            component.get("status") == "healthy"
            for component in health["components"].values()
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        health["error"] = str(exc)
    finally:
        health["latency_ms"] = (time.time() - start_time) * 1000

    if health["healthy"]:
        circuit_breaker.record_success()
    else:
        circuit_breaker.record_failure()

    return health


__all__ = ["run_health_check"]
