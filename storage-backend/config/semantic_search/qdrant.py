"""Qdrant vector database configuration."""

from __future__ import annotations

import os

from config.environment import ENVIRONMENT

URL = os.getenv("QDRANT_URL", "")
API_KEY = os.getenv("QDRANT_API_KEY", "")

_DEFAULT_COLLECTIONS = {
    "production": {
        "semantic": "chat_messages_prod",
        "hybrid": "chat_messages_prod_hybrid",
        "sessions": "chat_sessions_summary_prod"
    },
    "sherlock": {
        "semantic": "chat_messages",
        "hybrid": "chat_messages_hybrid",
        "sessions": "chat_sessions_summary"
    },
    "local": {
        "semantic": "chat_messages",
        "hybrid": "chat_messages_hybrid",
        "sessions": "chat_sessions_summary"
    },
}
_collection_defaults = _DEFAULT_COLLECTIONS.get(ENVIRONMENT, _DEFAULT_COLLECTIONS["local"])

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", _collection_defaults["hybrid"])
COLLECTION_SEMANTIC = os.getenv("QDRANT_COLLECTION_SEMANTIC", _collection_defaults["semantic"])
COLLECTION_HYBRID = os.getenv("QDRANT_COLLECTION_HYBRID", COLLECTION_NAME or _collection_defaults["hybrid"])
QDRANT_COLLECTION_NAME_SESSIONS = os.getenv("QDRANT_COLLECTION_NAME_SESSIONS", _collection_defaults["sessions"])

CONNECTION_TIMEOUT = 10  # seconds
REQUEST_TIMEOUT = 30  # seconds

__all__ = [
    "URL",
    "API_KEY",
    "COLLECTION_NAME",
    "COLLECTION_SEMANTIC",
    "COLLECTION_HYBRID",
    "QDRANT_COLLECTION_NAME_SESSIONS",
    "CONNECTION_TIMEOUT",
    "REQUEST_TIMEOUT",
]
