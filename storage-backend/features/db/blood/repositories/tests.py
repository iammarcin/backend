"""Read-only repository for fetching blood test history."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import DatabaseError
from ..db_models import BloodTest, TestDefinition
from ..types import BloodTestRow

logger = logging.getLogger(__name__)


class BloodTestRepository:
    """Expose read operations for blood test records."""

    def __init__(self, *, log: logging.Logger | None = None) -> None:
        self._logger = log or logger

    async def list_tests(self, session: AsyncSession) -> list[BloodTestRow]:
        """Return blood tests ordered by most recent ``test_date`` first."""

        statement = (
            select(BloodTest)
            .options(selectinload(BloodTest.test_definition))
            .order_by(BloodTest.test_date.desc(), BloodTest.id.desc())
        )

        try:
            result = await session.execute(statement)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive logging
            self._logger.exception(
                "Failed to fetch blood tests", extra={"operation": "blood.tests.list"}
            )
            raise DatabaseError(
                "Failed to fetch blood tests", operation="blood.tests.list"
            ) from exc

        records = result.scalars().all()
        rows: list[BloodTestRow] = []

        for record in records:
            definition: TestDefinition | None = record.test_definition
            if definition is None:  # pragma: no cover - schema guard
                self._logger.warning(
                    "Blood test missing definition", extra={"test_id": record.id}
                )

            row: BloodTestRow = {
                "id": record.id,
                "test_definition_id": record.test_definition_id,
                "test_date": record.test_date,
                "result_value": record.result_value,
                "result_unit": record.result_unit,
                "reference_range": record.reference_range,
                "category": definition.category if definition else None,
                "test_name": definition.test_name if definition else None,
                "short_explanation": definition.short_explanation if definition else None,
                "long_explanation": definition.long_explanation if definition else None,
            }
            rows.append(row)

        self._logger.debug(
            "Fetched blood tests", extra={"operation": "blood.tests.list", "count": len(rows)}
        )
        return rows


__all__ = ["BloodTestRepository"]
