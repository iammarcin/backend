"""Dependency wiring for Garmin FastAPI endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import ConfigurationError
from core.providers.garmin import GarminConnectClient
from core.providers.withings import WithingsClient
from core.providers.withings.client import WithingsTokenStore
from infrastructure.db.mysql import (
    AsyncSessionFactory,
    SessionDependency,
    get_session_dependency,
    require_garmin_session_factory,
)
from features.db.garmin.repositories import build_repositories
from features.db.garmin.service import GarminService

from .service import GarminProviderService
from .settings import get_garmin_provider_settings, get_withings_provider_settings

logger = logging.getLogger(__name__)

_ServiceFactory = Callable[[], GarminService]

_session_dependency: SessionDependency | None = None
_service_instance: GarminService | None = None
_provider_service: GarminProviderService | None = None
_withings_client: WithingsClient | None = None


def _resolve_session_dependency() -> SessionDependency:
    """Return the cached FastAPI session dependency, initialising it on demand."""

    global _session_dependency

    if _session_dependency is None:
        try:
            factory: AsyncSessionFactory = require_garmin_session_factory()
        except ConfigurationError as exc:
            logger.error("GARMIN_DB_URL is missing; cannot create Garmin session dependency")
            raise ConfigurationError(
                "GARMIN_DB_URL must be configured before accessing Garmin endpoints",
                key="GARMIN_DB_URL",
            ) from exc

        logger.debug("Initialising Garmin session dependency")
        _session_dependency = get_session_dependency(factory)

    return _session_dependency


async def get_garmin_session() -> AsyncIterator[AsyncSession | None]:
    """Yield an :class:`AsyncSession` for Garmin operations.

    Returns:
        Async iterator yielding database sessions when Garmin is enabled,
        otherwise ``None`` exactly once when the feature toggle is disabled.

    Raises:
        ConfigurationError: If Garmin is enabled but ``GARMIN_DB_URL`` is not
        configured or the dependency factory cannot be constructed.
    """

    if not settings.garmin_enabled:
        logger.debug("Garmin features disabled in settings; yielding empty session")
        yield None
        return

    try:
        dependency = _resolve_session_dependency()
    except ConfigurationError:
        logger.error("Garmin enabled but GARMIN_DB_URL is not configured; failing fast")
        raise

    async for session in dependency():
        yield session


def _build_service() -> GarminService:
    repositories = build_repositories()
    return GarminService(
        sleep_repo=repositories["sleep"],
        summary_repo=repositories["summary"],
        training_repo=repositories["training"],
        activity_repo=repositories["activity"],
    )


def get_garmin_service() -> GarminService:
    """Return a singleton Garmin service for request handling.

    The service composes ingestion/retrieval repositories and is shared across
    requests so that higher-level dependencies only need to manage database
    sessions.
    """

    global _service_instance

    if _service_instance is None:
        logger.debug("Creating GarminService singleton for dependency injection")
        _service_instance = _build_service()

    return _service_instance


def get_garmin_provider_service() -> GarminProviderService:
    """Return the singleton Garmin provider service.

    Raises:
        ConfigurationError: If the Garmin client cannot be initialised because
        authentication settings are missing or invalid.
    """

    global _provider_service

    if _provider_service is None:
        logger.debug("Creating GarminProviderService singleton for dependency injection")
        settings = get_garmin_provider_settings()
        client = GarminConnectClient(
            session_path=Path(settings.session_path),
            username=settings.username,
            password=settings.password,
            request_timeout=settings.request_timeout,
            backoff_factor=settings.backoff_factor,
            max_retry_attempts=settings.max_retry_attempts,
        )
        withings_client = _get_withings_client()
        garmin_service = get_garmin_service()
        _provider_service = GarminProviderService(
            client=client,
            garmin_service=garmin_service,
            save_to_db_default=settings.save_to_db_default,
            withings_client=withings_client,
        )

    return _provider_service


def _get_withings_client() -> WithingsClient | None:
    """Return a Withings client when credentials are configured.

    The Withings integration is optional. When no credentials are found (either
    via environment variables or the legacy file-based config), the provider
    service runs without Withings enrichment and logs an informational message.
    """
    global _withings_client

    if _withings_client is not None:
        return _withings_client

    settings = get_withings_provider_settings()

    # Try environment variables first
    client_id = settings.client_id
    client_secret = settings.client_secret

    # Fall back to file-based config (withings_app.json) if env vars not set
    if not client_id or not client_secret:
        logger.debug("Withings credentials not found in environment; attempting file-based config")
        client_id, client_secret = _load_withings_file_config()

    if not client_id or not client_secret:
        logger.info(
            "Withings credentials not found; Withings integration disabled. "
            "Set WITHINGS_CLIENT_ID and WITHINGS_CLIENT_SECRET to enable."
        )
        return None

    # Token path defaults to ~/.withings_user.json if not overridden
    token_path = Path(settings.token_path)

    logger.debug("Initialising Withings provider client", extra={"token_path": str(token_path)})
    token_store = WithingsTokenStore(token_path)
    _withings_client = WithingsClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=settings.redirect_uri or "",
        token_store=token_store,
        scope=settings.scope,
        request_timeout=settings.request_timeout,
        default_height_cm=settings.default_height_cm,
    )
    return _withings_client


def _load_withings_file_config() -> tuple[str | None, str | None]:
    """Load Withings app config from withings_app.json (file-based auth).

    This supports the legacy file-based authentication approach where:
    - ~/withings_app.json contains client_id and consumer_secret (OAuth app credentials)
    - ~/.withings_user.json contains access_token, refresh_token (user authorization)
    """
    import json

    try:
        # Try the mounted home directory first, but keep legacy /app path for compatibility
        app_config_paths = [
            Path.home() / "withings_app.json",
        ]

        for app_config_path in app_config_paths:
            if not app_config_path.exists():
                continue

            try:
                with app_config_path.open("r", encoding="utf-8") as f:
                    config = json.load(f)
                    client_id = config.get("client_id")
                    # Legacy code uses "consumer_secret", new code uses "client_secret"
                    client_secret = config.get("consumer_secret") or config.get("client_secret")

                    if client_id and client_secret:
                        logger.info(
                            "Loaded Withings credentials from file-based config",
                            extra={"path": str(app_config_path)}
                        )
                        return client_id, client_secret
                    else:
                        logger.warning(
                            "withings_app.json missing required fields",
                            extra={"path": str(app_config_path), "has_client_id": bool(client_id)}
                        )
            except json.JSONDecodeError as exc:
                logger.warning("Failed to parse withings_app.json", exc_info=exc)
                continue

        logger.debug("withings_app.json not found in standard locations")
        return None, None

    except Exception as exc:
        logger.warning("Error loading withings file-based config", exc_info=exc)
        return None, None


__all__ = ["get_garmin_service", "get_garmin_session", "get_garmin_provider_service"]
