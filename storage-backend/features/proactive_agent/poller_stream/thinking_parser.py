"""Stateful parser for <thinking> tags in streaming text."""

from dataclasses import dataclass
from enum import Enum


class ChunkType(Enum):
    TEXT = "text"
    THINKING = "thinking"


@dataclass
class ParsedChunk:
    type: ChunkType
    content: str


OPENING_TAG = "<thinking>"
CLOSING_TAG = "</thinking>"


class ThinkingParser:
    """
    Stateful parser for <thinking> tags in streaming text.

    Usage:
        parser = ThinkingParser()
        for delta in stream:
            chunks = parser.process(delta)
            for chunk in chunks:
                if chunk.type == ChunkType.THINKING:
                    emit_thinking_chunk(chunk.content)
                else:
                    emit_text_chunk(chunk.content)

        final_chunks = parser.flush()
        clean_text = parser.get_clean_text()
    """

    def __init__(self) -> None:
        """Initialize parser state."""
        self._in_thinking = False
        self._buffer = ""
        self._accumulated_text = ""
        self._accumulated_thinking = ""
        self._accumulated_clean = ""
        self._had_partial_tag = False

    def process(self, text: str) -> list[ParsedChunk]:
        """Process incoming text chunk and return parsed chunks."""
        if not text:
            return []

        self._accumulated_text += text
        # Check if we have a partial tag before appending
        tag = CLOSING_TAG if self._in_thinking else OPENING_TAG
        self._had_partial_tag = self._partial_tag_length(tag) > 0
        self._buffer += text
        return self._parse_buffer()

    def _parse_buffer(self) -> list[ParsedChunk]:
        """Parse buffered content and emit complete chunks."""
        chunks = []
        completed_partial = False
        while True:
            tag = CLOSING_TAG if self._in_thinking else OPENING_TAG
            tag_pos = self._buffer.find(tag)

            if tag_pos != -1:
                # Found complete tag
                before = self._buffer[:tag_pos]
                if before:
                    chunks.append(self._make_chunk(before))
                self._in_thinking = not self._in_thinking
                self._buffer = self._buffer[tag_pos + len(tag) :]
                completed_partial = self._had_partial_tag
                self._had_partial_tag = False
            else:
                # Check for partial tag at end
                partial_len = self._partial_tag_length(tag)
                if partial_len > 0:
                    # Emit content before partial tag, keep partial buffered
                    before = self._buffer[:-partial_len]
                    if before:
                        chunks.append(self._make_chunk(before))
                    self._buffer = self._buffer[-partial_len:]
                elif self._buffer:
                    # Emit immediately regardless of mode (real-time streaming)
                    chunks.append(self._make_chunk(self._buffer))
                    self._buffer = ""
                break
        return chunks

    def _partial_tag_length(self, tag: str) -> int:
        """Return length of partial tag match at end of buffer."""
        for length in range(min(len(tag) - 1, len(self._buffer)), 0, -1):
            if tag.startswith(self._buffer[-length:]):
                return length
        return 0

    def _make_chunk(self, content: str) -> ParsedChunk:
        """Create chunk and update accumulators."""
        chunk_type = ChunkType.THINKING if self._in_thinking else ChunkType.TEXT
        if self._in_thinking:
            self._accumulated_thinking += content
        else:
            self._accumulated_clean += content
        return ParsedChunk(chunk_type, content)

    def flush(self) -> list[ParsedChunk]:
        """Flush any remaining buffered content."""
        if not self._buffer:
            return []
        chunk = self._make_chunk(self._buffer)
        self._buffer = ""
        return [chunk]

    def get_accumulated_text(self) -> str:
        """Get full accumulated text INCLUDING <thinking> tags."""
        return self._accumulated_text

    def get_clean_text(self) -> str:
        """Get accumulated text with thinking content removed."""
        return self._accumulated_clean

    def get_accumulated_thinking(self) -> str:
        """Get just the thinking content (without tags)."""
        return self._accumulated_thinking

    def reset(self) -> None:
        """Reset parser state for reuse."""
        self._in_thinking = False
        self._buffer = ""
        self._accumulated_text = ""
        self._accumulated_thinking = ""
        self._accumulated_clean = ""
        self._had_partial_tag = False
