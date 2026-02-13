import time

import pytest
from starlette.testclient import TestClient

@pytest.mark.requires_concurrent_loop
@pytest.mark.e2e_websocket
class TestAudioWebSocketRaceCondition:
    """
    Tests for audio WebSocket race condition introduced by concurrent
    message loop in cancellation implementation.
    """

    def test_audio_recording_with_concurrent_message_loop(
        self,
        authenticated_client: TestClient,
        auth_token: str,
        monkeypatch: pytest.MonkeyPatch
    ):
        """
        Reproduces the audio WebSocket race condition.

        Scenario:
        1. Client connects via WebSocket
        2. Client sends audio workflow message
        3. Backend starts concurrent message loop (cancellation infrastructure)
        4. Client starts sending audio chunks
        5. Main loop and audio source both try websocket.receive()
        6. RuntimeError: cannot call recv while another coroutine is already waiting

        Expected: Test FAILS with RuntimeError (reproduces bug)
        """
        from features.audio.service import STTService
        from features.chat.service import ChatService

        consumed_chunks: list[bytes] = []

        async def mock_transcribe_stream(self, *, audio_source, **kwargs):
            async for chunk in audio_source:
                if not chunk:
                    break
                consumed_chunks.append(chunk)
            return "Mock transcription"

        async def mock_stream_response(
            self,
            *,
            prompt,
            settings,
            customer_id,
            manager,
            **kwargs,
        ):
            await manager.send_to_queues(
                {
                    "type": "custom_event",
                    "content": {"type": "transcription", "message": "transcriptionCompleted"},
                }
            )
            return {"success": True, "content": "ok"}

        monkeypatch.setattr(STTService, "transcribe_stream", mock_transcribe_stream)
        monkeypatch.setattr(ChatService, "stream_response", mock_stream_response)

        with authenticated_client.websocket_connect(f"/chat/ws?token={auth_token}") as websocket:
            # Receive websocket_ready from switchboard
            ready1 = websocket.receive_json()
            assert ready1["type"] == "websocket_ready"

            # Send audio workflow message (canonical snake_case format)
            audio_message = {
                "request_type": "audio",
                "user_input": {
                    "prompt": [{"type": "text", "text": ""}],
                    "audio": {
                        "codec": "pcm16",
                        "sample_rate": 16000,
                        "channels": 1
                    }
                },
                "user_settings": {
                    "general": {
                        "ai_text_model_override": "claude-mini",
                        "temperature": 0.3
                    },
                    "audio": {
                        "transcription_engine": "deepgram",
                        "model": "nova-3",
                        "language": "en"
                    }
                }
            }

            websocket.send_json(audio_message)

            # Receive websocket_ready from websocket_chat_endpoint
            ready2 = websocket.receive_json()
            assert ready2["type"] == "websocket_ready"

            # Wait for working event
            working = websocket.receive_json()
            assert working["type"] == "working"

            # Now send audio chunks
            # The backend's audio source will try to websocket.receive()
            # The main loop is also trying to websocket.receive() for cancel messages
            # This should trigger RuntimeError

            audio_chunk_1 = b'\x00\x01' * 1000  # 2000 bytes of PCM16
            audio_chunk_2 = b'\x00\x02' * 1000

            # Send first chunk
            websocket.send_bytes(audio_chunk_1)

            # Send second chunk
            websocket.send_bytes(audio_chunk_2)

            # Send empty chunk to signal end
            websocket.send_bytes(b'')

            websocket.close(code=1000)

            # Allow the ASGI thread to flush events so mocks capture chunk usage.
            time.sleep(0.05)

        assert consumed_chunks, "Audio chunks never reached the STT service (race condition still present)"

    @pytest.mark.anyio
    async def test_audio_recording_without_concurrent_loop(
        self,
    ):
        """
        Control test: Audio source works fine when called directly
        without concurrent message loop.

        This test should PASS before and after the fix.
        """
        from features.audio.audio_sources import websocket_audio_source
        from unittest.mock import AsyncMock

        # Create mock WebSocket that simulates sequential reads
        mock_websocket = AsyncMock()

        # Simulate audio chunks
        audio_chunks = [
            {"type": "websocket.receive", "bytes": b'\x00\x01' * 1000},
            {"type": "websocket.receive", "bytes": b'\x00\x02' * 1000},
            {"type": "websocket.receive", "bytes": b''},  # End signal
        ]

        mock_websocket.receive = AsyncMock(side_effect=audio_chunks)

        # Call audio source (no concurrent loop)
        chunks_received = []
        async for chunk in websocket_audio_source(
            websocket=mock_websocket
        ):
            if not chunk:
                break
            chunks_received.append(chunk)

        # Should receive 2 chunks (third is empty = end signal)
        assert len(chunks_received) == 2
        assert chunks_received[0] == b'\x00\x01' * 1000
        assert chunks_received[1] == b'\x00\x02' * 1000

    async def test_audio_recording_cancelled_mid_stream(
        self,
        authenticated_client: TestClient,
        auth_token: str,
        monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that audio can be cancelled mid-stream without race conditions.

        This test will FAIL initially but is important for validating the fix.
        """
        # Similar setup to Test 1
        # But send cancel message while audio chunks are streaming
        # Should cancel gracefully without RuntimeError
        pytest.skip("Pending milestone scope (cancellation coverage to be implemented).")

    async def test_multiple_concurrent_audio_sessions(
        self,
        authenticated_client: TestClient,
        auth_token: str,
        monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that multiple WebSocket connections can do audio simultaneously.

        Ensures fix doesn't introduce issues with multiple connections.
        """
        # Open multiple WebSocket connections
        # Each sends audio workflow
        # Verify no race conditions across connections
        pytest.skip("Pending milestone scope (multi-session coverage to be implemented).")
