"""Minimal environment variable loading and settings dataclass.

All domain-specific configuration has been moved to config/ subdirectories.

This module only handles:
1. Environment detection (delegates to config.environment)
2. API key loading (delegates to config.api_keys)
3. Feature toggles (minimal set)
4. Settings dataclass for dependency injection

For domain-specific config, import from config/ subdirectories:
- Audio/STT: config.audio
- TTS: config.tts
- Realtime: config.realtime
- Image: config.image
- Video: config.video
- Semantic search: config.semantic_search
- Database: config.database
- Text providers: config.text
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# Import all config modules to make them available
from config import (
    environment,
    api_keys,
    audio,
    tts,
    video,
    realtime,
    image,
    semantic_search,
    database,
    text,
)

# Re-export environment helpers
from config.environment import (
    get_node_env,
    ENVIRONMENT,
    IS_DEVELOPMENT,
    IS_PRODUCTION,
    IS_TEST,
    IS_SHERLOCK,
)

# Re-export API keys
from config.api_keys import API_KEYS

# Re-export semantic search utilities
from config.semantic_search import defaults as semantic_defaults
from config.semantic_search import qdrant as qdrant_config
from config.semantic_search.utils.collection_resolver import get_collection_for_mode, SEMANTIC_COLLECTION_MAPPING

# Feature toggles (minimal set - most moved to respective config modules)
# garmin enabled by default in PROD
GARMIN_ENABLED = os.getenv("GARMIN_ENABLED", "true" if IS_PRODUCTION else "false").lower() == "true"
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
SEMANTIC_SEARCH_ENABLED = os.getenv("SEMANTIC_SEARCH_ENABLED", "true").lower() == "true"

@dataclass(frozen=True)
class Settings:
    """Dependency injection wrapper for feature settings.

    Most domain-specific settings have been moved to config/ modules.
    This dataclass only contains truly cross-cutting settings.
    """
    environment: str = ENVIRONMENT
    debug_mode: bool = DEBUG_MODE
    garmin_enabled: bool = GARMIN_ENABLED
    semantic_search_enabled: bool = SEMANTIC_SEARCH_ENABLED
    semantic_search_indexing_enabled: bool = semantic_defaults.INDEXING_ENABLED
    semantic_embedding_model: str = "text-embedding-3-small"
    qdrant_url: str = qdrant_config.URL
    qdrant_api_key: str = qdrant_config.API_KEY
    semantic_search_timeout: float = 10.0

settings = Settings()

__all__ = [
    # Environment
    "get_node_env",
    "ENVIRONMENT",
    "IS_DEVELOPMENT",
    "IS_PRODUCTION",
    "IS_TEST",
    "IS_SHERLOCK",
    # API Keys
    "API_KEYS",
    # Feature toggles
    "GARMIN_ENABLED",
    "DEBUG_MODE",
    "SEMANTIC_SEARCH_ENABLED",
    # Settings
    "Settings",
    "settings",
    # Semantic search utilities
    "get_collection_for_mode",
    "SEMANTIC_COLLECTION_MAPPING",
]
