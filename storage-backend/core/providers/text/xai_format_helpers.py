"""Helper functions supporting xAI message formatting."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx
from xai_sdk import AsyncClient as XaiAsyncClient
from xai_sdk import chat

logger = logging.getLogger(__name__)


DownloadFn = Callable[[str], Awaitable[bytes]]

_VALID_DETAIL_HINTS = {"auto", "low", "high"}


def _is_remote_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _is_data_url(url: str) -> bool:
    return url.startswith("data:")


def _is_local_path(path_str: str) -> bool:
    if not path_str or _is_remote_url(path_str) or _is_data_url(path_str):
        return False
    try:
        path = Path(path_str)
    except OSError:  # pragma: no cover - path parsing edge cases
        return False
    return path.exists()


def normalise_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value)
        except TypeError:  # pragma: no cover - defensive guard
            return str(value)
    return str(value)


async def download_file(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _extract_filename(file_payload: Any, fallback_url: str | None = None) -> str:
    if isinstance(file_payload, dict):
        for key in ("filename", "name", "file_name"):
            if value := file_payload.get(key):
                return str(value)
    if fallback_url:
        try:
            url_path = Path(fallback_url)
            if url_path.name and url_path.name != fallback_url:
                return url_path.name
        except OSError:  # pragma: no cover - invalid path strings
            logger.debug("Failed to derive filename from %s", fallback_url, exc_info=True)
    return "attachment"


async def _read_local_file(path: Path) -> bytes:
    return await asyncio.to_thread(path.read_bytes)


async def _resolve_file_content(
    *,
    item: dict[str, Any],
    client: XaiAsyncClient,
    upload_cache: Dict[str, str],
    uploaded_file_ids: List[str],
    temporary_files: List[Path],
    download_fn: DownloadFn,
) -> Any | None:
    file_value = item.get("file_url")
    if isinstance(file_value, dict):
        url = normalise_text(file_value.get("url"))
    else:
        url = normalise_text(file_value)

    if not url:
        logger.debug("Skipping file_url content without URL: %s", item)
        return None

    if url in upload_cache:
        file_id = upload_cache[url]
        return chat.file(file_id=file_id)

    filename = _extract_filename(file_value, url)

    if _is_local_path(url):
        path = Path(url)
        temporary_files.append(path)
        file_bytes = await _read_local_file(path)
    else:
        file_bytes = await download_fn(url)

    upload_response = await client.files.upload(file_bytes, filename=filename)
    file_id = getattr(upload_response, "id", None)
    if not file_id and isinstance(upload_response, dict):  # pragma: no cover
        file_id = upload_response.get("id")
    if not file_id:  # pragma: no cover - guard for SDK changes
        raise RuntimeError("xAI upload did not return a file id")

    upload_cache[url] = file_id
    uploaded_file_ids.append(file_id)
    return chat.file(file_id=file_id)


async def _resolve_image_content(
    *,
    item: dict[str, Any],
    temporary_files: List[Path],
) -> tuple[str | None, str | None]:
    image_url: str | None = None
    detail: str | None = None

    if item.get("type") == "image":
        source = item.get("source", {})
        if isinstance(source, dict):
            source_type = str(source.get("type") or "").lower()
            if source_type == "base64":
                media_type = source.get("media_type") or "image/png"
                data = source.get("data")
                if data:
                    image_url = f"data:{media_type};base64,{data}"
            elif source_type == "url":
                image_url = normalise_text(source.get("url"))
            else:
                image_url = normalise_text(source.get("data"))
        detail = item.get("detail")
    else:
        image_payload = item.get("image_url") or item.get("image")
        if isinstance(image_payload, dict):
            image_url = normalise_text(image_payload.get("url") or image_payload.get("data"))
            detail = image_payload.get("detail") or item.get("detail")
        else:
            image_url = normalise_text(image_payload)
            detail = item.get("detail")

    if not image_url:
        return None, None

    if _is_local_path(image_url):
        path = Path(image_url)
        temporary_files.append(path)
        image_bytes = await _read_local_file(path)
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type:
            mime_type = "application/octet-stream"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        image_url = f"data:{mime_type};base64,{encoded}"

    detail_hint = None
    if isinstance(detail, str):
        lowered = detail.lower()
        if lowered in _VALID_DETAIL_HINTS:
            detail_hint = lowered

    return image_url, detail_hint


async def convert_content_item(
    item: Any,
    *,
    client: XaiAsyncClient,
    upload_cache: Dict[str, str],
    uploaded_file_ids: List[str],
    temporary_files: List[Path],
    download_fn: DownloadFn,
) -> Any | None:
    if not isinstance(item, dict):
        return chat.text(normalise_text(item))

    item_type = item.get("type")

    if item_type == "text":
        return chat.text(normalise_text(item.get("text")))

    if item_type in {"image_url", "image"}:
        image_url, detail = await _resolve_image_content(
            item=item,
            temporary_files=temporary_files,
        )
        if not image_url:
            return None
        if detail:
            return chat.image(image_url, detail=detail)  # type: ignore[arg-type]
        return chat.image(image_url)

    if item_type == "file_url":
        return await _resolve_file_content(
            item=item,
            client=client,
            upload_cache=upload_cache,
            uploaded_file_ids=uploaded_file_ids,
            temporary_files=temporary_files,
            download_fn=download_fn,
        )

    logger.debug("Unhandled content item type for xAI conversion: %s", item_type)
    return chat.text(normalise_text(item))


def build_tool_result(content: Any) -> Any:
    if isinstance(content, (dict, list)):
        try:
            return chat.tool_result(json.dumps(content))
        except TypeError:  # pragma: no cover
            return chat.tool_result(str(content))
    return chat.tool_result(normalise_text(content))


__all__ = [
    "DownloadFn",
    "build_tool_result",
    "convert_content_item",
    "download_file",
    "normalise_text",
]
