"""Tests for audio_direct Gemini integration."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from core.streaming.manager import StreamingManager
from features.chat.service import ChatService
from features.chat.utils.websocket_workflows import (
    _convert_pcm_to_wav,
    _extract_text_from_prompt,
    _process_audio_with_gemini,
)


pytestmark = pytest.mark.anyio("asyncio")


class TestWAVConversion:
    """Test PCM to WAV conversion."""

    @pytest.mark.asyncio
    async def test_wav_conversion_adds_headers(self) -> None:
        """WAV conversion adds proper WAV headers."""

        # 1 second of silence at 16kHz (2 bytes per sample)
        pcm_data = b"\x00" * (16000 * 2)

        wav_data = await _convert_pcm_to_wav(
            pcm_data,
            sample_rate=16000,
            channels=1,
        )

        assert wav_data[:4] == b"RIFF"
        assert wav_data[8:12] == b"WAVE"
        assert len(wav_data) > len(pcm_data)


class TestPromptExtraction:
    """Test text extraction from prompt structures."""

    def test_extract_from_list(self) -> None:
        """Extracts text from list of prompt items."""

        prompt = [
            {"type": "text", "text": "Hello world"},
            {"type": "image_url", "url": "http://example.com/image.jpg"},
        ]

        assert _extract_text_from_prompt(prompt) == "Hello world"

    def test_extract_from_string(self) -> None:
        """Handles direct string prompts."""

        prompt = "Direct string prompt"

        assert _extract_text_from_prompt(prompt) == "Direct string prompt"

    def test_extract_from_empty(self) -> None:
        """Returns empty string for empty prompt."""

        assert _extract_text_from_prompt(None) == ""
        assert _extract_text_from_prompt([]) == ""


class TestGeminiMultimodalIntegration:
    """Test Gemini multimodal API integration."""

    @pytest.mark.asyncio
    async def test_process_audio_with_mocked_gemini(self) -> None:
        """Process audio workflow with mocked Gemini API."""

        manager = StreamingManager()
        output_queue: asyncio.Queue = asyncio.Queue()
        manager.add_queue(output_queue)

        mock_service = MagicMock(spec=ChatService)

        audio_buffer = bytearray(b"\x00" * (16000 * 2))
        prompt = [{"type": "text", "text": "Analyze this audio"}]
        settings = {
            "speech": {"recording_sample_rate": 16000},
            "text": {"stream": False},
            "tts": {"tts_auto_execute": False},
        }

        with patch("core.utils.env.is_production", return_value=False), patch(
            "core.clients.ai.get_gemini_client"
        ) as mock_client_factory:
            mock_client = MagicMock()
            mock_models = MagicMock()
            mock_models.generate_content.return_value = type(
                "Response", (), {"text": "This is a test audio response"}
            )()
            mock_client.models = mock_models
            mock_client_factory.return_value = mock_client

            result = await _process_audio_with_gemini(
                audio_buffer=audio_buffer,
                prompt=prompt,
                settings=settings,
                customer_id=1,
                manager=manager,
                service=mock_service,
                timings={},
                user_input={},
            )

        assert result["success"] is True
        assert result["text_response"] == "This is a test audio response"
        assert result["ai_response"] == "This is a test audio response"
        assert result["model"] == "gemini-2.5-flash"

        # Verify Gemini client called once
        mock_models.generate_content.assert_called_once()

        # Verify messages streamed to frontend
        messages = []
        while not output_queue.empty():
            messages.append(await output_queue.get())

        message_types = [m.get("type") for m in messages if isinstance(m, dict)]
        assert "custom_event" in message_types
        assert "text_chunk" in message_types
        assert "text_completed" in message_types
        assert "tts_not_requested" in message_types

    @pytest.mark.asyncio
    async def test_process_audio_with_streaming_enabled(self) -> None:
        """Process audio with streaming enabled."""

        manager = StreamingManager()
        output_queue: asyncio.Queue = asyncio.Queue()
        manager.add_queue(output_queue)

        mock_service = MagicMock(spec=ChatService)

        audio_buffer = bytearray(b"\x00" * (16000 * 2))
        settings = {
            "speech": {"recording_sample_rate": 16000},
            "text": {"stream": True},
            "tts": {"tts_auto_execute": False},
        }

        with patch("core.utils.env.is_production", return_value=False), patch(
            "core.clients.ai.get_gemini_client"
        ) as mock_client_factory:
            mock_client = MagicMock()
            mock_models = MagicMock()

            class MockChunk:
                def __init__(self, text: str) -> None:
                    self.text = text

            mock_models.generate_content_stream.return_value = iter(
                [MockChunk("Chunk 1 "), MockChunk("Chunk 2")]
            )
            mock_client.models = mock_models
            mock_client_factory.return_value = mock_client

            result = await _process_audio_with_gemini(
                audio_buffer=audio_buffer,
                prompt=[{"type": "text", "text": "Test"}],
                settings=settings,
                customer_id=1,
                manager=manager,
                service=mock_service,
                timings={},
                user_input={},
            )

        assert result["success"] is True
        assert result["text_response"] == "Chunk 1 Chunk 2"

        messages = []
        while not output_queue.empty():
            messages.append(await output_queue.get())

        text_messages = [m for m in messages if isinstance(m, dict) and m.get("type") == "text_chunk"]
        assert len(text_messages) == 2

    @pytest.mark.asyncio
    async def test_error_handling_in_gemini_call(self) -> None:
        """Error in Gemini API call is handled gracefully."""

        manager = StreamingManager()
        output_queue: asyncio.Queue = asyncio.Queue()
        manager.add_queue(output_queue)

        mock_service = MagicMock(spec=ChatService)

        audio_buffer = bytearray(b"\x00" * 1000)

        with patch("core.utils.env.is_production", return_value=False), patch(
            "core.clients.ai.get_gemini_client"
        ) as mock_client_factory:
            mock_client = MagicMock()
            mock_models = MagicMock()
            mock_models.generate_content.side_effect = Exception("API Error")
            mock_models.generate_content_stream.side_effect = Exception("API Error")
            mock_client.models = mock_models
            mock_client_factory.return_value = mock_client

            result = await _process_audio_with_gemini(
                audio_buffer=audio_buffer,
                prompt=[],
                settings={"speech": {}, "text": {"stream": True}, "tts": {}},
                customer_id=1,
                manager=manager,
                service=mock_service,
                timings={},
                user_input={},
            )

        assert result["success"] is False
        assert "error" in result

        messages = []
        while not output_queue.empty():
            messages.append(await output_queue.get())

        error_messages = [m for m in messages if isinstance(m, dict) and m.get("type") == "error"]
        assert len(error_messages) > 0
