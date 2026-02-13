"""Integration checks for the OpenAI streaming provider."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, AsyncIterator

import pytest

from core.providers.audio.factory import get_audio_provider
from core.providers.audio.utils.session import build_session_config
from core.streaming.manager import StreamingManager

requires_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not configured",
)

requires_manual = pytest.mark.skipif(
    os.getenv("RUN_MANUAL_TESTS") != "1",
    reason="Set RUN_MANUAL_TESTS=1 to run live API tests",
)


async def load_test_audio(filepath: str) -> AsyncIterator[bytes | None]:
    """Yield audio frames from the fixtures directory."""

    import wave

    fixtures_root = Path(__file__).parent / "fixtures"
    audio_path = fixtures_root / filepath

    if not audio_path.exists():
        pytest.skip(f"Test audio file not found: {audio_path}")

    with wave.open(str(audio_path), "rb") as wav_file:
        chunk_size = 4096
        while True:
            data = wav_file.readframes(chunk_size)
            if not data:
                break
            yield data
    yield None


def test_session_config_format() -> None:
    """Session config uses the unified OpenAI Realtime format."""

    config = build_session_config(
        model="gpt-4o-transcribe",
        session_model="gpt-realtime",
        transcription_model="gpt-4o-transcribe",
        language="en",
        prompt="Meeting transcription",
        enable_vad=True,
        vad_threshold=0.5,
        vad_prefix_padding_ms=300,
        vad_silence_duration_ms=500,
    )

    assert config["type"] == "session.update"
    assert "session" in config

    session = config["session"]
    assert session["type"] == "realtime"
    assert session["model"] == "gpt-realtime"

    audio_input = session["audio"]["input"]
    audio_format = audio_input["format"]
    assert audio_format["type"] == "audio/pcm"
    assert audio_format["rate"] == 24000

    transcription = audio_input["transcription"]
    assert transcription["model"] == "gpt-4o-transcribe"
    assert transcription["language"] == "en"
    assert transcription["prompt"] == "Meeting transcription"

    turn_detection = audio_input["turn_detection"]
    assert turn_detection["type"] == "server_vad"
    assert turn_detection["threshold"] == 0.5
    assert turn_detection["prefix_padding_ms"] == 300
    assert turn_detection["silence_duration_ms"] == 500


def test_session_config_without_vad() -> None:
    """VAD settings are null when disabled."""

    config = build_session_config(
        model="gpt-4o-mini-transcribe",
        session_model="gpt-realtime",
        transcription_model="gpt-4o-mini-transcribe",
        language="es",
        enable_vad=False,
    )

    turn_detection = config["session"]["audio"]["input"]["turn_detection"]
    assert turn_detection is None


def test_session_config_without_prompt() -> None:
    """Prompt is omitted when not provided."""

    config = build_session_config(
        model="whisper-1",
        session_model="gpt-realtime",
        transcription_model="whisper-1",
        language="fr",
        prompt=None,
    )

    transcription = config["session"]["audio"]["input"]["transcription"]
    assert "prompt" not in transcription


@pytest.mark.anyio
async def test_factory_resolves_openai_streaming_for_models() -> None:
    """Model hint routes to the streaming provider."""

    settings = {"audio": {"model": "gpt-4o-mini-transcribe"}}

    provider = get_audio_provider(settings, action="stream")

    assert provider.name == "openai-streaming"
    assert provider.streaming_capable is True


@pytest.mark.anyio
async def test_factory_resolves_explicit_openai_provider() -> None:
    """Explicit provider selection honours streaming override."""

    settings = {
        "audio": {
            "provider": "openai",
            "model": "gpt-4o-transcribe",
        }
    }

    provider = get_audio_provider(settings, action="stream")

    assert provider.name == "openai-streaming"

