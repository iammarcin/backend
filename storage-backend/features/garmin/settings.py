"""Configuration objects for Garmin and Withings providers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from core.exceptions import ConfigurationError


@dataclass(frozen=True)
class GarminProviderSettings:
    """Configuration required by the Garmin provider service."""

    session_path: str
    base_url: str
    username: str | None
    password: str | None
    save_to_db_default: bool
    request_timeout: float
    backoff_factor: float
    max_retry_attempts: int


def get_garmin_provider_settings() -> GarminProviderSettings:
    """Return environment configuration for the Garmin provider."""

    session_path = os.getenv(
        "GARMIN_SESSION_PATH", str(Path.home() / ".garmin_session")
    )
    base_url = os.getenv("GARMIN_BASE_URL", "https://connect.garmin.com")
    username = os.getenv("GARMIN_USERNAME")
    password = os.getenv("GARMIN_PASSWORD")
    save_to_db = _bool_env("GARMIN_SAVE_TO_DB", default=True)
    timeout = _float_env("GARMIN_REQUEST_TIMEOUT", default=30.0)
    backoff = _float_env("GARMIN_BACKOFF_FACTOR", default=0.5)
    retries = _int_env("GARMIN_MAX_RETRY_ATTEMPTS", default=3)

    return GarminProviderSettings(
        session_path=session_path,
        base_url=base_url,
        username=username,
        password=password,
        save_to_db_default=save_to_db,
        request_timeout=timeout,
        backoff_factor=backoff,
        max_retry_attempts=retries,
    )


@dataclass(frozen=True)
class WithingsProviderSettings:
    """Configuration for the Withings provider client."""

    token_path: str
    client_id: str | None
    client_secret: str | None
    redirect_uri: str | None
    scope: str
    default_height_cm: float | None
    request_timeout: float

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.token_path)


def get_withings_provider_settings() -> WithingsProviderSettings:
    """Return environment configuration for the Withings provider.

    Supports both approaches:
    1. Environment variables: WITHINGS_CLIENT_ID, WITHINGS_CLIENT_SECRET
    2. File-based config: ~/withings_app.json (app credentials), ~/.withings_user.json (tokens)

    The file-based approach mirrors the legacy authentication method.
    """

    # Default token path is ~/.withings_user.json (mounted from home dir in docker-compose)
    token_path = os.getenv(
        "WITHINGS_TOKEN_PATH", str(Path.home() / ".withings_user.json")
    )
    client_id = os.getenv("WITHINGS_CLIENT_ID")
    client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
    redirect_uri = os.getenv("WITHINGS_REDIRECT_URI")
    scope = os.getenv("WITHINGS_SCOPE", "user.metrics") or "user.metrics"
    default_height_cm = _optional_float_env("WITHINGS_DEFAULT_HEIGHT_CM")
    request_timeout = _float_env("WITHINGS_REQUEST_TIMEOUT", default=30.0)

    return WithingsProviderSettings(
        token_path=token_path,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        default_height_cm=default_height_cm,
        request_timeout=request_timeout,
    )


__all__ = [
    "GarminProviderSettings",
    "WithingsProviderSettings",
    "get_garmin_provider_settings",
    "get_withings_provider_settings",
]


def _bool_env(key: str, *, default: bool) -> bool:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(key: str, *, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - configuration misfire
        raise ConfigurationError(f"{key} must be an integer", key=key) from exc


def _float_env(key: str, *, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - configuration misfire
        raise ConfigurationError(f"{key} must be a floating point value", key=key) from exc


def _optional_float_env(key: str) -> float | None:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - configuration misfire
        raise ConfigurationError(f"{key} must be a floating point value", key=key) from exc
