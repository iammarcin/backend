import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from features.batch.db_models import BatchJob
from features.batch.repositories.batch_job_repository import BatchJobRepository
from infrastructure.db.base import Base


class _TestUser(Base):
    __tablename__ = "TestUsers"
    id = Column(Integer, primary_key=True)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_TestUser.__table__.create)
        await conn.run_sync(BatchJob.__table__.create)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_batch_job(db_session: AsyncSession):
    repo = BatchJobRepository(db_session)

    job = await repo.create(
        job_id="batch_test123",
        customer_id=1,
        provider="openai",
        model="gpt-5-mini",
        request_count=5,
        metadata={"description": "unit test"},
    )
    await db_session.commit()

    assert job.job_id == "batch_test123"
    assert job.status == "queued"
    assert job.metadata_payload["description"] == "unit test"


@pytest.mark.asyncio
async def test_update_status(db_session: AsyncSession):
    repo = BatchJobRepository(db_session)
    await repo.create(
        job_id="batch_status",
        customer_id=1,
        provider="anthropic",
        model="claude-haiku-4-5",
        request_count=2,
    )
    await db_session.commit()

    updated = await repo.update_status(
        job_id="batch_status",
        status="completed",
        results_url="s3://bucket/results.jsonl",
    )
    await db_session.commit()

    assert updated is True
    job = await repo.get_by_job_id("batch_status")
    assert job.status == "completed"
    assert job.results_url == "s3://bucket/results.jsonl"


@pytest.mark.asyncio
async def test_update_counts_and_list(db_session: AsyncSession):
    repo = BatchJobRepository(db_session)
    for idx in range(3):
        await repo.create(
            job_id=f"batch_list_{idx}",
            customer_id=1,
            provider="google",
            model="gemini-2.5-flash",
            request_count=idx + 1,
        )
    await db_session.commit()

    await repo.update_counts(
        job_id="batch_list_1",
        succeeded=2,
        failed=1,
    )
    await db_session.commit()

    job = await repo.get_by_job_id("batch_list_1")
    assert job.succeeded_count == 2
    assert job.failed_count == 1

    jobs = await repo.list_by_customer(customer_id=1, limit=10)
    assert len(jobs) == 3


@pytest.mark.asyncio
async def test_get_pending_jobs(db_session: AsyncSession):
    repo = BatchJobRepository(db_session)
    await repo.create(
        job_id="pending_job",
        customer_id=1,
        provider="openai",
        model="gpt-5-mini",
        request_count=1,
    )
    await db_session.commit()

    pending = await repo.get_pending_jobs()
    assert len(pending) == 1
    assert pending[0].job_id == "pending_job"

    deleted = await repo.delete("pending_job")
    await db_session.commit()
    assert deleted is True
