"""Event translation utilities for the Google Gemini Live realtime provider.

The realtime API emits nested payloads that must be converted into
internal :class:`RealtimeEvent` representation.  To keep the
provider implementation focused on transport concerns, this module exposes
``GoogleEventTranslator`` which encapsulates the translation logic and the
state required to track response identifiers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping

from ..base import RealtimeEvent, RealtimeEventType


class GoogleEventTranslator:
    """Translate Gemini Live websocket payloads into ``RealtimeEvent`` objects."""

    def __init__(self) -> None:
        self._current_response_id: str | None = None
        self._turn_index = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def translate(self, event: Mapping[str, object]) -> list[RealtimeEvent]:
        """Convert a raw websocket payload into one or more ``RealtimeEvent`` objects."""

        events: list[RealtimeEvent] = []

        setup_complete = event.get("setupComplete")
        if setup_complete:
            events.append(
                RealtimeEvent(
                    RealtimeEventType.SESSION,
                    {"event": "setup.complete", "payload": setup_complete},
                )
            )

        client_content = event.get("clientContent")
        if isinstance(client_content, list):
            for item in client_content:
                events.extend(self._translate_client_content(item))
        elif isinstance(client_content, Mapping):
            events.extend(self._translate_client_content(client_content))

        server_content = event.get("serverContent")
        if isinstance(server_content, list):
            for item in server_content:
                events.extend(self._translate_server_content(item))
        elif isinstance(server_content, Mapping):
            events.extend(self._translate_server_content(server_content))

        error = event.get("error")
        if error:
            message = error.get("message") if isinstance(error, Mapping) else str(error)
            events.append(
                RealtimeEvent(
                    RealtimeEventType.ERROR,
                    {"event": "provider.error", "message": message or "Unknown error"},
                )
            )

        return events

    def reset_response(self) -> None:
        """Reset the current response identifier.

        This is primarily useful when closing a turn to avoid leaking state
        across sessions.
        """

        self._current_response_id = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _translate_client_content(self, content: Mapping[str, object]) -> Iterable[RealtimeEvent]:
        events: list[RealtimeEvent] = []
        turns = content.get("turns")
        collected_text: list[str] = []

        if isinstance(turns, list):
            for turn in turns:
                if not isinstance(turn, Mapping):
                    continue
                parts = turn.get("parts")
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    text = self._extract_text(part)
                    if text:
                        collected_text.append(text)
                        events.append(
                            RealtimeEvent(
                                RealtimeEventType.MESSAGE,
                                {"event": "user.transcript.delta", "text": text},
                            )
                        )

        if content.get("turnComplete"):
            payload: MutableMapping[str, object] = {"event": "user.transcript.completed"}
            if collected_text:
                payload["text"] = " ".join(collected_text)
            events.append(RealtimeEvent(RealtimeEventType.MESSAGE, payload))

        return events

    def _translate_server_content(self, content: Mapping[str, object]) -> Iterable[RealtimeEvent]:
        events: list[RealtimeEvent] = []
        response_id = self._ensure_response_id()
        text_emitted = False
        audio_emitted = False

        model_turn = content.get("modelTurn")
        if isinstance(model_turn, Mapping):
            parts = model_turn.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    text = self._extract_text(part)
                    if text:
                        text_emitted = True
                        events.append(
                            RealtimeEvent(
                                RealtimeEventType.MESSAGE,
                                {
                                    "event": "assistant.text.delta",
                                    "response_id": response_id,
                                    "text": text,
                                },
                            )
                        )
                    audio_chunk, audio_format = self._extract_audio(part)
                    if audio_chunk:
                        audio_emitted = True
                        events.append(
                            RealtimeEvent(
                                RealtimeEventType.AUDIO_CHUNK,
                                {
                                    "response_id": response_id,
                                    "audio": audio_chunk,
                                    "format": audio_format or "pcm16",
                                },
                            )
                        )

        if content.get("turnComplete"):
            if text_emitted:
                events.append(
                    RealtimeEvent(
                        RealtimeEventType.MESSAGE,
                        {"event": "assistant.text.completed", "response_id": response_id},
                    )
                )
            if audio_emitted:
                events.append(
                    RealtimeEvent(
                        RealtimeEventType.AUDIO_CHUNK,
                        {
                            "response_id": response_id,
                            "event": "assistant.audio.completed",
                        },
                    )
                )
            events.append(
                RealtimeEvent(
                    RealtimeEventType.CONTROL,
                    {"event": "turn.completed", "response_id": response_id, "status": "completed"},
                )
            )
            self.reset_response()

        return events

    def _extract_text(self, part: Mapping[str, object] | object) -> str | None:
        if isinstance(part, Mapping):
            text = part.get("text") or part.get("response")
            if text is None and "language" in part:
                candidate = part.get("language")
                if isinstance(candidate, Mapping):
                    text = candidate.get("text")
            if text is not None:
                return str(text)
        if isinstance(part, str):
            return part
        return None

    def _extract_audio(self, part: Mapping[str, object] | object) -> tuple[str | None, str | None]:
        if isinstance(part, Mapping):
            inline_data = part.get("inlineData")
            if isinstance(inline_data, Mapping):
                data = inline_data.get("data")
                if isinstance(data, str):
                    mime_type = inline_data.get("mimeType")
                    return data, str(mime_type) if mime_type else None
        return None, None

    def _ensure_response_id(self) -> str:
        if not self._current_response_id:
            self._turn_index += 1
            self._current_response_id = f"gemini-turn-{self._turn_index:04d}"
        return self._current_response_id


__all__ = ["GoogleEventTranslator"]

