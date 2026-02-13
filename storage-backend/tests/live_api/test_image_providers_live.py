"""Live API tests for image generation providers.

These tests hit real APIs to verify image generation works end-to-end.
Run with: RUN_MANUAL_TESTS=1 pytest tests/live_api/test_image_providers_live.py -v -s

Uses lowest quality/cheapest models to minimize costs:
- OpenAI: gpt-image-1-mini (smallest, cheapest)
- Gemini: gemini-2.5-flash-image (fast, cheap)
- Flux: flux-dev (cheapest flux option)
"""

from __future__ import annotations

import os

import httpx
import pytest

from core.exceptions import ProviderError
from tests.utils.live_providers import (
    require_live_client,
    skip_if_transient_provider_error,
)

pytestmark = pytest.mark.live_api


# Smallest dimensions to minimize cost/time
# Note: OpenAI gpt-image only supports 1024x1024, 1024x1536, 1536x1024
TEST_WIDTH = 512
TEST_HEIGHT = 512
TEST_WIDTH_OPENAI = 1024  # OpenAI minimum
TEST_HEIGHT_OPENAI = 1024
TEST_PROMPT = "A simple red circle on white background"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# =============================================================================
# OpenAI Image Provider Tests
# =============================================================================


@pytest.mark.anyio
async def test_openai_image_generation_mini():
    """Test OpenAI image generation with cheapest model (gpt-image-1-mini)."""
    require_live_client("openai", "OPENAI_API_KEY")

    from core.providers.image.openai import OpenAIImageProvider

    provider = OpenAIImageProvider()

    try:
        result = await provider.generate(
            prompt=TEST_PROMPT,
            model="gpt-image-1-mini",
            width=TEST_WIDTH_OPENAI,  # OpenAI requires 1024+
            height=TEST_HEIGHT_OPENAI,
            quality="low",
        )
    except ProviderError as exc:
        skip_if_transient_provider_error(exc, "OpenAI")
        raise

    assert isinstance(result, bytes)
    assert len(result) > 1000, "Image should be more than 1KB"
    # PNG magic bytes or JPEG
    assert result[:4] == b"\x89PNG" or result[:2] == b"\xff\xd8", "Should be PNG or JPEG"


# =============================================================================
# Gemini Image Provider Tests
# =============================================================================


@pytest.mark.anyio
async def test_gemini_flash_image_generation():
    """Test Gemini Flash image generation (nano-banana)."""
    require_live_client("gemini", "GOOGLE_API_KEY")

    from core.providers.image.gemini import GeminiImageProvider

    provider = GeminiImageProvider()

    try:
        result = await provider.generate(
            prompt=TEST_PROMPT,
            model="gemini-2.5-flash-image",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
        )
    except ProviderError as exc:
        skip_if_transient_provider_error(exc, "Gemini")
        raise

    assert isinstance(result, bytes)
    assert len(result) > 1000, "Image should be more than 1KB"


# =============================================================================
# Flux Image Provider Tests
# =============================================================================


@pytest.mark.anyio
async def test_flux_dev_image_generation():
    """Test Flux image generation with cheapest model (flux-dev)."""
    require_live_client("flux", "FLUX_API_KEY")

    from core.providers.image.flux import FluxImageProvider

    try:
        provider = FluxImageProvider()
    except ProviderError as exc:
        pytest.skip(f"Flux provider not available: {exc}")

    try:
        result = await provider.generate(
            prompt=TEST_PROMPT,
            model="flux-dev",
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
        )
    except httpx.ConnectError as exc:
        pytest.skip(f"Flux API connection error (transient): {exc}")
    except ProviderError as exc:
        # Flux queue can timeout during high load - treat as transient
        if "timed out" in str(exc).lower():
            pytest.skip(f"Flux queue timed out (transient): {exc}")
        skip_if_transient_provider_error(exc, "Flux")
        raise

    assert isinstance(result, bytes)
    assert len(result) > 1000, "Image should be more than 1KB"


# =============================================================================
# Cross-Provider Smoke Test
# =============================================================================


@pytest.mark.anyio
async def test_image_service_with_settings():
    """Test ImageService with settings dict (integration smoke test)."""
    require_live_client("gemini", "GOOGLE_API_KEY")

    from features.image.service import ImageService

    service = ImageService()

    settings = {
        "image": {
            "model": "nano-banana",  # Cheapest Gemini
            "width": TEST_WIDTH,
            "height": TEST_HEIGHT,
            "quality": "low",
        }
    }

    try:
        s3_url, image_bytes, metadata = await service.generate_image(
            prompt=TEST_PROMPT,
            settings=settings,
            customer_id=1,
            save_to_s3=False,  # Don't upload in tests
        )
    except ProviderError as exc:
        skip_if_transient_provider_error(exc, "ImageService")
        raise

    assert s3_url is None  # save_to_s3=False
    assert isinstance(image_bytes, bytes)
    assert len(image_bytes) > 1000
    assert metadata["provider"] == "gemini"
    assert metadata["model"] == "gemini-2.5-flash-image"
