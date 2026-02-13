"""Unit tests for Gemini video request assembly."""

from __future__ import annotations

import pytest

from core.exceptions import ValidationError
from core.providers.video.utils.gemini import requests as request_utils


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _noop_prepare_image(_: object) -> None:
    return None


def _noop_resolve_reference_type(_: object) -> None:
    return None


@pytest.mark.anyio("asyncio")
async def test_build_generation_request_with_supported_options():
    generation_request = await request_utils.build_generation_request(
        duration_seconds=6,
        aspect_ratio="16:9",
        kwargs={
            "person_generation": "dont_allow",
            "enhance_prompt": False,
            "resolution": "1080p",
            "negative_prompt": "avoid text overlays",
        },
        number_of_videos=1,
        available_aspect_ratios={"16:9", "9:16"},
        available_person_generation={"dont_allow", "allow_adult"},
        available_resolutions={"720p", "1080p"},
        prepare_image=_noop_prepare_image,
        resolve_reference_type=_noop_resolve_reference_type,
        default_aspect_ratio="16:9",
    )

    config = generation_request.config
    assert generation_request.duration == 6
    assert generation_request.aspect_ratio == "16:9"
    assert config.aspect_ratio == "16:9"
    assert config.duration_seconds == 6
    assert config.number_of_videos == 1
    assert config.resolution == "1080p"
    assert config.negative_prompt == "avoid text overlays"
    # Unsupported options should remain unset when not provided.
    assert getattr(config, "fps", None) is None
    assert getattr(config, "compression_quality", None) is None


@pytest.mark.anyio("asyncio")
@pytest.mark.parametrize(
    "option, value",
    [
        ("fps", 24),
        ("generate_audio", True),
        ("compression_quality", "lossless"),
        ("mask", {"mask": "fake"}),
        ("output_gcs_uri", "gs://bucket/video.mp4"),
        ("seed", 1234),
        ("pubsub_topic", "projects/demo/topics/video"),
    ],
)
async def test_build_generation_request_rejects_unsupported_options(option: str, value: object):
    kwargs = {option: value, "person_generation": "allow_adult"}

    with pytest.raises(ValidationError) as exc:
        await request_utils.build_generation_request(
            duration_seconds=5,
            aspect_ratio="9:16",
            kwargs=kwargs,
            number_of_videos=1,
            available_aspect_ratios={"16:9", "9:16"},
            available_person_generation={"dont_allow", "allow_adult"},
            available_resolutions={"720p", "1080p"},
            prepare_image=_noop_prepare_image,
            resolve_reference_type=_noop_resolve_reference_type,
            default_aspect_ratio="9:16",
        )

    expected_messages = {
        "fps": "Frame rate (fps) configuration is not supported by the Gemini video API.",
        "generate_audio": "Audio track generation is not supported by the Gemini video API.",
        "compression_quality": "Compression quality selection is not supported by the Gemini video API.",
        "mask": "Video masks are not supported by the Gemini video API.",
        "output_gcs_uri": "Direct GCS output is not supported by the Gemini video API.",
        "seed": "Deterministic seeds are not supported by the Gemini video API.",
        "pubsub_topic": "Pub/Sub delivery is not supported by the Gemini video API.",
    }

    assert str(exc.value) == expected_messages[option]
