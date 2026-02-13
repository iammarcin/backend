from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.exceptions import NotFoundError, ValidationError
from core.pydantic_schemas import ProviderResponse
from features.batch.schemas.requests import BatchRequestItem, CreateBatchRequest
from features.batch.services.batch_service import BatchService


def _mock_batch_job(**overrides):
    defaults = {
        "job_id": "batch_123",
        "customer_id": 1,
        "provider": "openai",
        "model": "gpt-4o",
        "status": "completed",
        "request_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "expired_count": 0,
        "created_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "completed_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "results_url": None,
        "error_message": None,
        "metadata_payload": {"provider_requests": [], "responses": [ProviderResponse(text="hi", model="gpt-4o", provider="openai").model_dump()]},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_submit_batch_success():
    repo = AsyncMock()
    batch_job = _mock_batch_job(
        status="pending",
        metadata_payload={
            "provider_requests": [{"custom_id": "req-1", "prompt": "Hello"}],
            "responses": [ProviderResponse(text="hello", model="gpt-4o", provider="openai").model_dump()]
        }
    )
    repo.create.return_value = batch_job
    repo.get_by_job_id.return_value = batch_job

    provider_mock = AsyncMock()
    provider_mock.generate_batch.return_value = [
        ProviderResponse(text="hello", model="gpt-4o", provider="openai")
    ]

    request = CreateBatchRequest(
        model="gpt-4o",
        requests=[BatchRequestItem(custom_id="req-1", prompt="Hello")],
    )

    with patch("features.batch.services.batch_service.get_model_config") as mock_model_config:
        mock_model_config.return_value = SimpleNamespace(provider_name="openai", supports_batch_api=True)
        with patch("features.batch.services.batch_service.get_text_provider", return_value=provider_mock):
            service = BatchService(repo)
            result = await service.submit_batch(request=request, customer_id=1)

    assert result.job_id == batch_job.job_id
    provider_mock.generate_batch.assert_awaited()
    repo.update_status.assert_awaited()
    repo.update_counts.assert_awaited()
    repo.set_expires_at.assert_awaited()


@pytest.mark.asyncio
async def test_get_batch_status_not_found():
    repo = AsyncMock()
    repo.get_by_job_id.return_value = None

    service = BatchService(repo)

    with pytest.raises(NotFoundError):
        await service.get_batch_status("missing", customer_id=1)


@pytest.mark.asyncio
async def test_get_batch_results_expired():
    expired_job = _mock_batch_job(
        status="completed",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    repo = AsyncMock()
    repo.get_by_job_id.return_value = expired_job

    service = BatchService(repo)

    with pytest.raises(ValidationError):
        await service.get_batch_results("batch_1", customer_id=1)


@pytest.mark.asyncio
async def test_cancel_batch_invalid_status():
    job = _mock_batch_job(status="completed")
    repo = AsyncMock()
    repo.get_by_job_id.return_value = job

    service = BatchService(repo)

    with pytest.raises(ValidationError):
        await service.cancel_batch("batch_1", customer_id=1)
