"""Unit tests for GeminiStreamingSpeechProvider."""

import asyncio
"""Unit tests for GeminiStreamingSpeechProvider."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.providers.audio.gemini_streaming import GeminiStreamingSpeechProvider
from core.streaming.manager import StreamingManager


class TestGeminiStreamingProviderInit:
    """Test provider initialization and configuration."""

    def test_default_initialization(self) -> None:
        """Provider initializes with sensible defaults."""

        provider = GeminiStreamingSpeechProvider()

        assert provider.name == "gemini-streaming"
        assert provider.streaming_capable is True
        assert provider.sample_rate == 16000
        assert provider.recording_sample_rate == 24000
        assert provider.buffer_duration_seconds == 3
        assert provider.channels == 1
        assert provider.language == "en"

    def test_configure_with_settings(self) -> None:
        """Provider applies custom settings correctly."""

        provider = GeminiStreamingSpeechProvider()

        settings = {
            "model": "gemini-2.5-pro",
            "language": "es",
            "sample_rate": 24000,
            "recording_sample_rate": 48000,
            "buffer_duration_seconds": 5.0,
            "optional_prompt": "Custom prompt",
        }

        provider.configure(settings)

        assert provider.model == "gemini-2.5-pro"
        assert provider.language == "es"
        assert provider.sample_rate == 24000
        assert provider.recording_sample_rate == 48000
        assert provider.buffer_duration_seconds == 5.0
        assert provider.optional_prompt == "Custom prompt"

    def test_model_normalization(self) -> None:
        """Provider normalizes model aliases."""

        provider = GeminiStreamingSpeechProvider()

        settings = {"model": "gemini-flash"}
        provider.configure(settings)

        assert provider.model == "gemini-2.5-flash"


class TestGeminiStreamingBuffering:
    """Test audio buffering logic."""

    @pytest.mark.anyio
    async def test_empty_audio_source(self) -> None:
        """Provider handles empty audio gracefully."""

        provider = GeminiStreamingSpeechProvider()
        manager = StreamingManager()

        async def empty_source():
            yield None  # Immediate completion

        result = await provider.transcribe_stream(
            audio_source=empty_source(),
            manager=manager,
            mode="non-realtime",
        )

        assert result == ""

    @pytest.mark.anyio
    async def test_small_chunks_accumulated(self) -> None:
        """Provider accumulates small chunks before transcription."""

        provider = GeminiStreamingSpeechProvider()
        manager = StreamingManager()

        with patch.object(
            provider, "_transcribe_buffer", new_callable=AsyncMock
        ) as mock_transcribe:
            mock_transcribe.return_value = "test result"

            async def chunk_source():
                chunk_size = 320  # 10ms at 16kHz mono, 16-bit
                for _ in range(10):
                    yield b"\x00" * chunk_size
                yield None

            await provider.transcribe_stream(
                audio_source=chunk_source(),
                manager=manager,
                mode="non-realtime",
            )

            assert mock_transcribe.call_count == 0


class TestGeminiStreamingWAVConversion:
    """Test PCM to WAV conversion."""

    @pytest.mark.anyio
    async def test_wav_conversion_produces_valid_format(self) -> None:
        """WAV conversion produces valid WAV headers."""

        provider = GeminiStreamingSpeechProvider()

        audio_bytes = b"\x00" * (16000 * 2)

        wav_data = await provider._convert_to_wav(audio_bytes)

        assert wav_data[:4] == b"RIFF"
        assert wav_data[8:12] == b"WAVE"
        assert len(wav_data) > len(audio_bytes)


class TestGeminiStreamingTranscription:
    """Test transcription workflow."""

    @pytest.mark.anyio
    async def test_transcribe_stream_with_mocked_api(self) -> None:
        """Provider calls Gemini API and streams results."""

        provider = GeminiStreamingSpeechProvider()
        manager = StreamingManager()
        output_queue: asyncio.Queue = asyncio.Queue()
        manager.add_queue(output_queue)

        with patch.object(
            provider, "_call_gemini_api", new_callable=AsyncMock
        ) as mock_api:
            mock_api.return_value = "transcribed text"

            async def audio_source():
                chunk_size = 16000 * 2
                yield b"\x00" * chunk_size
                yield None

            result = await provider.transcribe_stream(
                audio_source=audio_source(),
                manager=manager,
                mode="non-realtime",
            )

            assert result == "transcribed text"
            assert mock_api.call_count >= 1

            messages = []
            while not output_queue.empty():
                messages.append(await output_queue.get())

            transcription_messages = [
                message
                for message in messages
                if message.get("type") == "transcription"
            ]
            assert len(transcription_messages) > 0
            assert transcription_messages[0]["content"] == "transcribed text"


@pytest.mark.anyio
async def test_provider_raises_on_static_file_request() -> None:
    """Provider rejects static file transcription requests."""

    from core.exceptions import ProviderError
    from core.providers.audio.base import SpeechProviderRequest

    provider = GeminiStreamingSpeechProvider()

    request = SpeechProviderRequest(file_path="/tmp/test.wav")

    with pytest.raises(ProviderError, match="streaming transcription only"):
        await provider.transcribe_file(request)

