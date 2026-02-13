"""Initialise AI provider clients used across the application."""

from __future__ import annotations

import asyncio
import atexit
import logging
from inspect import isawaitable
from typing import Dict

from anthropic import Anthropic, AsyncAnthropic
from google import genai
from openai import AsyncOpenAI, OpenAI
from xai_sdk import AsyncClient as XaiAsyncClient
from xai_sdk import Client as XaiClient

from core.utils.env import get_env
from .xai_adapters import XaiAsyncClientAdapter, XaiClientAdapter

logger = logging.getLogger(__name__)


def _get_env(key: str, required: bool = False) -> str | None:
    """Read an environment variable, optionally ensuring it exists."""

    value = get_env(key)
    if required and not value:
        raise ValueError(f"Required environment variable {key} not set")
    return value


ai_clients: Dict[str, object] = {}
_xai_shutdown_registered = False


def _parse_bool_env(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean environment variable value: {value}")


def _parse_float_env(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid float environment variable value: {value}") from exc


def _register_xai_shutdown() -> None:
    """Ensure xAI SDK clients are closed when the interpreter exits."""

    global _xai_shutdown_registered

    if _xai_shutdown_registered:
        return

    def _shutdown_xai_clients() -> None:
        sync_client = ai_clients.get("xai")
        if sync_client is not None:
            close_fn = getattr(sync_client, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:  # pragma: no cover - best-effort cleanup
                    logger.debug("Failed to close xAI client", exc_info=True)

        async_client = ai_clients.get("xai_async")
        if async_client is not None:
            close_fn = getattr(async_client, "close", None)
            if callable(close_fn):
                try:
                    result = close_fn()
                    if isawaitable(result):
                        async_logger = logging.getLogger("asyncio")
                        previous_disabled = async_logger.disabled
                        async_logger.disabled = True
                        try:
                            asyncio.run(result)
                        except RuntimeError:
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = None
                            if loop and loop.is_running():
                                loop.create_task(result)  # type: ignore[arg-type]
                            elif loop:
                                loop.run_until_complete(result)
                        finally:
                            async_logger.disabled = previous_disabled
                except Exception:  # pragma: no cover - best-effort cleanup
                    logger.debug("Failed to close async xAI client", exc_info=True)

    atexit.register(_shutdown_xai_clients)
    _xai_shutdown_registered = True

try:
    if _get_env("OPENAI_API_KEY"):
        ai_clients["openai"] = OpenAI()
        ai_clients["openai_async"] = AsyncOpenAI()
        logger.info("Initialised OpenAI clients")

    if _get_env("CLAUDE_KEY"):
        ai_clients["anthropic"] = Anthropic(api_key=_get_env("CLAUDE_KEY"))
        ai_clients["anthropic_async"] = AsyncAnthropic(api_key=_get_env("CLAUDE_KEY"))
        logger.info("Initialised Anthropic clients")

    if _get_env("GOOGLE_API_KEY"):
        ai_clients["gemini"] = genai.Client(api_key=_get_env("GOOGLE_API_KEY"))
        logger.info("Initialised Gemini client")

    if _get_env("GROQ_API_KEY"):
        ai_clients["groq"] = OpenAI(api_key=_get_env("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")
        ai_clients["groq_async"] = AsyncOpenAI(
            api_key=_get_env("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )
        logger.info("Initialised Groq clients")

    if _get_env("PERPLEXITY_API_KEY"):
        ai_clients["perplexity"] = OpenAI(
            api_key=_get_env("PERPLEXITY_API_KEY"),
            base_url="https://api.perplexity.ai",
        )
        ai_clients["perplexity_async"] = AsyncOpenAI(
            api_key=_get_env("PERPLEXITY_API_KEY"),
            base_url="https://api.perplexity.ai",
        )
        logger.info("Initialised Perplexity clients")

    if _get_env("DEEPSEEK_API_KEY"):
        ai_clients["deepseek"] = OpenAI(
            api_key=_get_env("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/",
        )
        ai_clients["deepseek_async"] = AsyncOpenAI(
            api_key=_get_env("DEEPSEEK_API_KEY"),
            #base_url="https://api.deepseek.com/v3.2_speciale_expires_on_20251215",
            base_url="https://api.deepseek.com/",
        )
        logger.info("Initialised DeepSeek clients")

    xai_api_key = _get_env("XAI_API_KEY")
    if xai_api_key:
        xai_kwargs: Dict[str, object] = {}

        if host := _get_env("XAI_API_HOST"):
            xai_kwargs["api_host"] = host

        if management_host := _get_env("XAI_MANAGEMENT_API_HOST"):
            xai_kwargs["management_api_host"] = management_host

        if management_key := _get_env("XAI_MANAGEMENT_KEY"):
            xai_kwargs["management_api_key"] = management_key

        timeout_value = _parse_float_env(_get_env("XAI_TIMEOUT"))
        if timeout_value is not None:
            xai_kwargs["timeout"] = timeout_value

        insecure_value = _parse_bool_env(_get_env("XAI_USE_INSECURE_CHANNEL"))
        if insecure_value is not None:
            xai_kwargs["use_insecure_channel"] = insecure_value

        ai_clients["xai"] = XaiClientAdapter(XaiClient(api_key=xai_api_key, **xai_kwargs))
        ai_clients["xai_async"] = XaiAsyncClientAdapter(
            XaiAsyncClient(api_key=xai_api_key, **xai_kwargs)
        )
        _register_xai_shutdown()
        logger.info("Initialised xAI SDK clients")
except Exception as exc:  # pragma: no cover - init failure should crash fast
    logger.error("Error initialising AI clients: %s", exc)
    raise

logger.info("Initialised %s AI client(s)", len(ai_clients))


def get_openai_client() -> OpenAI:
    """Return a cached synchronous OpenAI client."""

    client = ai_clients.get("openai")
    if client is not None:
        return client  # type: ignore[return-value]

    api_key = _get_env("OPENAI_API_KEY", required=True)
    client = OpenAI(api_key=api_key)
    ai_clients["openai"] = client
    logger.info("Initialised OpenAI client via helper")
    return client


def get_openai_async_client() -> AsyncOpenAI:
    """Return a cached asynchronous OpenAI client."""

    client = ai_clients.get("openai_async")
    if client is not None:
        return client  # type: ignore[return-value]

    api_key = _get_env("OPENAI_API_KEY", required=True)
    client = AsyncOpenAI(api_key=api_key)
    ai_clients["openai_async"] = client
    logger.info("Initialised OpenAI async client via helper")
    return client


def get_google_client():
    """Return an initialised Google Generative AI client."""

    client = ai_clients.get("gemini")
    if client is not None:
        return client

    api_key = _get_env("GOOGLE_API_KEY", required=True)
    client = genai.Client(api_key=api_key)
    ai_clients["gemini"] = client
    logger.info("Initialised Gemini client via helper")
    return client


def get_gemini_client():
    """Alias around :func:`get_google_client` for clarity."""

    return get_google_client()
