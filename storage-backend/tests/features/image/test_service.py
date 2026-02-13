"""Tests for the image service."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.exceptions import ValidationError
from features.image.service import ImageService


def test_generate_image_propagates_validation_error() -> None:
    """ImageService should surface provider validation issues as ValidationError."""

    settings = {"image": {"model": "dalle-3"}}

    with patch("features.image.service.get_image_provider") as mock_get_provider:
        provider = AsyncMock()
        provider.generate.side_effect = ValidationError("Invalid prompt", field="image.prompt")
        mock_get_provider.return_value = provider

        service = ImageService()

        async def _run() -> None:
            await service.generate_image(
                prompt="Generate art",
                settings=settings,
                customer_id=1,
                save_to_s3=False,
            )

        with pytest.raises(ValidationError) as exc_info:
            asyncio.run(_run())

    assert "Invalid prompt" in str(exc_info.value)


def test_generate_image_applies_model_alias() -> None:
    """ImageService should resolve user friendly aliases before invoking provider."""

    settings = {"image": {"model": "openai mini", "width": 256, "height": 256}}

    with patch("features.image.service.get_image_provider") as mock_get_provider:
        provider = AsyncMock()
        provider.generate.return_value = b"pixels"
        mock_get_provider.return_value = provider

        service = ImageService()

        async def _run() -> None:
            await service.generate_image(
                prompt="Generate art",
                settings=settings,
                customer_id=1,
                save_to_s3=False,
            )

        asyncio.run(_run())

    provider.generate.assert_awaited_once()
    args = provider.generate.await_args.kwargs
    assert args["model"] == "gpt-image-1-mini"
