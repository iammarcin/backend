"""Database models for batch job tracking."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.sql import func

from infrastructure.db.base import Base


class BatchJob(Base):
    """Batch job tracking record."""

    __tablename__ = "batch_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(255), unique=True, nullable=False, index=True)
    customer_id = Column(
        Integer,
        ForeignKey("Users.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False, index=True)
    model = Column(String(100), nullable=False)
    status = Column(
        Enum(
            "queued",
            "processing",
            "completed",
            "failed",
            "cancelled",
            "expired",
            name="batch_job_status",
        ),
        nullable=False,
        default="queued",
        index=True,
    )

    request_count = Column(Integer, nullable=False, default=0)
    succeeded_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    cancelled_count = Column(Integer, default=0)
    expired_count = Column(Integer, default=0)

    results_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    metadata_payload = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("idx_status_provider", "status", "provider"),
        Index("idx_customer_created", "customer_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<BatchJob(job_id='{self.job_id}', status='{self.status}', "
            f"provider='{self.provider}')>"
        )


__all__ = ["BatchJob"]
