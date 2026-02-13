"""SQLAlchemy declarative base helpers for domain models."""

from __future__ import annotations

from typing import Final

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


metadata = Base.metadata


async def prepare_database(engine: AsyncEngine) -> None:
    """Create all tables for the configured metadata on the given engine."""

    async with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            # SQLite lacks schema support; skip schema-qualified tables like cc4life.
            tables = [table for table in metadata.sorted_tables if table.schema is None]
            await connection.run_sync(metadata.create_all, tables=tables)
        else:
            await connection.run_sync(metadata.create_all)


__all__: Final = ["Base", "metadata", "prepare_database"]
