"""Tests for audio_direct workflow setup."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.streaming.manager import StreamingManager
from features.chat.service import ChatService
from features.chat.utils.websocket_workflows import (
    _update_user_message,
    handle_audio_direct_workflow,
)


pytestmark = pytest.mark.anyio("asyncio")


class TestAudioDirectWorkflowSetup:
    """Test audio_direct workflow infrastructure."""

    @pytest.mark.asyncio
    async def test_placeholder_message_sent_to_frontend(self):
        """Workflow sends placeholder transcription message."""

        manager = StreamingManager()
        output_queue: asyncio.Queue = asyncio.Queue()
        manager.add_queue(output_queue)

        mock_websocket = AsyncMock()
        mock_service = MagicMock(spec=ChatService)

        mock_websocket.receive.side_effect = [
            {
                "type": "websocket.receive",
                "text": '{"type": "RecordingFinished"}',
            }
        ]

        await handle_audio_direct_workflow(
            websocket=mock_websocket,
            prompt=[],
            settings={},
            customer_id=1,
            manager=manager,
            service=mock_service,
            timings={},
            user_input={},
        )

        messages = []
        while not output_queue.empty():
            messages.append(await output_queue.get())

        transcription_messages = [
            message
            for message in messages
            if message.get("type") == "transcription"
        ]

        assert transcription_messages
        assert "🎤" in transcription_messages[0]["content"]
        assert "multimodal" in transcription_messages[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_audio_collection_from_websocket(self, monkeypatch):
        """Workflow collects audio chunks from WebSocket."""

        manager = StreamingManager()
        mock_websocket = AsyncMock()
        mock_service = MagicMock(spec=ChatService)

        audio_chunk_1 = b"\x00" * 1000
        audio_chunk_2 = b"\x00" * 1000

        mock_websocket.receive.side_effect = [
            {"type": "websocket.receive", "bytes": audio_chunk_1},
            {"type": "websocket.receive", "bytes": audio_chunk_2},
            {
                "type": "websocket.receive",
                "text": '{"type": "RecordingFinished"}',
            },
        ]

        # Mock the Gemini call to avoid hitting real API
        async def mock_gemini_call(**kwargs):
            return {"collected_text": "Test response", "model": "gemini-mock"}

        monkeypatch.setattr(
            "features.chat.utils.websocket_workflows.gemini._call_gemini_multimodal_and_stream",
            mock_gemini_call,
        )

        result = await handle_audio_direct_workflow(
            websocket=mock_websocket,
            prompt=[],
            settings={},
            customer_id=1,
            manager=manager,
            service=mock_service,
            timings={},
            user_input={},
        )

        assert result["success"] is True
        assert result["audio_size"] == 2000

    @pytest.mark.asyncio
    async def test_empty_audio_returns_error(self):
        """Workflow handles empty audio gracefully."""

        manager = StreamingManager()
        output_queue: asyncio.Queue = asyncio.Queue()
        manager.add_queue(output_queue)

        mock_websocket = AsyncMock()
        mock_service = MagicMock(spec=ChatService)

        mock_websocket.receive.side_effect = [
            {
                "type": "websocket.receive",
                "text": '{"type": "RecordingFinished"}',
            }
        ]

        result = await handle_audio_direct_workflow(
            websocket=mock_websocket,
            prompt=[],
            settings={},
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

        error_messages = [
            message for message in messages if message.get("type") == "error"
        ]
        assert error_messages


class TestUserMessageUpdate:
    """Test user message updating helper."""

    def test_adds_text_to_empty_prompt(self):
        """Helper adds text to empty prompt array."""

        user_input = {"prompt": []}

        result = _update_user_message(user_input, "Test message")

        assert len(result["prompt"]) == 1
        assert result["prompt"][0]["type"] == "text"
        assert result["prompt"][0]["text"] == "Test message"

    def test_updates_existing_text_prompt(self):
        """Helper updates existing text prompt."""

        user_input = {
            "prompt": [
                {"type": "text", "text": "Old message"},
                {"type": "image_url", "url": "http://example.com/image.jpg"},
            ]
        }

        result = _update_user_message(user_input, "New message")

        text_prompts = [
            prompt for prompt in result["prompt"] if prompt["type"] == "text"
        ]
        assert len(text_prompts) == 1
        assert text_prompts[0]["text"] == "New message"

        image_prompts = [
            prompt for prompt in result["prompt"] if prompt["type"] == "image_url"
        ]
        assert len(image_prompts) == 1


class TestRequestTypeDetection:
    """Test audio_direct mode detection."""

    def test_send_full_audio_triggers_audio_direct(self):
        """send_full_audio_to_llm setting triggers audio_direct mode."""

        from features.chat.utils.websocket_request import normalise_request_type

        data = {
            "request_type": "audio",
            "user_settings": {"speech": {"send_full_audio_to_llm": True}},
        }

        request_type = normalise_request_type(data)

        assert request_type == "audio_direct"

    def test_normal_audio_without_flag(self):
        """Normal audio request without flag stays as 'audio'."""

        from features.chat.utils.websocket_request import normalise_request_type

        data = {
            "request_type": "audio",
            "user_settings": {"speech": {"model": "gemini-pro"}},
        }

        request_type = normalise_request_type(data)

        assert request_type == "audio"
