"""Utilities for creating and managing per-request streaming runtime state.

The runtime object keeps the streaming manager, asyncio tasks, and queues that
bridge the backend workflow with the frontend WebSocket connection. Audio
workflows additionally require a queue for binary/audio messages so the main
WebSocket loop can remain the sole reader from the socket without competing
``receive()`` calls. This module centralises the queue lifecycle so both the
producer (websocket loop) and consumer (audio workflow) coordinate safely.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, List, Optional

from fastapi import WebSocket

from core.streaming.manager import StreamingManager

from .websocket_streaming import send_to_frontend


@dataclass
class WorkflowRuntime:
    """Runtime resources required while processing a single workflow request."""

    manager: StreamingManager
    tasks: List[asyncio.Task]
    frontend_queue: asyncio.Queue[Any]
    _cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    _audio_queue: Optional[asyncio.Queue[Any]] = field(default=None, init=False, repr=False)
    _final_attachments: Optional[List[Any]] = field(default=None, init=False, repr=False)
    _recording_id: Optional[str] = field(default=None, init=False, repr=False)
    _additional_text: Optional[str] = field(default=None, init=False, repr=False)
    _allow_disconnect: bool = field(default=False, init=False, repr=False)

    def cancel(self) -> None:
        """Signal that this workflow should stop processing."""
        if not self._cancelled.is_set():
            self._cancelled.set()

    def is_cancelled(self) -> bool:
        """Return True if cancellation has been requested."""
        return self._cancelled.is_set()

    def allow_disconnect(self) -> None:
        """Allow the workflow to finish even if the websocket disconnects."""
        self._allow_disconnect = True

    def should_cancel_on_disconnect(self) -> bool:
        """Return True if disconnects should cancel this workflow."""
        return not self._allow_disconnect

    async def wait_for_cancellation(self) -> None:
        """Block until cancellation is requested. Useful for tests."""
        await self._cancelled.wait()

    def create_audio_queue(self, *, maxsize: int = 0) -> asyncio.Queue[Any]:
        """Initialise the audio queue used to forward websocket frames."""

        if self._audio_queue is not None:
            raise RuntimeError("Audio queue already initialised for this runtime")

        self._audio_queue = asyncio.Queue(maxsize=maxsize)
        return self._audio_queue

    def get_audio_queue(self) -> Optional[asyncio.Queue[Any]]:
        """Return the audio queue if present."""

        return self._audio_queue

    async def enqueue_audio_message(self, message: Any) -> None:
        """Push a websocket frame onto the audio queue."""

        if self._audio_queue is None:
            raise RuntimeError("Audio queue not initialised")

        await self._audio_queue.put(message)

    def close_audio_queue(self) -> None:
        """Signal the audio queue that no more messages will arrive."""

        if self._audio_queue is None:
            return

        queue = self._audio_queue
        self._audio_queue = None
        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:
            # Consumer will drain current payloads and see None afterwards.
            pass

    def set_final_attachments(self, attachments: List[Any]) -> None:
        """Store final attachments received with RecordingFinished message.

        When a user adds attachments DURING audio recording, those are included
        in the RecordingFinished message and stored here for merging into the
        user_input prompt before SQS dispatch.
        """
        self._final_attachments = attachments

    def get_final_attachments(self) -> Optional[List[Any]]:
        """Return final attachments if set, else None."""
        return self._final_attachments

    def set_recording_id(self, recording_id: str) -> None:
        """Store recording_id from RecordingFinished for ACK correlation."""
        self._recording_id = recording_id

    def get_recording_id(self) -> Optional[str]:
        """Return recording_id if set, else None."""
        return self._recording_id

    def set_additional_text(self, text: str) -> None:
        """Store additional_text typed during voice recording."""
        self._additional_text = text

    def get_additional_text(self) -> Optional[str]:
        """Return additional_text if set, else None."""
        return self._additional_text


async def create_workflow_runtime(
    *, session_id: str, websocket: WebSocket
) -> WorkflowRuntime:
    """Prepare streaming infrastructure for a workflow execution."""

    manager = StreamingManager()
    frontend_queue: asyncio.Queue[Any] = asyncio.Queue()
    manager.add_queue(frontend_queue)
    frontend_task = asyncio.create_task(
        send_to_frontend(frontend_queue, websocket, session_id=session_id)
    )
    return WorkflowRuntime(manager=manager, tasks=[frontend_task], frontend_queue=frontend_queue)
