"""Repository for batch job persistence."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from features.batch.db_models import BatchJob


class BatchJobRepository:
    """CRUD helper for BatchJob records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        job_id: str,
        customer_id: int,
        provider: str,
        model: str,
        request_count: int,
        metadata: Optional[dict] = None,
    ) -> BatchJob:
        batch_job = BatchJob(
            job_id=job_id,
            customer_id=customer_id,
            provider=provider,
            model=model,
            request_count=request_count,
            status="queued",
            metadata_payload=metadata or {},
        )
        self.session.add(batch_job)
        await self.session.flush()
        await self.session.refresh(batch_job)
        return batch_job

    async def get_by_job_id(self, job_id: str) -> Optional[BatchJob]:
        stmt = select(BatchJob).where(BatchJob.job_id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, batch_id: int) -> Optional[BatchJob]:
        stmt = select(BatchJob).where(BatchJob.id == batch_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_customer(
        self,
        *,
        customer_id: int,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[BatchJob]:
        stmt = select(BatchJob).where(BatchJob.customer_id == customer_id)
        if status:
            stmt = stmt.where(BatchJob.status == status)
        stmt = stmt.order_by(desc(BatchJob.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        *,
        job_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        results_url: Optional[str] = None,
        error_message: Optional[str] = None,
        commit: bool = False,
    ) -> bool:
        update_data = {"status": status}
        if started_at:
            update_data["started_at"] = started_at
        if completed_at:
            update_data["completed_at"] = completed_at
        if results_url:
            update_data["results_url"] = results_url
        if error_message:
            update_data["error_message"] = error_message

        stmt = update(BatchJob).where(BatchJob.job_id == job_id).values(**update_data)
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return result.rowcount > 0

    async def update_counts(
        self,
        *,
        job_id: str,
        succeeded: int = 0,
        failed: int = 0,
        cancelled: int = 0,
        expired: int = 0,
        commit: bool = False,
    ) -> bool:
        stmt = (
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(
                succeeded_count=succeeded,
                failed_count=failed,
                cancelled_count=cancelled,
                expired_count=expired,
            )
        )
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return result.rowcount > 0

    async def set_expires_at(self, *, job_id: str, expires_at: datetime, commit: bool = False) -> bool:
        stmt = (
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(expires_at=expires_at)
        )
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return result.rowcount > 0

    async def delete(self, job_id: str, *, commit: bool = False) -> bool:
        stmt = update(BatchJob).where(BatchJob.job_id == job_id).values(status="cancelled")
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return result.rowcount > 0

    async def update_metadata(self, *, job_id: str, metadata: dict, commit: bool = False) -> bool:
        """Replace metadata payload for a batch job."""

        stmt = (
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(metadata_payload=metadata)
        )
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return result.rowcount > 0

    async def get_pending_jobs(self, limit: int = 100) -> List[BatchJob]:
        stmt = (
            select(BatchJob)
            .where(BatchJob.status.in_(["queued", "processing"]))
            .order_by(BatchJob.created_at)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["BatchJobRepository"]
