"""Tests for response models."""

from core.pydantic_schemas import APIResponse, ChatResponse, ImageGenerationResponse


def test_api_response_defaults():
    response = APIResponse(success=True)
    assert response.data is None
    assert response.error is None
    assert response.code == 200


def test_chat_response_fields():
    response = ChatResponse(text="hi", model="gpt-4o", provider="openai", reasoning="", citations=None)
    assert response.text == "hi"
    assert response.provider == "openai"


def test_image_generation_response():
    response = ImageGenerationResponse(image_url="https://example", provider="openai", model="dall-e", settings={})
    assert response.image_url.startswith("https://")
