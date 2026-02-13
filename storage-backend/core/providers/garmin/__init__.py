"""Garmin provider client utilities with lazy imports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import-time optimisation
    from .client import GarminConnectClient as _GarminConnectClient

__all__ = ["GarminConnectClient"]


def __getattr__(name: str):  # pragma: no cover - trivial delegation
    if name == "GarminConnectClient":
        from .client import GarminConnectClient as _GarminConnectClient

        return _GarminConnectClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

