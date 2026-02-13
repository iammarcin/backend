"""MySQL session management utilities."""

from __future__ import annotations
import os

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config.database.urls import (
    BLOOD_DB_URL as CONFIG_BLOOD_DB_URL,
    CC4LIFE_DB_URL as CONFIG_CC4LIFE_DB_URL,
    GARMIN_DB_URL as CONFIG_GARMIN_DB_URL,
    MAIN_DB_URL as CONFIG_MAIN_DB_URL,
    UFC_DB_URL as CONFIG_UFC_DB_URL,
)
from core.exceptions import ConfigurationError, DatabaseError
from infrastructure.db.mysql_engines import create_mysql_engine, get_session_factory

logger = logging.getLogger(__name__)


# Database URLs from environment
blood_db_url = os.getenv("BLOOD_DB_URL")
cc4life_db_url = os.getenv("CC4LIFE_DB_URL")
garmin_db_url = os.getenv("GARMIN_DB_URL")
main_db_url = os.getenv("MAIN_DB_URL")
ufc_db_url = os.getenv("UFC_DB_URL")

# Lazy-loaded session factories - initialized to None
main_session_factory: Optional[async_sessionmaker] = None
garmin_session_factory: Optional[async_sessionmaker] = None
blood_session_factory: Optional[async_sessionmaker] = None
ufc_session_factory: Optional[async_sessionmaker] = None
cc4life_session_factory: Optional[async_sessionmaker] = None


@asynccontextmanager
async def session_scope(factory: async_sessionmaker) -> AsyncIterator[AsyncSession]:
    """Provide a transactional scope around a series of operations."""

    session = factory()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as exc:  # pragma: no cover - passthrough guard
        await session.rollback()
        raise DatabaseError("Database operation failed", operation="transaction") from exc
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def get_session_dependency(factory: async_sessionmaker) -> Callable[[], AsyncIterator[AsyncSession]]:
    """Return a FastAPI dependency that yields a database session per request."""

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_scope(factory) as session:
            yield session

    return _get_session


def require_main_session_factory() -> async_sessionmaker:
    """Return the main chat session factory or raise a configuration error."""
    global main_session_factory

    if main_session_factory is None:
        url = main_db_url if main_db_url is not None else CONFIG_MAIN_DB_URL
        if not url:
            raise ConfigurationError(
                "MAIN_DB_URL is not configured; set it before requesting sessions",
                key="MAIN_DB_URL",
            )

        from config.database.defaults import ECHO, POOL_SIZE, MAX_OVERFLOW, POOL_RECYCLE

        from config.database.defaults import ECHO, POOL_SIZE, MAX_OVERFLOW, POOL_RECYCLE

        engine = create_mysql_engine(
            url,
            echo=ECHO,
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_recycle=POOL_RECYCLE,
            url_key="MAIN_DB_URL",
        )
        main_session_factory = get_session_factory(engine)

    return main_session_factory


def require_garmin_session_factory() -> async_sessionmaker:
    """Return the Garmin session factory or raise a configuration error."""
    global garmin_session_factory

    if garmin_session_factory is None:
        url = garmin_db_url if garmin_db_url is not None else CONFIG_GARMIN_DB_URL
        if not url:
            raise ConfigurationError(
                "GARMIN_DB_URL is not configured; set it before requesting sessions",
                key="GARMIN_DB_URL",
            )
        from config.database.defaults import ECHO, POOL_SIZE, MAX_OVERFLOW, POOL_RECYCLE

        engine = create_mysql_engine(
            url,
            echo=ECHO,
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_recycle=POOL_RECYCLE,
            url_key="GARMIN_DB_URL",
        )
        garmin_session_factory = get_session_factory(engine)

    return garmin_session_factory


def require_blood_session_factory() -> async_sessionmaker:
    """Return the blood session factory or raise a configuration error."""
    global blood_session_factory

    if blood_session_factory is None:
        url = blood_db_url if blood_db_url is not None else CONFIG_BLOOD_DB_URL
        if not url:
            raise ConfigurationError(
                "BLOOD_DB_URL is not configured; set it before requesting sessions",
                key="BLOOD_DB_URL",
            )

        from config.database.defaults import ECHO, POOL_SIZE, MAX_OVERFLOW, POOL_RECYCLE

        engine = create_mysql_engine(
            url,
            echo=ECHO,
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_recycle=POOL_RECYCLE,
            url_key="BLOOD_DB_URL",
        )
        blood_session_factory = get_session_factory(engine)

    return blood_session_factory


def require_ufc_session_factory() -> async_sessionmaker:
    """Return the UFC session factory or raise a configuration error."""
    global ufc_session_factory

    if ufc_session_factory is None:
        url = ufc_db_url if ufc_db_url is not None else CONFIG_UFC_DB_URL
        if not url:
            raise ConfigurationError(
                "UFC_DB_URL is not configured; set it before requesting sessions",
                key="UFC_DB_URL",
            )

        from config.database.defaults import ECHO, POOL_SIZE, MAX_OVERFLOW, POOL_RECYCLE

        engine = create_mysql_engine(
            url,
            echo=ECHO,
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_recycle=POOL_RECYCLE,
            url_key="UFC_DB_URL",
        )
        ufc_session_factory = get_session_factory(engine)

    return ufc_session_factory


def require_cc4life_session_factory() -> async_sessionmaker:
    """Return the cc4life session factory or raise a configuration error."""
    global cc4life_session_factory

    if cc4life_session_factory is None:
        url = cc4life_db_url if cc4life_db_url is not None else CONFIG_CC4LIFE_DB_URL
        if not url:
            raise ConfigurationError(
                "CC4LIFE_DB_URL is not configured; set it before requesting sessions",
                key="CC4LIFE_DB_URL",
            )

        from config.database.defaults import ECHO, POOL_SIZE, MAX_OVERFLOW, POOL_RECYCLE

        engine = create_mysql_engine(
            url,
            echo=ECHO,
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_recycle=POOL_RECYCLE,
            url_key="CC4LIFE_DB_URL",
        )
        cc4life_session_factory = get_session_factory(engine)

    return cc4life_session_factory


__all__ = [
    "session_scope",
    "get_session_dependency",
    "require_main_session_factory",
    "require_garmin_session_factory",
    "require_blood_session_factory",
    "require_ufc_session_factory",
    "require_cc4life_session_factory",
    "main_session_factory",
    "garmin_session_factory",
    "blood_session_factory",
    "ufc_session_factory",
    "cc4life_session_factory",
]
