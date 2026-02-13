"""Common helpers for Garmin repositories."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Sequence, TypeVar

from sqlalchemy import Select, asc, desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeMeta

from config.environment import IS_POSTGRESQL
from core.exceptions import DatabaseError

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=DeclarativeMeta)


def _get_upsert_statement(
    model: type, values: dict[str, Any], is_postgresql: bool, conflict_columns: list[str]
):
    """Build database-specific upsert statement.

    MySQL: INSERT ... ON DUPLICATE KEY UPDATE (triggers on ANY unique constraint)
    PostgreSQL: INSERT ... ON CONFLICT DO UPDATE (requires explicit constraint specification)

    For PostgreSQL, conflict_columns specifies the unique constraint to use (e.g., customer_id, calendar_date).
    """
    if is_postgresql:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        statement = pg_insert(model).values(**values)

        # Build update dict using excluded (PostgreSQL syntax)
        # Exclude conflict columns and id from updates
        update_columns = {
            column.name: statement.excluded[column.name]
            for column in model.__table__.columns
            if column.name not in conflict_columns and column.name != "id" and column.name in values
        }

        # If no columns to update (only key columns provided), use DO NOTHING
        if not update_columns:
            return statement.on_conflict_do_nothing(index_elements=conflict_columns)

        return statement.on_conflict_do_update(
            index_elements=conflict_columns,
            set_=update_columns,
        )
    else:
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        statement = mysql_insert(model).values(**values)

        # Build update dict using inserted (MySQL syntax)
        update_columns = {
            column.name: statement.inserted[column.name]
            for column in model.__table__.columns
            if column.name != "id" and column.name in values
        }

        return statement.on_duplicate_key_update(**update_columns)


class GarminRepository:
    """Base repository providing upsert helpers and logging."""

    def __init__(self, *, log: logging.Logger | None = None) -> None:
        self._logger = log or logger

    async def _upsert(
        self,
        session: AsyncSession,
        model: ModelType,
        values: dict[str, Any],
        lookup_filters: Sequence[Any],
        *,
        operation: str,
    ) -> Any:
        """Execute an upsert and fetch the row.

        MySQL: INSERT ... ON DUPLICATE KEY UPDATE
        PostgreSQL: INSERT ... ON CONFLICT DO UPDATE

        Only columns provided in ``values`` will be part of the UPDATE clause so the
        generated SQL never references fields that were absent from the INSERT.

        The lookup_filters determine which columns form the natural key for conflict resolution.
        """
        # Extract column names from lookup_filters for PostgreSQL conflict target
        # lookup_filters are BinaryExpression objects like Model.column == value
        conflict_columns: list[str] = []
        for filter_expr in lookup_filters:
            if hasattr(filter_expr, "left") and hasattr(filter_expr.left, "key"):
                conflict_columns.append(filter_expr.left.key)

        upsert_stmt = _get_upsert_statement(model, values, IS_POSTGRESQL, conflict_columns)

        try:
            await session.execute(upsert_stmt)
            await session.flush()
            query: Select[Any] = select(model).where(*lookup_filters)
            result = await session.execute(query)
            instance = result.scalar_one_or_none()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive logging
            self._logger.exception("Database operation failed", extra={"operation": operation})
            raise DatabaseError("Database operation failed", operation=operation) from exc

        if instance is None:
            raise DatabaseError("Upsert did not return a record", operation=operation)

        return instance

    async def _fetch(
        self,
        session: AsyncSession,
        model: ModelType,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
        extra_filters: Sequence[Any] | None = None,
        operation: str,
    ) -> list[Any]:
        """Return rows for ``customer_id`` bounded by optional date filters."""

        order_column = desc(model.calendar_date) if descending else asc(model.calendar_date)
        statement: Select[Any] = select(model).where(model.customer_id == customer_id).order_by(order_column)

        if start is not None:
            statement = statement.where(model.calendar_date >= start)
        if end is not None:
            statement = statement.where(model.calendar_date <= end)

        for filter_clause in extra_filters or ():
            statement = statement.where(filter_clause)

        if offset:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        try:
            result = await session.execute(statement)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive logging
            self._logger.exception("Database select failed", extra={"operation": operation})
            raise DatabaseError("Database operation failed", operation=operation) from exc

        records = list(result.scalars().all())
        return records


__all__ = ["GarminRepository"]
