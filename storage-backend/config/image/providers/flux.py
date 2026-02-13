"""Flux (Black Forest Labs) image configuration."""

from __future__ import annotations

DEFAULT_MODEL = "flux-2-pro"
SUPPORTED_MODELS = [
    # FLUX.2 Series (November 2025)
    "flux-2-max",
    "flux-2-pro",
    "flux-2-flex",
    # FLUX.1 Series (legacy)
    "flux-dev",
    "flux-pro-1.1",
    "flux-pro-1.1-ultra",
    "flux-kontext-pro",
]

DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024
MAX_DIMENSION = 2048

POLL_INTERVAL_SECONDS = 1
MAX_POLL_ATTEMPTS = 60

__all__ = [
    "DEFAULT_MODEL",
    "SUPPORTED_MODELS",
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "MAX_DIMENSION",
    "POLL_INTERVAL_SECONDS",
    "MAX_POLL_ATTEMPTS",
]
