from __future__ import annotations

from datetime import date

import pytest

from features.garmin.service import DatasetResult
from features.garmin.tasks import DEFAULT_SYNC_DATASETS, build_nightly_sync_job, run_nightly_sync


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class DummySession:
    async def commit(self) -> None:  # pragma: no cover - trivial method
        pass

    async def rollback(self) -> None:  # pragma: no cover - defensive method
        pass

    async def close(self) -> None:  # pragma: no cover - trivial method
        pass


class DummyFactory:
    def __call__(self) -> DummySession:  # pragma: no cover - simple factory
        return DummySession()


class ProviderStub:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def fetch_dataset(self, dataset: str, query, customer_id: int, save_to_db: bool, session) -> DatasetResult:
        self.calls.append(dataset)
        return DatasetResult(dataset=dataset, items=[{"id": 1}], raw=[], ingested=[], saved=True)


@pytest.mark.anyio
async def test_run_nightly_sync_returns_summary():
    provider = ProviderStub()
    summary = await run_nightly_sync(
        provider,
        DummyFactory(),
        customer_id=42,
        target_date=date(2024, 7, 1),
        datasets=("sleep", "body_composition"),
    )

    assert provider.calls == ["sleep", "body_composition"]
    assert summary["sleep"]["status"] == "ok"
    assert summary["sleep"]["saved"] is True


@pytest.mark.anyio
async def test_build_nightly_sync_job_wraps_callable():
    provider = ProviderStub()
    job = build_nightly_sync_job(provider, DummyFactory(), 7, datasets=None)
    result = await job()

    assert set(provider.calls) == set(DEFAULT_SYNC_DATASETS)
    assert set(result.keys()) == set(DEFAULT_SYNC_DATASETS)
