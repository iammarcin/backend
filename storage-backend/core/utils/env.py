"""Common environment helpers used across the backend."""

from __future__ import annotations

import os

from core.exceptions import ConfigurationError

__all__ = ["get_env", "get_node_env", "is_local", "is_production"]


def get_env(key: str, default: str | None = None, *, required: bool = False) -> str | None:
    """Return an environment variable and optionally enforce its presence."""

    value = os.getenv(key, default)
    if required and value is None:
        raise ConfigurationError(f"Required environment variable {key} not set", key=key)
    return value


def get_node_env() -> str:
    """Return the current runtime environment label."""

    return (get_env("NODE_ENV", default="local") or "local").strip()


def is_production() -> bool:
    """True when running in production."""

    return get_node_env() == "production"


def is_local() -> bool:
    """True when running locally."""

    return get_node_env() == "local"

