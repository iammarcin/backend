"""Utility helpers shared across core packages.

The previous implementation re-exported Garmin database helpers which live in
``features.db.garmin``.  Importing them here pulled in feature modules during
app start-up which in turn import :mod:`core.config`.  Because
``core.config`` needs ``core.utils`` to resolve environment helpers, this
created a circular import chain during pytest collection.  Keeping
``core.utils`` limited to environment helpers avoids the cycle while callers
can still import Garmin utilities directly from
``features.db.garmin.utils``.
"""

from .env import get_env, get_node_env, is_local, is_production

__all__ = [
    "get_env",
    "get_node_env",
    "is_local",
    "is_production",
]
