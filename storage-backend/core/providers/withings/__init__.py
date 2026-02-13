"""Withings provider client utilities with lazy imports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - optimisation for static analysis
    from .client import WithingsClient as _WithingsClient

__all__ = ["WithingsClient"]


def __getattr__(name: str):  # pragma: no cover - simple delegation
    if name == "WithingsClient":
        from .client import WithingsClient as _WithingsClient

        return _WithingsClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
