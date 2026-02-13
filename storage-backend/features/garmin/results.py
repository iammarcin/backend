"""Result objects returned by Garmin services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from fastapi.encoders import jsonable_encoder


@dataclass(slots=True)
class IngestResult:
    """Lightweight container describing the outcome of an ingest call."""

    record_type: str
    calendar_date: datetime | None
    rows_written: int = 1
    duplicates_skipped: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_repository(
        cls,
        record_type: str,
        record: Any,
        *,
        calendar_attr: str = "calendar_date",
        rows_written: int = 1,
        duplicates_skipped: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> "IngestResult":
        """Build a result instance from a SQLAlchemy model."""

        calendar_date = getattr(record, calendar_attr, None)
        return cls(
            record_type=record_type,
            calendar_date=calendar_date,
            rows_written=rows_written,
            duplicates_skipped=duplicates_skipped,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serialisable representation for API responses."""

        return {
            "record_type": self.record_type,
            "calendar_date": jsonable_encoder(self.calendar_date),
            "rows_written": self.rows_written,
            "duplicates_skipped": self.duplicates_skipped,
            "metadata": dict(self.metadata),
        }


__all__ = ["IngestResult"]
