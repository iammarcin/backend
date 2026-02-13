"""FastAPI dependency injection for semantic search service."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends

from config.semantic_search import defaults as semantic_defaults
from core.config import settings
from core.exceptions import ConfigurationError
from features.semantic_search.service import (
    SemanticSearchService,
    get_semantic_search_service,
)

logger = logging.getLogger(__name__)

# Re-export settings for test compatibility
from core.config import settings


async def get_semantic_search_service_dependency() -> SemanticSearchService | None:
    """Provide an initialized semantic search service or explicitly fail.

    Returns:
        SemanticSearchService | None: Returns None only when the feature flag
        disables semantic search. When enabled, a fully initialized service is
        returned or a ConfigurationError is raised.
    """
    if not settings.semantic_search_enabled:
        logger.debug("Semantic search disabled in settings")
        return None

    try:
        service = get_semantic_search_service()

        if not service._initialized:
            await service.initialize()

        return service

    except ConfigurationError:
        logger.error("Semantic search enabled but not configured properly")
        raise

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Failed to initialize semantic search service: %s", exc, exc_info=True
        )
        raise ConfigurationError(
            "Semantic search initialization failed. "
            "Check OPENAI_API_KEY and Qdrant configuration.",
            key="SEMANTIC_SEARCH_CONFIG",
        ) from exc


SemanticSearchServiceDep = Annotated[
    SemanticSearchService | None,
    Depends(get_semantic_search_service_dependency),
]
