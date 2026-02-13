"""Garmin provider scaffolding and backward-compatible persistence exports."""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_PERSISTENCE_MODULE = "features.db.garmin"
_PERSISTENCE_EXPORTS = {
    "GarminPersistenceService",
    "GarminService",
    "GarminActivityRepository",
    "GarminSleepRepository",
    "GarminSummaryRepository",
    "GarminTrainingRepository",
    "build_repositories",
    "db_models",
}


def _load_persistence() -> Any:
    return importlib.import_module(_PERSISTENCE_MODULE)


def _load_service() -> Any:
    from . import service as service_module

    return service_module


def __getattr__(name: str) -> Any:
    if name == "GarminProviderService":
        module = _load_service()
        return module.GarminProviderService

    if name in _PERSISTENCE_EXPORTS:
        module = _load_persistence()
        if name == "GarminPersistenceService":
            return module.GarminService
        if name == "GarminService":
            return module.GarminService
        return getattr(module, name)

    if name == "logger":
        return logger

    raise AttributeError(f"module 'features.garmin' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted({*globals().keys(), *_PERSISTENCE_EXPORTS, "GarminProviderService", "logger"})


__all__ = ["GarminProviderService", "GarminPersistenceService", "GarminService", "GarminActivityRepository", "GarminSleepRepository", "GarminSummaryRepository", "GarminTrainingRepository", "build_repositories", "db_models", "logger"]
