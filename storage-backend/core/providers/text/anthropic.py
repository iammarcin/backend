"""Anthropic Claude text generation provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.clients.ai import ai_clients
from core.exceptions import ProviderError, ValidationError
from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.providers.base import BaseTextProvider
from core.providers.batch import AnthropicBatchOperations
from core.providers.text.utils import log_tool_usage
from config.batch.defaults import (
    BATCH_MAX_FILE_SIZE_MB_ANTHROPIC,
    BATCH_MAX_REQUESTS_ANTHROPIC,
)
from .anthropic_batch import prepare_anthropic_batch_requests, process_anthropic_batch_response
from .anthropic_params import build_api_params, prepare_messages
from .anthropic_streaming import stream_anthropic

logger = logging.getLogger(__name__)


class AnthropicTextProvider(BaseTextProvider):
    """Text provider implementation for Anthropic Claude models."""

    provider_name = "anthropic"

    def __init__(self) -> None:
        self.client = ai_clients.get("anthropic_async")
        if not self.client:
            raise ProviderError("Anthropic client not initialized", provider="anthropic")

        self.capabilities = ProviderCapabilities(
            streaming=True,
            reasoning=True,
            citations=False,
            audio_input=False,
            image_input=True,
            batch_api=True,
            batch_max_requests=BATCH_MAX_REQUESTS_ANTHROPIC,
            batch_max_file_size_mb=BATCH_MAX_FILE_SIZE_MB_ANTHROPIC,
        )

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = "claude-sonnet-4-5",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        enable_reasoning: bool = False,
        reasoning_value: Optional[int] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a non-streaming response."""

        if not prompt:
            raise ProviderError("Prompt cannot be empty", provider="anthropic")

        final_messages = prepare_messages(prompt, messages)
        # Remove unsupported kwargs that might be provided by higher-level services
        kwargs.pop("tool_settings", None)
        kwargs.pop("builtin_tool_config", None)

        provided_tools = kwargs.pop("tools", None)
        disable_native_tools = bool(kwargs.pop("disable_native_tools", False))
        if provided_tools is not None:
            tools_payload = provided_tools
        elif disable_native_tools:
            tools_payload = []
        else:
            tools_payload = self.get_native_tools()

        api_params = build_api_params(
            model=model,
            messages=final_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            enable_reasoning=enable_reasoning,
            reasoning_value=reasoning_value,
            tools=tools_payload,
            extra_kwargs=kwargs,
        )

        logger.debug(
            "Anthropic API call: model=%s, messages_count=%d, system_prompt=%s, temperature=%.2f, max_tokens=%d, thinking=%s",
            api_params["model"],
            len(final_messages),
            "present" if system_prompt else "none",
            api_params.get("temperature", 0.0),
            api_params.get("max_tokens", 0),
            api_params.get("thinking", "disabled"),
        )

        try:
            response = await self.client.messages.create(**api_params)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Anthropic generate error: %s", exc)
            raise ProviderError(f"Anthropic error: {exc}", provider="anthropic") from exc

        log_tool_usage(
            "Anthropic",
            getattr(response, "content", None),
            logger=logger,
        )

        text = ""
        if getattr(response, "content", None):
            text = "".join(part.text for part in response.content if getattr(part, "text", None))

        return ProviderResponse(
            text=text,
            model=model,
            provider="anthropic",
        )

    async def generate_batch(
        self,
        requests: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> List[ProviderResponse]:
        """Generate multiple completions via Anthropic Message Batches API."""

        if not getattr(self.capabilities, "batch_api", False):
            return await super().generate_batch(requests, **kwargs)

        if not requests:
            return []

        batch_requests, request_map = prepare_anthropic_batch_requests(self, requests)
        batch_ops = AnthropicBatchOperations(self.client)

        try:
            results = await batch_ops.submit_and_wait(batch_requests)
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Anthropic batch submission failed")
            raise ProviderError("Anthropic batch submission failed", provider="anthropic", original_error=exc) from exc

        return await process_anthropic_batch_response(self, requests, results)

    async def stream(
        self,
        prompt: str,
        model: Optional[str] = "claude-sonnet-4-5",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        enable_reasoning: bool = False,
        reasoning_value: Optional[int] = None,
        runtime: Optional["WorkflowRuntime"] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Stream response chunks using Anthropic's streaming API."""
        provided_tools = kwargs.pop("tools", None)
        disable_native_tools = kwargs.pop("disable_native_tools", False)

        async for item in stream_anthropic(
            self.client,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            messages=messages,
            enable_reasoning=enable_reasoning,
            reasoning_value=reasoning_value,
            runtime=runtime,
            provider=self,
            tools=provided_tools,
            disable_native_tools=disable_native_tools,
            **kwargs,
        ):
            yield item

    async def generate_with_reasoning(
        self,
        prompt: str,
        reasoning_effort: str = "medium",
        model: Optional[str] = "claude-sonnet-4-5",
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a response that includes Anthropic's thinking output."""

        kwargs.setdefault("reasoning", {"effort": reasoning_effort})
        return await self.generate(prompt=prompt, model=model, **kwargs)

    def get_native_tools(self) -> list[dict[str, Any]]:
        """Return native tools available without custom configuration."""

        return [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5,
            }
        ]
