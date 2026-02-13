"""Persistence helpers for Withings OAuth token handling.

The Withings client stores OAuth tokens on disk so that background jobs can
refresh credentials without re-authorising through the UI.  This module keeps
that behaviour isolated and well documented.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

logger = logging.getLogger(__name__)


def _ensure_parent(path: Path) -> None:
    """Create the directory that will hold the token store if missing."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to create Withings token directory", extra={"path": str(path)}, exc_info=exc)


@dataclass(slots=True)
class WithingsTokenStore:
    """Simple JSON-backed token persistence for the Withings API."""

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    def ensure_ready(self) -> None:
        """Prepare the token store for use by ensuring its directory exists."""

        _ensure_parent(self.path)

    def load(self) -> MutableMapping[str, Any]:
        """Load tokens from disk, returning an empty dict if none exist."""

        if not self.path.exists():
            return {}

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                if isinstance(data, MutableMapping):
                    return data
                if isinstance(data, dict):
                    return dict(data)
        except FileNotFoundError:  # pragma: no cover - raced deletion
            return {}
        except json.JSONDecodeError as exc:  # pragma: no cover - corrupted file
            logger.warning("Failed to parse Withings token store", extra={"path": str(self.path)}, exc_info=exc)
        return {}

    def save(self, tokens: Mapping[str, Any]) -> None:
        """Persist the provided tokens to disk."""

        _ensure_parent(self.path)
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump(tokens, handle, indent=2)
        except Exception as exc:  # pragma: no cover - disk errors
            logger.warning("Failed to persist Withings tokens", extra={"path": str(self.path)}, exc_info=exc)


__all__ = ["WithingsTokenStore"]
