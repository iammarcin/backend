"""Helper utilities for configuration modules."""

from __future__ import annotations


def build_database_url(
    user: str,
    password: str | None,
    host: str,
    database: str,
    *,
    driver: str = "postgresql+asyncpg",
    schema: str | None = None,
    port: int | None = None,
) -> str:
    """Build async database connection string.

    Args:
        user: Database username
        password: Database password (can be None for socket auth)
        host: Database host (can include port as host:port)
        database: Database name
        driver: SQLAlchemy driver string (default: postgresql+asyncpg)
        schema: PostgreSQL schema to set as search_path (optional)
        port: Database port (optional, can also be in host)

    Returns:
        Async SQLAlchemy connection URL
    """
    credentials = f"{user}:{password}" if password else user

    # Handle port in host or separate port arg
    if port and ":" not in host:
        host_with_port = f"{host}:{port}"
    else:
        host_with_port = host

    url = f"{driver}://{credentials}@{host_with_port}/{database}"

    if schema:
        # PostgreSQL search_path via connection options
        url += f"?options=-csearch_path%3D{schema}"

    return url


def build_mysql_url(user: str, password: str | None, host: str, database: str) -> str:
    """Return an async MySQL connection string for the provided credentials."""
    return build_database_url(user, password, host, database, driver="mysql+aiomysql")


def build_postgresql_url(
    user: str,
    password: str | None,
    host: str,
    database: str,
    *,
    schema: str | None = None,
    port: int = 5432,
) -> str:
    """Return an async PostgreSQL connection string for the provided credentials."""
    return build_database_url(
        user, password, host, database,
        driver="postgresql+asyncpg",
        schema=schema,
        port=port,
    )
