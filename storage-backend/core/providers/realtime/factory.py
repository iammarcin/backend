"""Registry helpers for realtime provider implementations."""

from __future__ import annotations

import logging
from typing import Dict, Type

from core.exceptions import ConfigurationError

from .base import BaseRealtimeProvider
from .utils import NullRealtimeProvider

logger = logging.getLogger(__name__)

_DEFAULT_PROVIDER_KEY = "null"

# Registry is pre-populated with the null provider so callers always receive a
# concrete provider instance even when resolution fails.
_REALTIME_PROVIDERS: Dict[str, Type[BaseRealtimeProvider]] = {
    _DEFAULT_PROVIDER_KEY: NullRealtimeProvider
}

_MODEL_PROVIDER_OVERRIDES: Dict[str, str] = {
    "gpt-realtime": "openai",
    "gpt-realtime-mini": "openai",
    "gpt-realtime-preview": "openai",
    "openai-realtime": "openai",
    "realtime": "openai",
    "realtime-mini": "openai",
    "gpt-4o-realtime": "openai",
    "gpt-4o-realtime-preview": "openai",
    "gpt-4o-mini-realtime": "openai",
    "gpt-4o-mini-realtime-preview": "openai",
    "gemini-live": "google",
    "gemini-realtime": "google",
    "gemini-pro-realtime": "google",
}


def register_realtime_provider(
    key: str,
    provider_class: Type[BaseRealtimeProvider],
) -> None:
    """Register a realtime provider implementation under ``key``."""

    if not key or not key.strip():
        raise ConfigurationError("Realtime provider key cannot be empty", key="realtime.providers")

    normalised = key.strip().lower()
    _REALTIME_PROVIDERS[normalised] = provider_class
    logger.debug(
        "Registered realtime provider",
        extra={"key": normalised, "class": provider_class.__name__},
    )


def list_realtime_providers(*, include_internal: bool = False) -> list[str]:
    """Return the currently registered realtime provider keys."""

    providers = _REALTIME_PROVIDERS.keys()
    if not include_internal:
        providers = (key for key in providers if key != _DEFAULT_PROVIDER_KEY)
    return sorted(providers)


def get_realtime_provider(
    model: str,
    customer_id: int | None = None,
    **kwargs,
) -> BaseRealtimeProvider:
    """Return a realtime provider instance matching ``model``."""

    if not _REALTIME_PROVIDERS:
        raise ConfigurationError("No realtime providers have been registered", key="realtime.providers")

    logger.info("Resolving realtime provider for model: %s", model)

    provider_name = _resolve_provider_name(model)
    logger.info("Resolved provider name: %s", provider_name)

    provider_class = _REALTIME_PROVIDERS.get(provider_name)
    if provider_class is None:
        available = list(_REALTIME_PROVIDERS.keys())
        logger.warning(
            "No provider found for '%s' (model=%s). Available providers: %s. Returning NullRealtimeProvider.",
            provider_name,
            model,
            available,
        )
        fallback_class = _REALTIME_PROVIDERS.get(_DEFAULT_PROVIDER_KEY, NullRealtimeProvider)
        return fallback_class()

    logger.info(
        "Instantiating provider: %s",
        provider_class.__name__,
        extra={"model": model, "provider": provider_name, "customer_id": customer_id},
    )

    provider_kwargs = dict(kwargs)
    return provider_class(**provider_kwargs)


def _resolve_provider_name(model: str | None) -> str:
    """Map an incoming model identifier to a registered provider key."""

    if not model:
        return _DEFAULT_PROVIDER_KEY

    cleaned = model.strip().lower()
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[0]

    override = _MODEL_PROVIDER_OVERRIDES.get(cleaned)
    if override:
        return override

    if cleaned.startswith(("gpt-", "openai", "o1-")):
        return "openai"
    if cleaned.startswith(("gemini", "google", "models/gemini")):
        return "google"

    return _DEFAULT_PROVIDER_KEY


def clear_registry() -> None:
    """Utility used by tests to reset the provider registry."""

    _REALTIME_PROVIDERS.clear()
    _REALTIME_PROVIDERS[_DEFAULT_PROVIDER_KEY] = NullRealtimeProvider


__all__ = [
    "clear_registry",
    "get_realtime_provider",
    "list_realtime_providers",
    "register_realtime_provider",
]
