"""Coordinate Withings OAuth tokens and measurement retrieval.

This module keeps the public client focused on orchestrating API calls while
delegating persistence and payload normalisation to dedicated helpers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping, MutableMapping

import httpx

from core.exceptions import ConfigurationError, ProviderError
from core.providers.withings.measurements import normalise_measure_group, to_timestamp_range
from core.providers.withings.token_store import WithingsTokenStore

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
_MEASURE_URL = "https://wbsapi.withings.net/measure"


@dataclass(slots=True)
class WithingsClient:
    """Thin wrapper around the Withings OAuth2 measurement API."""

    client_id: str
    client_secret: str
    redirect_uri: str
    token_store: WithingsTokenStore
    scope: str = "user.metrics"
    request_timeout: float = 30.0
    token_url: str = _TOKEN_URL
    measurement_url: str = _MEASURE_URL
    default_height_cm: float | None = None
    _tokens: MutableMapping[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.token_store.ensure_ready()
        self._tokens.update(self.token_store.load())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def metadata(self) -> Mapping[str, Any]:
        """Return metadata useful for diagnostics."""

        tokens = self._tokens or {}
        return {
            "token_path": str(self.token_store.path),
            "has_access_token": bool(tokens.get("access_token")),
            "has_refresh_token": bool(tokens.get("refresh_token")),
            "scope": self.scope,
        }

    def fetch_body_composition(
        self,
        *,
        start: date,
        end: date | None = None,
        height_cm: float | None = None,
    ) -> list[dict[str, Any]]:
        """Return normalised Withings body-composition measurements."""

        tokens = self._ensure_access_token()
        start_ts, end_ts = to_timestamp_range(start, end)

        payload = {
            "action": "getmeas",
            "category": 1,
            "access_token": tokens.get("access_token"),
            "startdate": start_ts,
            "enddate": end_ts,
        }

        try:
            response = httpx.post(self.measurement_url, data=payload, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.error("Withings request failed", exc_info=exc)
            raise ProviderError("Withings measurement request failed", provider="withings", original_error=exc) from exc

        status = data.get("status")
        if status not in (0, "0"):
            logger.error("Withings API returned an error", extra={"status": status})
            raise ProviderError(f"Withings API error (status {status})", provider="withings")

        body = data.get("body") or {}
        groups: Iterable[Mapping[str, Any]] = body.get("measuregrps") or []
        height = height_cm if height_cm is not None else self.default_height_cm

        records: list[dict[str, Any]] = []
        for group in groups:
            record = normalise_measure_group(group, height_cm=height)
            if record:
                records.append(record)
        return records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_access_token(self) -> MutableMapping[str, Any]:
        """Return valid tokens, refreshing them when necessary."""

        if not self._tokens:
            self._tokens.update(self.token_store.load())

        access_token = self._tokens.get("access_token")
        refresh_token = self._tokens.get("refresh_token")
        if not access_token and not refresh_token:
            raise ConfigurationError(
                "Withings tokens must be configured before fetching measurements",
                key="WITHINGS_TOKEN_PATH",
            )

        if self._is_expired(self._tokens):
            logger.info("Refreshing Withings access token")
            self._tokens = self._refresh_tokens(refresh_token)

        return self._tokens

    def _refresh_tokens(self, refresh_token: Any | None) -> MutableMapping[str, Any]:
        """Exchange the stored refresh token for a new access token."""

        if not refresh_token:
            raise ConfigurationError(
                "Withings refresh token missing; re-authorisation required",
                key="WITHINGS_REFRESH_TOKEN",
            )

        payload = {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }

        try:
            response = httpx.post(self.token_url, data=payload, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.error("Withings token refresh failed", exc_info=exc)
            raise ProviderError("Withings token refresh failed", provider="withings", original_error=exc) from exc

        status = data.get("status")
        if status not in (0, "0"):
            logger.error("Withings token refresh returned error", extra={"status": status})
            raise ProviderError(f"Withings token refresh failed (status {status})", provider="withings")

        body = data.get("body") or {}
        expires_in = body.get("expires_in")
        expires_at: float | None = None
        if expires_in is not None:
            try:
                expires_at = time.time() + float(expires_in)
            except (TypeError, ValueError):  # pragma: no cover - invalid payload
                expires_at = None

        tokens: MutableMapping[str, Any] = {
            "access_token": body.get("access_token"),
            "refresh_token": body.get("refresh_token", refresh_token),
            "userid": body.get("userid", self._tokens.get("userid")),
        }
        if expires_at is not None:
            tokens["expires_at"] = expires_at

        self._tokens.update(tokens)
        self.token_store.save(self._tokens)
        return self._tokens

    def _is_expired(self, tokens: Mapping[str, Any]) -> bool:
        """Return ``True`` when the access token is about to expire."""

        expires_at = tokens.get("expires_at")
        if not expires_at:
            return True  # Treat missing expiry as expired to force refresh
        try:
            return float(expires_at) <= time.time() + 60
        except (TypeError, ValueError):  # pragma: no cover - invalid payload
            return True


__all__ = ["WithingsClient", "WithingsTokenStore"]

