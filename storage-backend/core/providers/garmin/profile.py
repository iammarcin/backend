"""Profile helpers for the Garmin Connect client.

The mixin encapsulates profile lookups and cached metadata handling so the main
client can delegate those responsibilities without becoming unwieldy.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from core.exceptions import ProviderError


class GarminProfileMixin:
    """Expose profile and metadata helpers shared across the provider."""

    _profile_cache: MutableMapping[str, Any]

    @property
    def display_name(self) -> str:
        self.authenticate()
        profile = self._profile()
        display_name = profile.get("displayName")
        if not display_name:
            raise ProviderError("Garmin profile does not expose a display name", provider="garmin")
        return display_name

    def metadata(self) -> Mapping[str, Any]:
        """Return cached profile metadata useful for status endpoints."""

        profile = self._profile()
        settings = self._fetch_user_settings()
        return {
            "display_name": profile.get("displayName"),
            "full_name": profile.get("fullName"),
            "unit_system": settings.get("userData", {}).get("measurementSystem"),
            "session_path": str(self.session_path),
            "domain": self.base_domain,
        }

    def _profile(self) -> Mapping[str, Any]:
        if self._profile_cache:
            return self._profile_cache
        try:
            profile = self._client.profile or {}
        except Exception:  # pragma: no cover - defensive guard
            profile = {}
        if not profile:
            profile = self._fetch_user_profile()
        self._profile_cache.update(profile or {})
        return self._profile_cache

    def _fetch_user_profile(self) -> Mapping[str, Any]:
        payload = self._request("/userprofile-service/userprofile")
        if isinstance(payload, Mapping):
            return payload
        return {}

    def _fetch_user_settings(self) -> Mapping[str, Any]:
        payload = self._request("/userprofile-service/userprofile/user-settings")
        if isinstance(payload, Mapping):
            return payload
        return {}


__all__ = ["GarminProfileMixin"]
