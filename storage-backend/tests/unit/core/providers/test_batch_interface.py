import pytest
from core.providers.base import BaseTextProvider
from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse


class MockBatchProvider(BaseTextProvider):
    capabilities = ProviderCapabilities(batch_api=True, batch_max_requests=50, batch_max_file_size_mb=10)

    async def generate(self, prompt, **kwargs):
        return ProviderResponse(text=f"Response to: {prompt}", model="mock-model", provider="mock")


class MockNoBatchProvider(BaseTextProvider):
    capabilities = ProviderCapabilities(batch_api=False)

    async def generate(self, prompt, **kwargs):
        return ProviderResponse(text=f"Response to: {prompt}", model="mock-model", provider="mock")


@pytest.mark.asyncio
async def test_default_batch_implementation():
    provider = MockNoBatchProvider()
    requests = [
        {"custom_id": "req-1", "prompt": "Hello"},
        {"custom_id": "req-2", "prompt": "World"},
        {"custom_id": "req-3", "prompt": "Batch"},
    ]

    results = await provider.generate_batch(requests)

    assert len(results) == 3
    for idx, response in enumerate(results, start=1):
        assert response.text.endswith(requests[idx - 1]["prompt"])
        assert response.custom_id == f"req-{idx}"


@pytest.mark.asyncio
async def test_batch_error_handling():
    class ErrorProvider(MockNoBatchProvider):
        async def generate(self, prompt, **kwargs):
            if "error" in prompt:
                raise ValueError("boom")
            return await super().generate(prompt, **kwargs)

    provider = ErrorProvider()
    requests = [
        {"custom_id": "req-1", "prompt": "ok"},
        {"custom_id": "req-2", "prompt": "error"},
        {"custom_id": "req-3", "prompt": "still ok"},
    ]

    results = await provider.generate_batch(requests)

    assert results[0].has_error is False
    assert results[1].has_error is True
    assert results[1].metadata["error_type"] == "ValueError"
    assert results[2].has_error is False


@pytest.mark.asyncio
async def test_batch_preserves_order_and_validates():
    provider = MockNoBatchProvider()
    requests = [{"custom_id": f"req-{i}", "prompt": f"Prompt {i}"} for i in range(5)]
    results = await provider.generate_batch(requests)

    for idx, response in enumerate(results):
        assert response.custom_id == f"req-{idx}"

def test_provider_capabilities():
    batch_provider = MockBatchProvider()
    no_batch_provider = MockNoBatchProvider()

    assert batch_provider.capabilities.batch_api is True
    assert batch_provider.capabilities.batch_max_requests == 50
    assert no_batch_provider.capabilities.batch_api is False
