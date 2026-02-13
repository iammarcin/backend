"""Tests for the batch request builder helpers."""

from __future__ import annotations

from features.batch.request_builder import BatchRequestBuilder
from features.batch.schemas.requests import BatchRequestItem, CreateBatchRequest


def test_build_provider_requests_resolves_model_aliases() -> None:
    request = CreateBatchRequest(
        model="claude-mini",
        requests=[
            BatchRequestItem(custom_id="session-1", prompt="hi there"),
            BatchRequestItem(custom_id="session-2", prompt="hello", model="claude-haiku-4.5"),
        ],
    )

    provider_requests = BatchRequestBuilder.build_provider_requests(request)

    assert provider_requests[0]["model"] == "claude-haiku-4-5"
    assert provider_requests[1]["model"] == "claude-haiku-4-5"
