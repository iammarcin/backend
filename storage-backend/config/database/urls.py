"""Database URL configuration.

Supports both MySQL (AWS/local) and PostgreSQL (Hetzner/Supabase) environments.

Environment Variables:
    - MAIN_DB_URL, GARMIN_DB_URL, etc.: Override entire URL (takes precedence)
    - DATABASE_USER: MySQL username (default: aitools)
    - AWS_DB_PASS: MySQL password
    - SUPABASE_DB_HOST: Supabase database host
    - SUPABASE_DB_PASS: Supabase database password
    - SUPABASE_DB_USER: Supabase username (default: postgres)
    - SUPABASE_DB_PORT: Supabase port (default: 5432)
"""

from __future__ import annotations

import os

from config.environment import ENVIRONMENT, IS_POSTGRESQL
from core.utils.config_helpers import build_mysql_url, build_postgresql_url

# MySQL credentials (AWS/local environments)
DATABASE_USER = os.getenv("DATABASE_USER", "aitools")
DATABASE_PASSWORD = os.getenv("AWS_DB_PASS", "") or ""

# Supabase/PostgreSQL credentials (Hetzner environments)
# Supports multiple naming conventions for flexibility
SUPABASE_DB_HOST = os.getenv("SUPABASE_HOST") or os.getenv("SUPABASE_DB_HOST", "")
SUPABASE_DB_PASS = os.getenv("SUPABASE_DB_PASSWORD") or os.getenv("SUPABASE_DB_PASS", "")
SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
SUPABASE_DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")

# MySQL environment configurations (host, database)
# NOTE: MySQL is deprecated - PostgreSQL is now the default
_MYSQL_DATABASES = {
    "production": {
        "main": {"host": "db.goodtogreat.life", "database": "aiapp"},
        "garmin": {"host": "db.goodtogreat.life", "database": "aiapp"},
        "blood": {"host": "db.goodtogreat.life", "database": "blood"},
        "ufc": {"host": "db.goodtogreat.life", "database": "ufc"},
    },
    "sherlock": {
        "main": {"host": "www.goodtogreat.life:8086", "database": "aiapp_nonprod"},
        "garmin": {"host": "www.goodtogreat.life:8086", "database": "aiapp_nonprod"},
        "blood": {"host": "www.goodtogreat.life:8086", "database": "blood"},
        "ufc": {"host": "www.goodtogreat.life:8086", "database": "ufc"},
    },
    "local": {
        "main": {"host": "docker-mysqlcg-1", "database": "aiapp"},
        "garmin": {"host": "docker-mysqlcg-1", "database": "aiapp"},
        "blood": {"host": "db.goodtogreat.life", "database": "blood"},
        "ufc": {"host": "db.ufcbot.com", "database": "ufc"},
    },
}

# PostgreSQL/Supabase environment configurations (schema names)
# Uses same host for all, different schemas
# Maps environment -> schema names
_POSTGRESQL_SCHEMAS = {
    # Production environments
    "production": {
        "main": "aiapp",
        "garmin": "aiapp",
        "blood": "blood",
        "ufc": "ufc",
        "cc4life": "cc4life",
    },
    "hetzner": {
        "main": "aiapp",
        "garmin": "aiapp",
        "blood": "blood",
        "ufc": "ufc",
        "cc4life": "cc4life",
    },
    # Non-production environments
    "sherlock": {
        "main": "aiapp_nonprod",
        "garmin": "aiapp_nonprod",
        "blood": "blood",
        "ufc": "ufc",
        "cc4life": "cc4life",
    },
    "hetzner_nonprod": {
        "main": "aiapp_nonprod",
        "garmin": "aiapp_nonprod",
        "blood": "blood",
        "ufc": "ufc",
        "cc4life": "cc4life",
    },
    "development": {
        "main": "aiapp",
        "garmin": "aiapp",
        "blood": "blood",
        "ufc": "ufc",
        "cc4life": "cc4life",
    },
    "local": {
        "main": "aiapp",
        "garmin": "aiapp",
        "blood": "blood",
        "ufc": "ufc",
        "cc4life": "cc4life",
    },
}


def _build_mysql_url(key: str) -> str:
    """Build MySQL URL for the given database key."""
    defaults = _MYSQL_DATABASES.get(ENVIRONMENT, _MYSQL_DATABASES["local"])
    db_config = defaults[key]
    return build_mysql_url(
        DATABASE_USER,
        DATABASE_PASSWORD or None,
        db_config["host"],
        db_config["database"],
    )


def _build_postgresql_url(key: str) -> str:
    """Build PostgreSQL URL for the given database key (Supabase)."""
    if not SUPABASE_DB_HOST or not SUPABASE_DB_PASS:
        # Return empty - will fail later with clear error
        return ""

    # Look up schema for current environment, fallback to production schemas
    schemas = _POSTGRESQL_SCHEMAS.get(ENVIRONMENT, _POSTGRESQL_SCHEMAS["production"])
    schema = os.getenv(f"{key.upper()}_DB_SCHEMA") or schemas.get(key, "public")

    return build_postgresql_url(
        SUPABASE_DB_USER,
        SUPABASE_DB_PASS,
        SUPABASE_DB_HOST,
        SUPABASE_DB_NAME,
        schema=schema,
        port=SUPABASE_DB_PORT,
    )


def _build_default_url(key: str) -> str:
    """Build database URL based on current environment."""
    if IS_POSTGRESQL:
        return _build_postgresql_url(key)
    return _build_mysql_url(key)


def _get_url(env_var: str, key: str) -> str:
    """Get database URL from environment or build default."""
    override = os.getenv(env_var)
    if override:
        return override
    return _build_default_url(key)


# Backward compatibility: DATABASE_DEFAULTS for MySQL environments
DATABASE_DEFAULTS = _MYSQL_DATABASES.get(ENVIRONMENT, _MYSQL_DATABASES["local"])

# Database URLs - environment variable takes precedence, then auto-build
MAIN_DB_URL = _get_url("MAIN_DB_URL", "main")
GARMIN_DB_URL = _get_url("GARMIN_DB_URL", "garmin")
BLOOD_DB_URL = _get_url("BLOOD_DB_URL", "blood")
UFC_DB_URL = _get_url("UFC_DB_URL", "ufc")
CC4LIFE_DB_URL = _get_url("CC4LIFE_DB_URL", "cc4life")

__all__ = [
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_DEFAULTS",
    "SUPABASE_DB_HOST",
    "SUPABASE_DB_PASS",
    "SUPABASE_DB_USER",
    "SUPABASE_DB_PORT",
    "MAIN_DB_URL",
    "GARMIN_DB_URL",
    "BLOOD_DB_URL",
    "UFC_DB_URL",
    "CC4LIFE_DB_URL",
]
