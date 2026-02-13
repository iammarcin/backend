"""Environment detection and helpers."""

from __future__ import annotations

import os
from typing import Literal

Environment = Literal["development", "production", "test", "sherlock", "hetzner", "hetzner_nonprod"]
DatabaseType = Literal["mysql", "postgresql"]


def get_node_env() -> Environment:
    """Return the current runtime environment label."""

    raw = os.getenv("NODE_ENV", "development").lower()
    if raw in ("development", "production", "test", "sherlock", "hetzner", "hetzner_nonprod"):
        return raw  # type: ignore[return-value]
    return "development"


def get_database_type() -> DatabaseType:
    """Return the database type to use.

    Explicitly set via DB_TYPE environment variable.

    DB_TYPE values: "postgresql", "postgres", "pg" -> postgresql
                    "mysql", "mariadb" -> mysql

    If DB_TYPE not set, defaults to postgresql.
    """
    db_type = os.getenv("DB_TYPE", "").lower()

    if db_type in ("postgresql", "postgres", "pg"):
        return "postgresql"
    if db_type in ("mysql", "mariadb"):
        return "mysql"

    # Default to PostgreSQL
    return "postgresql"


ENVIRONMENT: Environment = get_node_env()
IS_DEVELOPMENT = ENVIRONMENT == "development"
IS_PRODUCTION = ENVIRONMENT == "production"
IS_TEST = ENVIRONMENT == "test"
IS_SHERLOCK = ENVIRONMENT == "sherlock"
IS_HETZNER = ENVIRONMENT == "hetzner"
IS_HETZNER_NONPROD = ENVIRONMENT == "hetzner_nonprod"

# Database type detection - can be overridden via DB_TYPE env var
DATABASE_TYPE: DatabaseType = get_database_type()
IS_POSTGRESQL = DATABASE_TYPE == "postgresql"
IS_MYSQL = DATABASE_TYPE == "mysql"

__all__ = [
    "Environment",
    "DatabaseType",
    "ENVIRONMENT",
    "DATABASE_TYPE",
    "IS_DEVELOPMENT",
    "IS_PRODUCTION",
    "IS_TEST",
    "IS_SHERLOCK",
    "IS_HETZNER",
    "IS_HETZNER_NONPROD",
    "IS_POSTGRESQL",
    "IS_MYSQL",
    "get_node_env",
    "get_database_type",
]
