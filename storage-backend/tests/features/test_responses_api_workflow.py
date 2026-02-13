"""End-to-end workflow tests for Responses API."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.providers.factory import get_text_provider
from core.providers.registry import get_model_config


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client with Responses API support."""
    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    mock_client.responses.create = AsyncMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client


def test_gpt5_nano_uses_responses_api(mock_openai_client):
    """Test that GPT-5 nano models automatically use the Responses API."""
    settings = {
        "text": {
            "model": "gpt-5-nano",
            "enable_reasoning": False,
        }
    }

    mock_response = MagicMock()
    mock_response.output = [MagicMock(type="text", text="GPT-5 response")]
    mock_openai_client.responses.create.return_value = mock_response

    with patch("core.providers.text.openai.ai_clients", {"openai_async": mock_openai_client}):
        provider = get_text_provider(settings)

        result = asyncio.run(
            provider.generate(
                prompt="Hello",
                model="gpt-5-nano",
            )
        )

    mock_openai_client.responses.create.assert_called_once()
    mock_openai_client.chat.completions.create.assert_not_called()
    assert result.text == "GPT-5 response"


def test_gpt4o_uses_chat_completions(mock_openai_client):
    """Test that GPT-4o models use Chat Completions API."""
    settings = {
        "text": {
            "model": "gpt-4o",
            "enable_reasoning": False,
        }
    }

    mock_response = MagicMock()
    choice = MagicMock()
    choice.message = MagicMock()
    choice.message.content = "GPT-4o response"
    choice.message.reasoning_content = None
    mock_response.choices = [choice]
    mock_response.usage = None
    mock_openai_client.chat.completions.create.return_value = mock_response

    with patch("core.providers.text.openai.ai_clients", {"openai_async": mock_openai_client}):
        provider = get_text_provider(settings)

        result = asyncio.run(
            provider.generate(
                prompt="Hello",
                model="chatgpt-4o-latest",
            )
        )

    mock_openai_client.chat.completions.create.assert_called_once()
    mock_openai_client.responses.create.assert_not_called()
    assert result.text == "GPT-4o response"


def test_model_config_has_correct_api_type():
    """Test that model configs have correct api_type field."""
    gpt5_nano_config = get_model_config("gpt-5-nano")
    assert gpt5_nano_config.api_type == "responses_api"
    assert gpt5_nano_config.model_name == "gpt-5-nano"

    o3_config = get_model_config("o3")
    # The lightweight o3 variant now routes through the Chat Completions API while
    # the larger o3-pro variant uses the Responses API. Reflect the current
    # registry values so the test documents the intended behaviour.
    assert o3_config.api_type == "chat_completion"

    gpt4o_config = get_model_config("gpt-4o")
    assert gpt4o_config.api_type == "chat_completion"


def test_responses_api_with_reasoning(mock_openai_client):
    """Test Responses API with reasoning enabled."""
    settings = {
        "text": {
            "model": "gpt-5-mini",
            "enable_reasoning": True,
        }
    }

    mock_response = MagicMock()
    mock_response.output = [
        MagicMock(type="text", text="Answer"),
        MagicMock(type="reasoning", content="My reasoning"),
    ]
    mock_openai_client.responses.create.return_value = mock_response

    with patch("core.providers.text.openai.ai_clients", {"openai_async": mock_openai_client}):
        provider = get_text_provider(settings)

        result = asyncio.run(
            provider.generate(
                prompt="Solve this problem",
                model="gpt-5-mini",
                enable_reasoning=True,
                reasoning_effort="high",
            )
        )

    call_kwargs = mock_openai_client.responses.create.call_args.kwargs
    assert "reasoning" in call_kwargs
    assert call_kwargs["reasoning"]["effort"] == "high"
    assert result.text == "Answer"
    assert result.reasoning == "My reasoning"
