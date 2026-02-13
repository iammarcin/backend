from unittest.mock import AsyncMock, MagicMock

import pytest

from features.chat.service import ChatService
from features.chat.utils.websocket_workflows.audio import handle_audio_workflow
from features.audio.service import STTService


@pytest.mark.asyncio
async def test_handle_audio_workflow_empty_transcript():
    """Empty transcripts return a user-friendly error and skip LLM processing."""

    mock_websocket = AsyncMock()

    mock_service = MagicMock(spec=ChatService)
    mock_service.stream_response = AsyncMock()

    mock_stt_service = MagicMock(spec=STTService)
    mock_stt_service.configure = MagicMock()
    mock_stt_service.websocket_audio_source = MagicMock(return_value=AsyncMock())
    mock_stt_service.transcribe_stream = AsyncMock(return_value="")

    mock_manager = MagicMock()
    mock_manager.send_to_queues = AsyncMock()
    mock_manager.signal_completion = AsyncMock()

    result = await handle_audio_workflow(
        websocket=mock_websocket,
        prompt=[],
        settings={},
        customer_id=42,
        manager=mock_manager,
        service=mock_service,
        stt_service=mock_stt_service,
        timings={},
        completion_token=None,
        user_input=None,
    )

    assert result["success"] is False
    assert result["error"] == "empty_transcript"
    assert result["user_transcript"] == ""

    mock_manager.send_to_queues.assert_awaited_once_with(
        {
            "type": "error",
            "content": "No speech detected in recording. Please try again.",
            "stage": "transcription",
        }
    )
    mock_service.stream_response.assert_not_awaited()
    mock_manager.signal_completion.assert_not_awaited()
