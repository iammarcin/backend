"""Context manager helpers for the deep research workflow."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import HTTPException

try:  # pragma: no cover - placeholder until dedicated error exposed
    from core.providers.text.perplexity import (  # type: ignore[attr-defined]
        PerplexityProviderError,
    )
except ImportError:  # pragma: no cover - fallback when provider error not defined
    from core.exceptions import ProviderError as PerplexityProviderError  # type: ignore


logger = logging.getLogger("features.chat.services.streaming.deep_research")


@asynccontextmanager
async def deep_research_context():
    """Context manager for error handling and cleanup."""

    try:
        yield
    except PerplexityProviderError as exc:
        logger.error("Deep research provider error: %s", exc)
        raise HTTPException(status_code=502, detail="Research provider unavailable") from exc
    except Exception as exc:  # pragma: no cover - placeholder until specific errors wired
        logger.error("Deep research orchestration error: %s", exc)
        raise HTTPException(status_code=500, detail="Deep research failed") from exc


__all__ = ["deep_research_context"]
