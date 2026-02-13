"""Tests for Responses API format conversion utilities."""

from core.providers.text.utils import convert_to_responses_format, is_responses_api_model


def test_convert_simple_text_messages() -> None:
    """Test conversion of simple text messages.

    The function now extracts system prompts and returns them separately
    since the Responses API expects them in the 'instructions' parameter.
    """

    chat_history = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]

    messages, system_instruction = convert_to_responses_format(chat_history)

    # System prompt should be extracted
    assert system_instruction == "You are helpful"

    # Messages should not contain system role (extracted out)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == [{"type": "input_text", "text": "Hello"}]
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == [{"type": "output_text", "text": "Hi there"}]


def test_convert_multimodal_user_message() -> None:
    """Test conversion of user message with text and image.

    Multimodal content should be properly converted to Responses API format.
    """

    chat_history = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's this?"},
                {"type": "image_url", "image_url": {"url": "https://example.com/img.jpg"}},
            ],
        },
    ]

    messages, system_instruction = convert_to_responses_format(chat_history)

    # No system prompt in this test
    assert system_instruction is None

    # Check message format
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert len(messages[0]["content"]) == 2

    # Text should be converted to input_text
    assert messages[0]["content"][0] == {"type": "input_text", "text": "What's this?"}

    # Image URL should be converted to input_image
    assert messages[0]["content"][1] == {
        "type": "input_image",
        "image_url": "https://example.com/img.jpg"
    }


def test_convert_file_url() -> None:
    """Test conversion of file URL.

    File URLs should be converted to input_file format for Responses API.
    """

    chat_history = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze this"},
                {"type": "file_url", "file_url": {"url": "https://example.com/doc.pdf"}},
            ],
        },
    ]

    messages, system_instruction = convert_to_responses_format(chat_history)

    # No system prompt in this test
    assert system_instruction is None

    # Check file URL conversion
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert len(messages[0]["content"]) == 2

    # Text should be converted
    assert messages[0]["content"][0] == {"type": "input_text", "text": "Analyze this"}

    # File URL should be converted to input_file
    assert messages[0]["content"][1] == {
        "type": "input_file",
        "file_url": "https://example.com/doc.pdf"
    }


def test_system_prompt_extraction() -> None:
    """Test that system prompts are correctly extracted from chat history.

    The Responses API requires system prompts to be sent via 'instructions',
    not in the messages array. This test verifies extraction works correctly.
    """

    # Test 1: Simple string system prompt
    chat_history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]

    messages, system_instruction = convert_to_responses_format(chat_history)

    assert system_instruction == "You are a helpful assistant."
    assert len(messages) == 1
    assert messages[0]["role"] == "user"

    # Test 2: System prompt with list content (should extract text parts)
    chat_history_list = [
        {
            "role": "system",
            "content": [
                {"type": "text", "text": "You are helpful."},
                {"type": "text", "text": "Be concise."}
            ]
        },
        {"role": "user", "content": "Test"},
    ]

    messages2, system_instruction2 = convert_to_responses_format(chat_history_list)

    assert system_instruction2 == "You are helpful. Be concise."
    assert len(messages2) == 1

    # Test 3: No system prompt
    chat_history_no_system = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    messages3, system_instruction3 = convert_to_responses_format(chat_history_no_system)

    assert system_instruction3 is None
    assert len(messages3) == 2


def test_is_responses_api_model() -> None:
    """Test Responses API model detection fallback."""

    assert is_responses_api_model("gpt-5-pro") is True
    assert is_responses_api_model("gpt-5") is True
    assert is_responses_api_model("o3") is True
    assert is_responses_api_model("o3-mini") is True
    assert is_responses_api_model("gpt-4o") is False
    assert is_responses_api_model("gpt-4o-mini") is False


def test_convert_tool_calls_and_outputs() -> None:
    """Ensure tool calls and outputs convert to Responses API format."""

    chat_history = [
        {"role": "user", "content": "Create an image"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc",
                    "function": {
                        "name": "generate_image",
                        "arguments": '{"prompt": "cat"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_abc", "content": {"url": "https://example.com"}},
    ]

    messages, system_instruction = convert_to_responses_format(chat_history)

    assert system_instruction is None
    assert len(messages) == 3
    assert messages[0]["role"] == "user"

    # Tool call should be represented as a function_call item
    assert messages[1]["type"] == "function_call"
    assert messages[1]["call_id"] == "call_abc"
    assert messages[1]["name"] == "generate_image"
    assert messages[1]["arguments"] == '{"prompt": "cat"}'

    # Tool result should convert to function_call_output
    assert messages[2]["type"] == "function_call_output"
    assert messages[2]["call_id"] == "call_abc"
    assert messages[2]["output"] == '{"url": "https://example.com"}'


def test_convert_assistant_text_and_tool_calls() -> None:
    """Assistant text plus tool calls should produce multiple entries."""

    chat_history = [
        {"role": "assistant", "content": "Let me help", "tool_calls": []},
        {
            "role": "assistant",
            "content": "Calling a tool",
            "tool_calls": [
                {
                    "id": "call_xyz",
                    "function": {
                        "name": "generate_text",
                        "arguments": {"prompt": "hello"},
                    },
                }
            ],
        },
    ]

    messages, _ = convert_to_responses_format(chat_history)

    assert len(messages) == 3
    assert messages[0]["role"] == "assistant"
    assert messages[0]["content"] == [{"type": "output_text", "text": "Let me help"}]

    # The second assistant entry should still produce text content
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == [{"type": "output_text", "text": "Calling a tool"}]

    # Tool call converted to function_call with JSON arguments
    assert messages[2]["type"] == "function_call"
    assert messages[2]["call_id"] == "call_xyz"
    assert messages[2]["name"] == "generate_text"
    assert messages[2]["arguments"] == '{"prompt": "hello"}'
