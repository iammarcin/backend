from unittest.mock import AsyncMock, patch

import pytest

from core.providers.text.openai import OpenAITextProvider


@pytest.mark.asyncio
async def test_openai_batch_generation():
    mock_batch_ops = AsyncMock()
    mock_batch_ops.submit_and_wait.return_value = [
        {
            "custom_id": "req-1",
            "response": {
                "body": {
                    "model": "gpt-4o",
                    "choices": [{"message": {"content": "Response 1"}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": 10},
                }
            },
        },
        {
            "custom_id": "req-2",
            "response": {
                "body": {
                    "model": "gpt-4o",
                    "choices": [{"message": {"content": "Response 2"}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": 12},
                }
            },
        },
    ]

    with patch.dict("core.providers.text.openai.ai_clients", {"openai_async": AsyncMock()}):
        with patch("core.providers.text.openai.OpenAIBatchOperations", return_value=mock_batch_ops):
            provider = OpenAITextProvider()
            requests = [
                {"custom_id": "req-1", "prompt": "Hello"},
                {"custom_id": "req-2", "prompt": "World"},
            ]

            responses = await provider.generate_batch(requests)

            assert len(responses) == 2
            assert responses[0].text == "Response 1"
            assert responses[0].custom_id == "req-1"
            assert responses[1].text == "Response 2"
            assert responses[1].custom_id == "req-2"


@pytest.mark.asyncio
async def test_openai_batch_handles_errors():
    mock_batch_ops = AsyncMock()
    mock_batch_ops.submit_and_wait.return_value = [
        {
            "custom_id": "req-1",
            "response": {
                "body": {
                    "model": "gpt-4o",
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                }
            },
        },
        {
            "custom_id": "req-2",
            "error": {"message": "Rate limit exceeded", "type": "rate_limit_error"},
        },
    ]

    with patch.dict("core.providers.text.openai.ai_clients", {"openai_async": AsyncMock()}):
        with patch("core.providers.text.openai.OpenAIBatchOperations", return_value=mock_batch_ops):
            provider = OpenAITextProvider()

            requests = [
                {"custom_id": "req-1", "prompt": "Hello"},
                {"custom_id": "req-2", "prompt": "World"},
            ]

            responses = await provider.generate_batch(requests)

            assert responses[0].has_error is False
            assert responses[1].has_error is True
            assert responses[1].metadata["error_type"] == "rate_limit_error"
