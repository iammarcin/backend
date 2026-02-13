"""Tests for Pydantic request models."""

import pytest
from pydantic import ValidationError

from core.pydantic_schemas import ChatRequest, ImageGenerationRequest, WebSocketMessage


def test_chat_request_trims_prompt():
    """ChatRequest should trim whitespace from prompt."""

    request = ChatRequest(prompt="  hello  ", settings={}, customer_id=1)
    assert request.prompt == "hello"


def test_chat_request_empty_prompt():
    """Empty prompt should raise a validation error."""

    with pytest.raises(ValidationError):
        ChatRequest(prompt="   ", settings={}, customer_id=1)


def test_image_generation_request_defaults():
    """ImageGenerationRequest should set sensible defaults."""

    request = ImageGenerationRequest(prompt="draw", customer_id=2)
    assert request.save_to_db is True
    assert request.settings == {}


def test_websocket_message_defaults():
    """WebSocketMessage should default settings to dict."""

    message = WebSocketMessage(type="chat")
    assert message.settings == {}
    assert message.customer_id is None
