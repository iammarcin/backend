"""FastAPI dependencies for batch feature."""

from __future__ import annotations

from typing import AsyncGenerator

from infrastructure.db.mysql import require_main_session_factory, session_scope
from features.batch.repositories.batch_job_repository import BatchJobRepository


async def get_batch_job_repository() -> AsyncGenerator[BatchJobRepository, None]:
    """Yield a repository bound to a database session."""

    session_factory = require_main_session_factory()
    async with session_scope(session_factory) as session:
        yield BatchJobRepository(session)


__all__ = ["get_batch_job_repository"]
