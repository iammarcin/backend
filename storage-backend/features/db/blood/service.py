"""Service layer orchestrating Blood domain data access."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from .types import BloodTestRow

from .repositories import (
    BloodRepositoryCollection,
    BloodTestRepository,
    build_repositories,
)
from .schemas import BloodTestFilterParams, BloodTestItem, BloodTestListResponse


class BloodService:
    """Provide high-level operations for blood test data."""

    def __init__(
        self,
        repositories: Optional[BloodRepositoryCollection] = None,
        *,
        tests_repo: BloodTestRepository | None = None,
    ) -> None:
        if tests_repo is not None:
            self._tests_repo = tests_repo
        else:
            collection = repositories or build_repositories()
            self._tests_repo = collection.get("tests") or BloodTestRepository()

    async def list_tests(
        self,
        session: AsyncSession,
        filters: BloodTestFilterParams | None = None,
    ) -> BloodTestListResponse:
        """Return blood tests enriched with metadata for API serialisation."""

        rows = await self._tests_repo.list_tests(session)
        filtered_rows = self._apply_filters(rows, filters)
        total_count = len(filtered_rows)
        latest_test_date = self._resolve_latest_date(filtered_rows)

        limited_rows = self._apply_limit(filtered_rows, filters)
        items = [BloodTestItem.model_validate(row) for row in limited_rows]

        applied_filters = filters.model_copy() if filters else None

        return BloodTestListResponse(
            items=items,
            total_count=total_count,
            latest_test_date=latest_test_date,
            filters=applied_filters,
        )

    @staticmethod
    def _apply_filters(
        rows: Sequence[BloodTestRow], filters: BloodTestFilterParams | None
    ) -> list[BloodTestRow]:
        if not filters:
            return list(rows)

        def _matches(row: BloodTestRow) -> bool:
            if filters.start_date and row["test_date"] < filters.start_date:
                return False
            if filters.end_date and row["test_date"] > filters.end_date:
                return False
            if filters.category and row["category"] != filters.category:
                return False
            return True

        return [row for row in rows if _matches(row)]

    @staticmethod
    def _apply_limit(
        rows: Sequence[BloodTestRow], filters: BloodTestFilterParams | None
    ) -> Sequence[BloodTestRow]:
        if not filters or filters.limit is None:
            return rows
        return rows[: filters.limit]

    @staticmethod
    def _resolve_latest_date(rows: Iterable[BloodTestRow]) -> date | None:
        latest: date | None = None
        for row in rows:
            if latest is None or row["test_date"] > latest:
                latest = row["test_date"]
        return latest


__all__ = ["BloodService"]
