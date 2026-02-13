"""Database engine management utilities.

Supports both MySQL (aiomysql) and PostgreSQL (asyncpg) drivers.
"""

from __future__ import annotations

import logging
import os
import re
import ssl
from typing import AsyncIterator, Callable, Optional
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config.database.defaults import (
    ECHO as DB_ECHO,
    MAX_OVERFLOW as DB_MAX_OVERFLOW,
    POOL_RECYCLE as DB_POOL_RECYCLE,
    POOL_SIZE as DB_POOL_SIZE,
)
from core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

AsyncSessionFactory = async_sessionmaker[AsyncSession]
SessionDependency = Callable[[], AsyncIterator[AsyncSession]]

# Lazy-loaded engines and session factories - initialized to None
main_engine: Optional[AsyncEngine] = None
main_session_factory: Optional[async_sessionmaker] = None
garmin_engine: Optional[AsyncEngine] = None
garmin_session_factory: Optional[async_sessionmaker] = None
blood_engine: Optional[AsyncEngine] = None
blood_session_factory: Optional[async_sessionmaker] = None
ufc_engine: Optional[AsyncEngine] = None
ufc_session_factory: Optional[async_sessionmaker] = None


def _create_ssl_context(cert_path: str | None) -> ssl.SSLContext | None:
    """Create SSL context for PostgreSQL connection if certificate path provided.

    Args:
        cert_path: Path to CA certificate file (e.g., prod-ca-2021.crt)

    Returns:
        SSLContext configured with CA cert, or None if no cert path
    """
    if not cert_path:
        return None

    if not os.path.exists(cert_path):
        logger.warning("SSL certificate not found at %s, skipping SSL", cert_path)
        return None

    ctx = ssl.create_default_context(cafile=cert_path)

    # Skip hostname verification when connecting through proxy (e.g., Watson via nginx)
    # The proxy hostname won't match Supabase's certificate, but connection is still encrypted
    # and certificate validity is still verified against the CA cert
    skip_hostname_check = os.environ.get("SUPABASE_SSL_SKIP_HOSTNAME_CHECK", "").lower() == "true"
    if skip_hostname_check:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED  # Still verify cert, just not hostname
        logger.info("SSL enabled (hostname verification disabled for proxy)")
    else:
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        logger.info("SSL enabled with certificate: %s", cert_path)

    return ctx


def _extract_search_path_from_url(url: str) -> tuple[str, str | None]:
    """Extract search_path from PostgreSQL URL options and return clean URL.

    asyncpg doesn't accept 'options' as a URL parameter - it must be passed
    via connect_args['server_settings']['search_path'].

    Args:
        url: Database URL, possibly with ?options=-csearch_path=schema

    Returns:
        Tuple of (clean_url_without_options, schema_or_none)
    """
    if "?" not in url:
        return url, None

    parsed = urlparse(url)
    if not parsed.query:
        return url, None

    query_params = parse_qs(parsed.query)
    options = query_params.get("options", [])

    schema = None
    if options:
        # Parse options like "-csearch_path=aiapp" or "-csearch_path%3Daiapp"
        options_str = unquote(options[0])
        match = re.search(r"-csearch_path[=](\w+)", options_str)
        if match:
            schema = match.group(1)

    # Remove options from query string
    remaining_params = {k: v for k, v in query_params.items() if k != "options"}
    if remaining_params:
        new_query = "&".join(f"{k}={v[0]}" for k, v in remaining_params.items())
    else:
        new_query = ""

    clean_url = urlunparse(parsed._replace(query=new_query))
    return clean_url, schema


def create_mysql_engine(
    url: str,
    *,
    echo: bool = False,
    pool_size: int = 10,
    max_overflow: int = 10,
    pool_recycle: int = 900,
    url_key: str = "DB_URL",
) -> AsyncEngine:
    """Create an async SQLAlchemy engine for MySQL or PostgreSQL.

    Despite the name (kept for backward compatibility), this function
    supports both MySQL (aiomysql) and PostgreSQL (asyncpg) drivers.
    The driver is detected from the URL prefix.
    """
    if not url:
        raise ConfigurationError("Database connection URL is required", key=url_key)

    # Determine driver type from URL and set appropriate connect_args
    is_postgresql = url.startswith("postgresql")

    if is_postgresql:
        # Extract search_path from URL options (asyncpg doesn't accept options param)
        clean_url, schema = _extract_search_path_from_url(url)
        url = clean_url

        # asyncpg uses command_timeout and server_settings for search_path
        connect_args: dict = {"command_timeout": 10}
        if schema:
            connect_args["server_settings"] = {"search_path": schema}
            logger.debug("PostgreSQL search_path set to: %s", schema)

        # SSL certificate support for Supabase
        ssl_cert_path = os.environ.get("SUPABASE_SSL_CERT_PATH")
        ssl_context = _create_ssl_context(ssl_cert_path)
        if ssl_context:
            connect_args["ssl"] = ssl_context
    else:
        # aiomysql uses connect_timeout
        connect_args = {"connect_timeout": 5}

    return create_async_engine(
        url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        isolation_level="READ COMMITTED",
        connect_args=connect_args,
    )


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """Return an ``async_sessionmaker`` bound to ``engine``."""

    return async_sessionmaker(engine, expire_on_commit=False)


async def dispose_all_engines() -> None:
    """Dispose any initialized async engines.

    Useful for scripts/tests to avoid event-loop shutdown warnings.
    """
    global main_engine, garmin_engine, blood_engine, ufc_engine
    global main_session_factory, garmin_session_factory, blood_session_factory, ufc_session_factory

    engines = [
        ("main", main_engine),
        ("garmin", garmin_engine),
        ("blood", blood_engine),
        ("ufc", ufc_engine),
    ]

    for name, engine in engines:
        if engine is None:
            continue
        try:
            await engine.dispose()
        except Exception:  # pragma: no cover - best-effort cleanup
            logger.warning("Failed to dispose %s engine", name, exc_info=True)
        finally:
            if name == "main":
                main_engine = None
                main_session_factory = None
            elif name == "garmin":
                garmin_engine = None
                garmin_session_factory = None
            elif name == "blood":
                blood_engine = None
                blood_session_factory = None
            elif name == "ufc":
                ufc_engine = None
                ufc_session_factory = None


__all__ = ["create_mysql_engine", "get_session_factory", "dispose_all_engines"]
