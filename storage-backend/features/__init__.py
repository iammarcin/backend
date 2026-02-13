"""Lazy feature module loader used across the backend."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Final

_MODULE_MAP: Final = {
    "chat": "features.chat",
    "db": "features.db",
    "blood": "features.db.blood",
    "ufc": "features.db.ufc",
    "garmin": "features.garmin",
    "tts": "features.tts",
    "realtime": "features.realtime",
    "admin": "features.admin",
}


def __getattr__(name: str) -> ModuleType:
    if name not in _MODULE_MAP:
        raise AttributeError(f"module 'features' has no attribute '{name}'")

    module = importlib.import_module(_MODULE_MAP[name])
    globals()[name] = module
    return module


__all__ = list(_MODULE_MAP)
