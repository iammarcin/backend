"""Database infrastructure helpers."""

from __future__ import annotations

from .base import Base, metadata, prepare_database
from .mysql import (
    AsyncSessionFactory,
    SessionDependency,
    blood_engine,
    blood_session_factory,
    create_mysql_engine,
    garmin_engine,
    garmin_session_factory,
    get_session_dependency,
    get_session_factory,
    main_engine,
    main_session_factory,
    require_main_session_factory,
    require_garmin_session_factory,
    require_blood_session_factory,
    require_ufc_session_factory,
    session_scope,
    ufc_engine,
    ufc_session_factory,
)

__all__ = [
    "Base",
    "metadata",
    "prepare_database",
    "AsyncSessionFactory",
    "SessionDependency",
    "create_mysql_engine",
    "get_session_factory",
    "session_scope",
    "get_session_dependency",
    "require_main_session_factory",
    "require_garmin_session_factory",
    "require_blood_session_factory",
    "require_ufc_session_factory",
    "main_engine",
    "main_session_factory",
    "garmin_engine",
    "garmin_session_factory",
    "blood_engine",
    "blood_session_factory",
    "ufc_engine",
    "ufc_session_factory",
]
