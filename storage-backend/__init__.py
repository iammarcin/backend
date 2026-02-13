"""Package initialisation for storage-backend-ng."""

from __future__ import annotations

import importlib

if __package__:
    features = importlib.import_module(".features", __package__)
else:  # pragma: no cover - fallback for direct execution
    features = importlib.import_module("features")

__all__ = ["features"]
