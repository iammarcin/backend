"""Adapters that expose xAI SDK clients through an OpenAI-compatible interface."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any, Dict

from xai_sdk import AsyncClient as XaiAsyncClient
from xai_sdk import Client as XaiClient
from xai_sdk import chat as xai_chat
from xai_sdk.chat import sample_pb2, usage_pb2


class _OpenAIMessageAdapter(dict):
    """Provide dict-style and attribute access to chat messages."""

    def __init__(self, role: str, content: str) -> None:
        super().__init__(role=role, content=content)
        self.role = role
        self.content = content


class _UsageAdapter:
    """Expose xAI usage proto via OpenAI-style interface."""

    def __init__(self, usage: usage_pb2.SamplingUsage) -> None:
        self._usage = usage

    def model_dump(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self._usage.prompt_tokens,
            "completion_tokens": self._usage.completion_tokens,
            "reasoning_tokens": getattr(self._usage, "reasoning_tokens", 0),
            "total_tokens": self._usage.total_tokens,
        }


class _OpenAIChoiceAdapter:
    def __init__(self, response: Any) -> None:
        role = getattr(response, "role", "assistant")
        content = getattr(response, "content", "")
        self.message = _OpenAIMessageAdapter(role=role, content=content)
        finish_reason = getattr(response, "finish_reason", None)
        self.finish_reason = finish_reason.lower() if isinstance(finish_reason, str) else finish_reason


class _OpenAIResponseAdapter:
    def __init__(self, response: Any) -> None:
        self.id = getattr(response, "id", None)
        self.model = getattr(getattr(response, "request_settings", None), "model", None)
        self.choices = [_OpenAIChoiceAdapter(response)]
        usage = getattr(response, "usage", None)
        self.usage = _UsageAdapter(usage) if usage is not None else None


class _OpenAIStreamDeltaAdapter:
    def __init__(self, chunk_choice: Any) -> None:
        self.role = "assistant"
        self.content = getattr(chunk_choice, "content", "")


class _OpenAIStreamChoiceAdapter:
    def __init__(self, chunk_choice: Any) -> None:
        self.delta = _OpenAIStreamDeltaAdapter(chunk_choice)
        finish_reason = getattr(chunk_choice, "finish_reason", None)
        if finish_reason is None:
            self.finish_reason = None
        else:
            try:
                enum_value = finish_reason
                self.finish_reason = sample_pb2.FinishReason.Name(enum_value).lower()
            except (TypeError, ValueError):  # pragma: no cover - defensive guard
                self.finish_reason = None


class _OpenAIStreamChunkAdapter:
    def __init__(self, chunk: Any) -> None:
        choices = getattr(chunk, "choices", []) or []
        self.choices = [_OpenAIStreamChoiceAdapter(choice) for choice in choices]


class _XaiSyncStreamWrapper:
    def __init__(self, iterator: Iterator[tuple[Any, Any]]) -> None:
        self._iterator = iterator

    def __iter__(self):
        for _, chunk in self._iterator:
            yield _OpenAIStreamChunkAdapter(chunk)


class _XaiAsyncStreamWrapper:
    def __init__(self, async_iterator: AsyncIterator[tuple[Any, Any]]) -> None:
        self._async_iterator = async_iterator

    def __aiter__(self):
        async def _generator():
            async for _, chunk in self._async_iterator:
                yield _OpenAIStreamChunkAdapter(chunk)

        return _generator()


def _normalise_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif item.get("type") == "image_url":
                    url_data = item.get("image_url", {})
                    if isinstance(url_data, dict):
                        parts.append(str(url_data.get("url", "")))
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return str(content)


_ROLE_BUILDERS = {
    "system": xai_chat.system,
    "user": xai_chat.user,
    "assistant": xai_chat.assistant,
    "tool": xai_chat.tool_result,
}


def _convert_openai_messages(messages: Sequence[Any]) -> list[Any]:
    converted: list[Any] = []
    for message in messages:
        if not isinstance(message, dict):
            converted.append(message)
            continue

        role = str(message.get("role", "user")).lower()
        builder = _ROLE_BUILDERS.get(role, xai_chat.user)
        content = _normalise_message_content(message.get("content"))
        try:
            converted.append(builder(content))
        except Exception:  # pragma: no cover - defensive
            converted.append(builder(str(content)))
    return converted


class _XaiSyncCompletionsAdapter:
    def __init__(self, chat_client: Any) -> None:
        self._chat_client = chat_client

    def create(self, *args: Any, **kwargs: Any) -> Any:
        stream = kwargs.pop("stream", False)
        messages = kwargs.get("messages")
        if isinstance(messages, list):
            kwargs["messages"] = _convert_openai_messages(messages)

        chat_request = self._chat_client.create(*args, **kwargs)
        if stream:
            return _XaiSyncStreamWrapper(chat_request.stream())

        response = chat_request.sample()
        return _OpenAIResponseAdapter(response)


class _XaiAsyncCompletionsAdapter:
    def __init__(self, chat_client: Any) -> None:
        self._chat_client = chat_client

    async def create(self, *args: Any, **kwargs: Any) -> Any:
        stream = kwargs.pop("stream", False)
        messages = kwargs.get("messages")
        if isinstance(messages, list):
            kwargs["messages"] = _convert_openai_messages(messages)

        chat_request = self._chat_client.create(*args, **kwargs)
        if stream:
            return _XaiAsyncStreamWrapper(chat_request.stream())

        response = await chat_request.sample()
        return _OpenAIResponseAdapter(response)


class XaiSyncChatAdapter:
    """Expose xAI chat client with OpenAI-compatible methods."""

    def __init__(self, chat_client: Any) -> None:
        self._chat_client = chat_client
        self.completions = _XaiSyncCompletionsAdapter(chat_client)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._chat_client, item)


class XaiAsyncChatAdapter:
    """Async variant of :class:`XaiSyncChatAdapter`."""

    def __init__(self, chat_client: Any) -> None:
        self._chat_client = chat_client
        self.completions = _XaiAsyncCompletionsAdapter(chat_client)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._chat_client, item)


class XaiClientAdapter:
    """Wrap a synchronous xAI client with OpenAI-compatible chat interface."""

    def __init__(self, client: XaiClient) -> None:
        self._client = client
        self.chat = XaiSyncChatAdapter(client.chat)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._client, item)

    def close(self) -> None:
        return self._client.close()


class XaiAsyncClientAdapter:
    """Wrap an asynchronous xAI client with OpenAI-compatible chat interface."""

    def __init__(self, client: XaiAsyncClient) -> None:
        self._client = client
        self.chat = XaiAsyncChatAdapter(client.chat)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._client, item)

    async def close(self) -> None:
        await self._client.close()


__all__ = [
    "XaiClientAdapter",
    "XaiAsyncClientAdapter",
    "XaiSyncChatAdapter",
    "XaiAsyncChatAdapter",
]
