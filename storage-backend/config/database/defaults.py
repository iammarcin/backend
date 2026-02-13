"""Database connection pool configuration."""

from __future__ import annotations

import os

POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "900"))
CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

__all__ = [
    "POOL_SIZE",
    "MAX_OVERFLOW",
    "POOL_RECYCLE",
    "CONNECT_TIMEOUT",
    "POOL_TIMEOUT",
    "ECHO",
]
