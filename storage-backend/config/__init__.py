"""Configuration package - lazy-loading entry point for all settings."""

from __future__ import annotations

import importlib
from typing import Any

_EXPORTS = {
    "aws",
    "api_keys",
    "audio",
    "batch",
    "database",
    "environment",
    "image",
    "realtime",
    "semantic_search",
    "text",
    "tts",
    "video",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Lazily import configuration submodules on demand."""

    if name not in _EXPORTS:
        raise AttributeError(f"module 'config' has no attribute '{name}'")

    module = importlib.import_module(f".{name}", __name__)
    globals()[name] = module
    return module
