from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.providers.text.gemini.provider import GeminiTextProvider


@pytest.mark.asyncio
async def test_gemini_batch_generation():
    mock_ops = AsyncMock()
    mock_ops.submit_and_wait.return_value = [
        {
            "key": "req-1",
            "response": SimpleNamespace(
                text="Gemini answer",
                candidates=[SimpleNamespace(finish_reason="STOP", content=SimpleNamespace(parts=[SimpleNamespace(text="Gemini answer")]))],
            ),
        },
        {"key": "req-2", "error": {"message": "quota exceeded"}},
    ]

    with patch.dict("core.providers.text.gemini.provider.ai_clients", {"gemini": AsyncMock()}):
        with patch("core.providers.text.gemini.provider.GeminiBatchOperations", return_value=mock_ops):
            provider = GeminiTextProvider()
            requests = [
                {"custom_id": "req-1", "prompt": "Hello"},
                {"custom_id": "req-2", "prompt": "World"},
            ]

            responses = await provider.generate_batch(requests)

            assert len(responses) == 2
            assert responses[0].text == "Gemini answer"
            assert responses[0].metadata["finish_reason"] == "STOP"
            assert responses[1].has_error is True
            assert responses[1].metadata["error_type"] == "batch_error"


@pytest.mark.asyncio
async def test_gemini_batch_missing_results():
    mock_ops = AsyncMock()
    mock_ops.submit_and_wait.return_value = []

    with patch.dict("core.providers.text.gemini.provider.ai_clients", {"gemini": AsyncMock()}):
        with patch("core.providers.text.gemini.provider.GeminiBatchOperations", return_value=mock_ops):
            provider = GeminiTextProvider()
            requests = [{"custom_id": "req-1", "prompt": "Hello"}]

            responses = await provider.generate_batch(requests)

            assert responses[0].has_error is True
            assert responses[0].metadata["error_type"] == "MissingResult"
