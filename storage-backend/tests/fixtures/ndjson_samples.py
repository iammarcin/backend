"""Sample NDJSON sequences for poller stream integration tests.

These fixtures represent real Claude CLI output patterns for testing
the complete poller stream pipeline.
"""

# Simple text response - just text chunks with no tools or thinking
SIMPLE_TEXT_RESPONSE = [
    '{"type": "system", "session_id": "claude-session-1"}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "Hello "}}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "world!"}}}',
    '{"type": "stream_event", "event": {"type": "message_stop"}}',
    '{"type": "result", "session_id": "claude-session-1"}',
]

# Response with thinking tags
THINKING_RESPONSE = [
    '{"type": "system", "session_id": "claude-session-2"}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "<thinking>Let me think"}}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": " about this...</thinking>"}}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "The answer is 42."}}}',
    '{"type": "stream_event", "event": {"type": "message_stop"}}',
    '{"type": "result", "session_id": "claude-session-2"}',
]

# Response with tool use (Bash command)
TOOL_USE_RESPONSE = [
    '{"type": "system", "session_id": "claude-session-3"}',
    '{"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "toolu_1", "name": "Bash"}}}',
    '{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "date"}}]}}',
    '{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "Mon Jan 1 2025"}]}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "The date is Monday."}}}',
    '{"type": "stream_event", "event": {"type": "message_stop"}}',
    '{"type": "result", "session_id": "claude-session-3"}',
]

# Response with chart marker in tool result
CHART_RESPONSE = [
    '{"type": "system", "session_id": "claude-session-4"}',
    '{"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "toolu_chart", "name": "Bash"}}}',
    '{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_chart", "name": "Bash", "input": {"command": "./generate_chart.sh"}}]}}',
    '{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_chart", "content": "[SHERLOCK_CHART:v1]\\n{\\"chart_type\\": \\"line\\", \\"title\\": \\"Test Chart\\", \\"data\\": {\\"labels\\": [\\"A\\", \\"B\\"], \\"datasets\\": [{\\"label\\": \\"Series\\", \\"data\\": [1, 2]}]}}\\n[/SHERLOCK_CHART]\\nChart generated successfully."}]}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "I have generated the chart."}}}',
    '{"type": "stream_event", "event": {"type": "message_stop"}}',
    '{"type": "result", "session_id": "claude-session-4"}',
]

# Response with research marker in tool result
RESEARCH_RESPONSE = [
    '{"type": "system", "session_id": "claude-session-5"}',
    '{"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "toolu_research", "name": "Bash"}}}',
    '{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_research", "name": "Bash", "input": {"command": "./deep_research.sh"}}]}}',
    '{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_research", "content": "[SHERLOCK_RESEARCH:v1]\\n{\\"query\\": \\"quantum computing applications\\"}\\n[/SHERLOCK_RESEARCH]\\nResearch initiated."}]}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "Research has been initiated."}}}',
    '{"type": "stream_event", "event": {"type": "message_stop"}}',
    '{"type": "result", "session_id": "claude-session-5"}',
]

# Response that starts then gets an error
PARTIAL_THEN_ERROR = [
    '{"type": "system", "session_id": "claude-session-6"}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "I am starting to..."}}}',
    # Error message would be sent separately as control message
]

# Multiple tool calls in sequence
MULTI_TOOL_RESPONSE = [
    '{"type": "system", "session_id": "claude-session-7"}',
    # First tool
    '{"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "toolu_a", "name": "Read"}}}',
    '{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_a", "name": "Read", "input": {"file_path": "/tmp/test.txt"}}]}}',
    '{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_a", "content": "File contents here"}]}}',
    # Second tool
    '{"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "toolu_b", "name": "Bash"}}}',
    '{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_b", "name": "Bash", "input": {"command": "echo test"}}]}}',
    '{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_b", "content": "test"}]}}',
    # Final response
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "Done with both operations."}}}',
    '{"type": "stream_event", "event": {"type": "message_stop"}}',
    '{"type": "result", "session_id": "claude-session-7"}',
]

# Empty response (only system and result)
EMPTY_RESPONSE = [
    '{"type": "system", "session_id": "claude-session-8"}',
    '{"type": "result", "session_id": "claude-session-8"}',
]

# Thinking that spans multiple chunks
SPLIT_THINKING_RESPONSE = [
    '{"type": "system", "session_id": "claude-session-9"}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "<think"}}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "ing>This is"}}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": " deep thinking</think"}}}',
    '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": "ing>Here is the answer."}}}',
    '{"type": "stream_event", "event": {"type": "message_stop"}}',
    '{"type": "result", "session_id": "claude-session-9"}',
]
