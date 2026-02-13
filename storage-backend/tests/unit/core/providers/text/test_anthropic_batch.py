from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.providers.text.anthropic import AnthropicTextProvider


@pytest.mark.asyncio
async def test_anthropic_batch_generation():
    mock_ops = AsyncMock()
    mock_ops.submit_and_wait.return_value = [
        {
            "custom_id": "req-1",
            "result": SimpleNamespace(
                type="succeeded",
                message=SimpleNamespace(
                    content=[SimpleNamespace(text="Answer 1")],
                    model="claude-sonnet-4-5",
                    stop_reason="end_turn",
                    usage=SimpleNamespace(input_tokens=10, output_tokens=20),
                ),
            ),
        },
        {
            "custom_id": "req-2",
            "result": SimpleNamespace(
                type="errored",
                error=SimpleNamespace(message="bad request", type="invalid_request_error"),
            ),
        },
    ]

    with patch.dict("core.providers.text.anthropic.ai_clients", {"anthropic_async": AsyncMock()}):
        with patch("core.providers.text.anthropic.AnthropicBatchOperations", return_value=mock_ops):
            provider = AnthropicTextProvider()
            requests = [
                {"custom_id": "req-1", "prompt": "Hello"},
                {"custom_id": "req-2", "prompt": "World"},
            ]

            responses = await provider.generate_batch(requests)

            assert len(responses) == 2
            assert responses[0].text == "Answer 1"
            assert responses[0].metadata["usage"]["input_tokens"] == 10
            assert responses[1].has_error is True
            assert responses[1].metadata["error_type"] == "invalid_request_error"


@pytest.mark.asyncio
async def test_anthropic_batch_handles_missing_results():
    mock_ops = AsyncMock()
    mock_ops.submit_and_wait.return_value = []

    with patch.dict("core.providers.text.anthropic.ai_clients", {"anthropic_async": AsyncMock()}):
        with patch("core.providers.text.anthropic.AnthropicBatchOperations", return_value=mock_ops):
            provider = AnthropicTextProvider()
            requests = [{"custom_id": "req-1", "prompt": "Hello"}]

            responses = await provider.generate_batch(requests)

            assert responses[0].has_error is True
            assert responses[0].metadata["error_type"] == "MissingResult"
