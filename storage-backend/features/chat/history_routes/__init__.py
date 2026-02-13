"""Chat history API router composed of specialised endpoint modules."""

from __future__ import annotations

from .shared import history_router

# Import endpoint modules so they register handlers with ``history_router``.
from . import auth, maintenance, messages, prompts, session_name, sessions  # noqa: F401

__all__ = ["history_router"]

