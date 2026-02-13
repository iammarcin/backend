"""Turn-scoped buffers used while processing realtime chat events."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class RealtimeTurnContext:
    """Accumulates streaming fragments for a single realtime conversation turn."""

    response_id: str | None = None
    user_transcript_parts: list[str] = field(default_factory=list)
    assistant_text_parts: list[str] = field(default_factory=list)
    assistant_transcript_parts: list[str] = field(default_factory=list)
    audio_chunks: list[bytes] = field(default_factory=list)
    live_translation_text: str | None = None
    live_translation_parts: list[str] = field(default_factory=list, repr=False)

    turn_number: int = 0
    ai_response_started: bool = False
    base_audio_filename: str = ""
    adjusted_audio_filename: str = ""
    initial_user_settings: Mapping[str, object] | None = None

    def reset(self) -> None:
        """Clear streaming buffers while retaining turn tracking metadata."""

        self.response_id = None
        self.user_transcript_parts.clear()
        self.assistant_text_parts.clear()
        self.assistant_transcript_parts.clear()
        self.audio_chunks.clear()
        self.live_translation_text = None
        self.live_translation_parts.clear()
        self.ai_response_started = False

    def append_live_translation(self, text: str, *, is_final: bool = False) -> None:
        """Append streaming translation fragments and honour final completions."""

        cleaned = text.strip()

        if is_final:
            if cleaned:
                self.live_translation_text = cleaned
            elif self.live_translation_text is None:
                # Persist an explicit empty string so downstream consumers can
                # distinguish "no translation" from "not populated yet".
                self.live_translation_text = ""
            self.live_translation_parts.clear()
            return

        if not cleaned:
            return

        self.live_translation_parts.append(cleaned)

        if self.live_translation_text:
            separator = " " if not self.live_translation_text.endswith((" ", "\n")) else ""
            self.live_translation_text = f"{self.live_translation_text}{separator}{cleaned}"
        else:
            self.live_translation_text = cleaned

    def user_transcript(self) -> str:
        """Return the concatenated transcript produced from user speech."""

        return " ".join(part for part in self.user_transcript_parts if part)

    def assistant_text(self) -> str:
        """Return the accumulated assistant text output from streaming events."""

        return "".join(self.assistant_text_parts)

    def assistant_transcript(self) -> str:
        """Return any assistant transcript captured during audio streaming."""

        return " ".join(part for part in self.assistant_transcript_parts if part)

    def audio_bytes(self) -> bytes:
        """Return the raw PCM audio generated for the current turn."""

        return b"".join(self.audio_chunks)

    def set_base_audio_filename(self, filename: str) -> None:
        """Persist the client supplied base filename for generated audio."""

        self.base_audio_filename = filename or ""
        if self.base_audio_filename:
            self.generate_turn_filename()
        else:
            self.adjusted_audio_filename = ""

    def generate_turn_filename(self) -> str:
        """Derive the filename for the current turn based on the base name."""

        if not self.base_audio_filename:
            self.adjusted_audio_filename = ""
            return ""

        path = Path(self.base_audio_filename)
        stem = path.stem
        extension = path.suffix or ".wav"

        match = re.search(r"_(\d{2,})$", stem)
        base_stem = stem[: match.start()] if match else stem
        if not base_stem:
            base_stem = "turn"

        filename = f"{base_stem}_{self.turn_number:02d}{extension}"
        parent = path.parent
        if parent and str(parent) != ".":
            self.adjusted_audio_filename = str(parent / filename)
        else:
            self.adjusted_audio_filename = filename
        return self.adjusted_audio_filename

    def prepare_for_next_turn(self) -> str:
        """Advance to the next turn and return the generated filename."""

        self.turn_number += 1
        next_filename = self.generate_turn_filename()
        # Update base_audio_filename to the current turn's filename to ensure
        # proper file rotation between turns in conversational mode
        if next_filename and self.base_audio_filename:
            self.base_audio_filename = next_filename
        return next_filename

    def increment_turn(self) -> None:
        """Advance the turn counter and refresh the derived filename."""

        self.prepare_for_next_turn()


__all__ = ["RealtimeTurnContext"]
