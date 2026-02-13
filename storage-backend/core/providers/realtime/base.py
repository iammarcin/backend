"""Base interfaces and shared dataclasses for realtime providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import AsyncIterator, Mapping, MutableMapping


class TurnStatus(str, Enum):
    """Common turn lifecycle states surfaced by realtime providers."""

    IDLE = "idle"
    RECEIVING_INPUT = "receiving_input"
    PROCESSING = "processing"
    STREAMING = "streaming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERRORED = "errored"


class RealtimeEventType(str, Enum):
    """Event categories emitted by realtime providers."""

    SESSION = "session"
    MESSAGE = "message"
    AUDIO_CHUNK = "audio_chunk"
    CONTROL = "control"
    ERROR = "error"


@dataclass(slots=True)
class RealtimeEvent:
    """Normalised provider event returned through the realtime stream."""

    type: RealtimeEventType
    payload: Mapping[str, object]
    metadata: MutableMapping[str, object] | None = None

    def to_payload(self) -> dict[str, object]:
        """Serialise the event into a JSON-compatible payload."""

        data: dict[str, object] = {"type": self.type.value, "payload": dict(self.payload)}
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data


class BaseRealtimeProvider(ABC):
    """Abstract base class implemented by realtime provider integrations."""

    name: str = "realtime"

    async def __aenter__(self) -> "BaseRealtimeProvider":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - defensive
        await self.close_session()

    @abstractmethod
    async def open_session(self, *, settings: Mapping[str, object]) -> None:
        """Initialise any provider specific session resources."""

    @abstractmethod
    async def close_session(self) -> None:
        """Gracefully shut down the provider session."""

    @abstractmethod
    async def send_user_event(self, payload: Mapping[str, object]) -> None:
        """Forward a user event (text/audio) to the provider session."""

    @abstractmethod
    async def receive_events(self) -> AsyncIterator[RealtimeEvent]:
        """Yield realtime events produced by the provider."""

    async def set_input_audio_queue(self, queue: asyncio.Queue[bytes | None]) -> None:
        """Provide an input audio queue for streaming client audio chunks."""

        # Default implementation stores the queue reference for providers that do
        # not stream audio input. Concrete providers that support duplex audio
        # should override this to integrate with their transport implementation.
        self._input_audio_queue = queue

    async def cancel_turn(self) -> None:  # pragma: no cover - optional override
        """Request cancellation of the active provider turn when supported."""


__all__ = [
    "BaseRealtimeProvider",
    "RealtimeEvent",
    "RealtimeEventType",
    "TurnStatus",
]
