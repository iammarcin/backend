"""Garmin Connect HTTP client wrapper.

The legacy backend relied on :mod:`garth` directly.  This wrapper centralises
session persistence, authentication retries, and dataset-specific helpers so the
feature layer can focus on orchestration rather than HTTP minutiae.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping

from garth.exc import GarthHTTPError
from garth.http import Client as GarthHttpClient

from core.exceptions import AuthenticationError, ConfigurationError, ProviderError

from .datasets import GarminDatasetMixin
from .profile import GarminProfileMixin
from .utils import ensure_parent

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GarminConnectClient(GarminDatasetMixin, GarminProfileMixin):
    """Thin wrapper around :class:`garth.Client` with retry helpers."""

    session_path: Path
    base_domain: str = "connect.garmin.com"
    username: str | None = None
    password: str | None = None
    request_timeout: float = 30.0
    backoff_factor: float = 0.5
    max_retry_attempts: int = 3
    prompt_mfa: Callable[[], str] | None = None
    _client: GarthHttpClient = field(init=False, repr=False)
    _authenticated: bool = field(default=False, init=False, repr=False)
    _profile_cache: MutableMapping[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.session_path = Path(self.session_path)
        ensure_parent(self.session_path)

        status_forcelist = (401, 429, 500, 502, 503, 504)
        # ``garth`` configures default retry behaviour inside ``Client.__init__``
        # and forwards keyword arguments directly to ``Client.configure``.  The
        # upstream implementation passes its own ``backoff_factor`` value which
        # collides when we provide one during initialisation, resulting in the
        # ``TypeError`` observed when the dependency is first resolved.  To avoid
        # double passing values we initialise the client with defaults and then
        # apply our configuration explicitly.
        self._client = GarthHttpClient()
        self._client.configure(
            backoff_factor=self.backoff_factor,
            status_forcelist=status_forcelist,
            retries=self.max_retry_attempts,
            timeout=self.request_timeout,
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def authenticate(self, *, force: bool = False) -> None:
        """Ensure a valid Garmin session is loaded."""

        if self._authenticated and not force:
            return

        if not force and self._load_session():
            self._authenticated = True
            logger.debug("Loaded cached Garmin session", extra={"session_path": str(self.session_path)})
            return

        logger.debug(
            "Cached Garmin session unavailable; falling back to credential-based authentication",
            extra={
                "session_path": str(self.session_path),
                "force": force,
            },
        )

        self._login()
        self._authenticated = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        self.authenticate()
        # Log the Garmin API path being called
        logger.info(
            f"Calling Garmin API: {path}",
            extra={
                "path": path,
                "params": dict(params) if params else None,
            },
        )
        try:
            return self._client.connectapi(path, params=params)
        except GarthHTTPError as exc:
            # GarthHTTPError doesn't expose response.status_code directly
            # Check error string for 401 auth errors
            error_str = str(exc)

            if "401" in error_str:
                logger.info("Garmin session expired; re-authenticating")
                self.authenticate(force=True)
                return self._client.connectapi(path, params=params)

            logger.warning(
                f"Garmin API error: {path}",
                extra={
                    "error": error_str,
                    "path": path,
                    "params": dict(params) if params else None,
                },
            )
            raise ProviderError(
                f"Garmin Connect request failed: {error_str}",
                provider="garmin",
                original_error=exc,
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception(
                "Unhandled error during Garmin Connect request",
                extra={
                    "path": path,
                    "params": dict(params) if params else None,
                },
            )
            raise ProviderError("Garmin Connect request failed", provider="garmin", original_error=exc) from exc

    def _login(self) -> None:
        username = self.username
        password = self.password
        if not username or not password:
            raise ConfigurationError(
                "Garmin credentials must be configured for first-time authentication "
                "(no cached session found). Set GARMIN_USERNAME and GARMIN_PASSWORD environment variables.",
                key="GARMIN_USERNAME",
            )

        logger.info("Authenticating with Garmin Connect", extra={"username": username})
        try:
            self._client.login(username, password, prompt_mfa=self.prompt_mfa)
        except Exception as exc:  # pragma: no cover - login errors are environment specific
            logger.error("Garmin authentication failed", extra={"username": username})
            raise AuthenticationError("Garmin authentication failed") from exc

        self._save_session()
        self._profile_cache.clear()

    def _save_session(self) -> None:
        try:
            self._client.save(str(self.session_path))
        except Exception as exc:  # pragma: no cover - disk IO failure
            logger.warning("Unable to persist Garmin session", extra={"path": str(self.session_path)}, exc_info=exc)

    def _load_session(self) -> bool:
        if not self.session_path.exists():
            return False
        try:
            self._client.load(str(self.session_path))
            self._profile_cache.clear()
            return True
        except (json.JSONDecodeError, FileNotFoundError):
            return False
        except Exception as exc:  # pragma: no cover - corrupted session
            logger.warning("Failed to load Garmin session", extra={"path": str(self.session_path)}, exc_info=exc)
            return False


__all__ = ["GarminConnectClient"]
