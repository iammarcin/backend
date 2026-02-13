"""REST streaming helpers for ElevenLabs."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, AsyncIterator, Mapping

import requests

from core.exceptions import ProviderError


logger = logging.getLogger(__name__)


async def stream_rest_audio(
    *,
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    provider_name: str,
) -> AsyncIterator[bytes]:
    """Yield audio bytes produced by the ElevenLabs REST streaming endpoint."""

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[object] = asyncio.Queue()
    sentinel = object()

    def _produce() -> None:
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=60,
                stream=True,
            )
            if response.status_code >= 400:
                raise ProviderError(
                    f"ElevenLabs TTS returned {response.status_code}: {response.text}",
                    provider=provider_name,
                )
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    loop.call_soon_threadsafe(queue.put_nowait, bytes(chunk))
        except ProviderError as exc:  # pragma: no cover - defensive
            loop.call_soon_threadsafe(queue.put_nowait, ("provider_error", exc))
        except Exception as exc:  # pragma: no cover - defensive
            loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    thread = threading.Thread(target=_produce, daemon=True)
    thread.start()

    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            if isinstance(item, tuple):
                label, exc = item
                if label == "provider_error":
                    raise exc
                raise ProviderError(
                    "ElevenLabs TTS streaming failed", provider=provider_name, original_error=exc
                ) from exc
            if isinstance(item, bytes) and item:
                yield item
    finally:
        await asyncio.to_thread(thread.join)


__all__ = ["stream_rest_audio"]
