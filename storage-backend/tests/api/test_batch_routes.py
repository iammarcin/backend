from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from core.auth import require_auth_context
from core.pydantic_schemas import ProviderResponse
from features.batch.dependencies import get_batch_job_repository
from features.batch.routes import router
from features.batch.schemas.responses import BatchJobListResponse, BatchJobResponse


class _FakeBatchService:
    def __init__(self, job_payload: Dict[str, Any]) -> None:
        self.job = BatchJobResponse(**job_payload)
        self.list_payload = BatchJobListResponse(jobs=[self.job], total=1, limit=20, offset=0)
        self.results: List[ProviderResponse] = [
            ProviderResponse(text="result", model="gpt-4o", provider="openai", metadata={"custom_id": "req-1"})
        ]

    async def get_batch_status(self, job_id: str, customer_id: int) -> BatchJobResponse:
        return self.job

    async def get_batch_results(self, job_id: str, customer_id: int) -> List[ProviderResponse]:
        return self.results

    async def list_batches(self, customer_id: int, limit: int, offset: int, status: str | None = None):
        return self.list_payload.model_dump()

    async def submit_batch(self, request, customer_id: int) -> BatchJobResponse:
        return self.job

    async def cancel_batch(self, job_id: str, customer_id: int) -> BatchJobResponse:
        return self.job


def _sample_job_payload() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "job_id": "batch_123",
        "provider": "openai",
        "model": "gpt-4o",
        "status": "completed",
        "request_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "expired_count": 0,
        "created_at": now,
        "started_at": now,
        "completed_at": now,
        "expires_at": None,
        "results_url": None,
        "error_message": None,
        "metadata_payload": {},
    }


def _build_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    fake_service = _FakeBatchService(_sample_job_payload())
    app = FastAPI()
    app.include_router(router)

    async def fake_auth():
        return {"customer_id": 1}

    async def fake_repo():
        return None

    app.dependency_overrides[require_auth_context] = fake_auth
    app.dependency_overrides[get_batch_job_repository] = fake_repo
    monkeypatch.setattr("features.batch.routes._get_service", lambda repo: fake_service)
    return app


@pytest.mark.asyncio
async def test_submit_batch_endpoint(monkeypatch: pytest.MonkeyPatch):
    app = _build_app(monkeypatch)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/batch/",
            json={
                "requests": [
                    {"custom_id": "req-1", "prompt": "Hello"},
                    {"custom_id": "req-2", "prompt": "World"},
                ],
                "model": "gpt-4o",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["job_id"] == "batch_123"


@pytest.mark.asyncio
async def test_get_batch_status_endpoint(monkeypatch: pytest.MonkeyPatch):
    app = _build_app(monkeypatch)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/batch/batch_123")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["job_id"] == "batch_123"


@pytest.mark.asyncio
async def test_get_batch_results_endpoint(monkeypatch: pytest.MonkeyPatch):
    app = _build_app(monkeypatch)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/batch/batch_123/results")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["metadata"]["custom_id"] == "req-1"


@pytest.mark.asyncio
async def test_list_batches_endpoint(monkeypatch: pytest.MonkeyPatch):
    app = _build_app(monkeypatch)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/batch/?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 1
