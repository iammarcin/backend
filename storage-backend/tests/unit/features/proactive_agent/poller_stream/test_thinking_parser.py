import pytest
from features.proactive_agent.poller_stream.thinking_parser import (
    ThinkingParser, ChunkType, ParsedChunk
)


class TestThinkingParser:

    def test_plain_text_no_tags(self):
        """Text without thinking tags passes through as text."""
        parser = ThinkingParser()
        chunks = parser.process("Hello world")
        assert len(chunks) == 1
        assert chunks[0].type == ChunkType.TEXT
        assert chunks[0].content == "Hello world"

    def test_complete_thinking_block(self):
        """Complete thinking block in single chunk."""
        parser = ThinkingParser()
        chunks = parser.process("<thinking>I am thinking</thinking>Done")

        # Should return: thinking chunk, then text chunk
        assert len(chunks) == 2
        assert chunks[0].type == ChunkType.THINKING
        assert chunks[0].content == "I am thinking"
        assert chunks[1].type == ChunkType.TEXT
        assert chunks[1].content == "Done"

    def test_partial_opening_tag(self):
        """Opening tag split across chunks."""
        parser = ThinkingParser()

        chunks1 = parser.process("Hello <think")
        # Should buffer the partial tag, emit "Hello "
        assert len(chunks1) == 1
        assert chunks1[0].content == "Hello "

        chunks2 = parser.process("ing>Deep thought")
        # Now complete tag, switch to thinking
        assert len(chunks2) == 1
        assert chunks2[0].type == ChunkType.THINKING
        assert chunks2[0].content == "Deep thought"

    def test_partial_closing_tag(self):
        """Closing tag split across chunks."""
        parser = ThinkingParser()

        parser.process("<thinking>")
        chunks1 = parser.process("Thought</think")
        # Should buffer partial tag, emit thinking content
        assert len(chunks1) == 1
        assert chunks1[0].type == ChunkType.THINKING
        assert chunks1[0].content == "Thought"

        chunks2 = parser.process("ing>After")
        # Complete tag, switch back to text
        assert len(chunks2) == 1
        assert chunks2[0].type == ChunkType.TEXT
        assert chunks2[0].content == "After"

    def test_false_positive_less_than(self):
        """< followed by non-tag text."""
        parser = ThinkingParser()
        chunks = parser.process("x < 5 and y > 3")
        assert len(chunks) == 1
        assert chunks[0].type == ChunkType.TEXT
        assert chunks[0].content == "x < 5 and y > 3"

    def test_multiple_thinking_blocks(self):
        """Multiple thinking blocks in sequence."""
        parser = ThinkingParser()
        text = "<thinking>First</thinking>Middle<thinking>Second</thinking>End"
        chunks = parser.process(text)

        assert len(chunks) == 4
        assert chunks[0] == ParsedChunk(ChunkType.THINKING, "First")
        assert chunks[1] == ParsedChunk(ChunkType.TEXT, "Middle")
        assert chunks[2] == ParsedChunk(ChunkType.THINKING, "Second")
        assert chunks[3] == ParsedChunk(ChunkType.TEXT, "End")

    def test_accumulated_text_includes_tags(self):
        """get_accumulated_text() includes raw tags."""
        parser = ThinkingParser()
        parser.process("<thinking>Thought</thinking>Text")

        assert parser.get_accumulated_text() == "<thinking>Thought</thinking>Text"

    def test_clean_text_excludes_thinking(self):
        """get_clean_text() excludes thinking content and tags."""
        parser = ThinkingParser()
        parser.process("Before<thinking>Thought</thinking>After")

        assert parser.get_clean_text() == "BeforeAfter"

    def test_accumulated_thinking(self):
        """get_accumulated_thinking() returns only thinking content."""
        parser = ThinkingParser()
        parser.process("Text<thinking>First</thinking>More<thinking>Second</thinking>")

        assert parser.get_accumulated_thinking() == "FirstSecond"

    def test_thinking_emits_immediately_before_close_tag(self):
        """Thinking content should stream in real-time, not wait for closing tag.

        M6.1 Bug Fix: Previously, thinking content was buffered until the closing
        tag arrived. Now it emits immediately for real-time streaming UX.
        """
        parser = ThinkingParser()

        chunks = parser.process("<thinking>Hello")
        assert len(chunks) == 1
        assert chunks[0].type == ChunkType.THINKING
        assert chunks[0].content == "Hello"

        chunks = parser.process(" world")
        assert len(chunks) == 1
        assert chunks[0].type == ChunkType.THINKING
        assert chunks[0].content == " world"

        chunks = parser.process("</thinking>The answer")
        assert len(chunks) == 1
        assert chunks[0].type == ChunkType.TEXT
        assert chunks[0].content == "The answer"

    def test_flush_with_partial_tag(self):
        """flush() returns buffered partial tag content."""
        parser = ThinkingParser()
        # Process content ending with partial closing tag
        parser.process("<thinking>Content</think")

        # The partial tag "</think" is buffered, but "Content" was already emitted
        chunks = parser.flush()
        # Only the partial tag remains in buffer, gets flushed as thinking
        assert len(chunks) == 1
        assert chunks[0].type == ChunkType.THINKING
        assert chunks[0].content == "</think"

    def test_empty_input(self):
        """Empty string returns empty list."""
        parser = ThinkingParser()
        chunks = parser.process("")
        assert chunks == []

    def test_streaming_character_by_character(self):
        """Works when receiving one character at a time."""
        parser = ThinkingParser()
        text = "<thinking>Hi</thinking>Bye"

        all_chunks = []
        for char in text:
            all_chunks.extend(parser.process(char))
        all_chunks.extend(parser.flush())

        # Combine chunks by type
        thinking = "".join(c.content for c in all_chunks if c.type == ChunkType.THINKING)
        regular = "".join(c.content for c in all_chunks if c.type == ChunkType.TEXT)

        assert thinking == "Hi"
        assert regular == "Bye"

    def test_reset(self):
        """reset() clears all state."""
        parser = ThinkingParser()
        parser.process("<thinking>Test</thinking>")
        parser.reset()

        assert parser.get_accumulated_text() == ""
        assert parser.get_clean_text() == ""
        assert parser.get_accumulated_thinking() == ""
