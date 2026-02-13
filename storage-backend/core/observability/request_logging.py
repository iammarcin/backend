"""Request logging helpers for HTTP and WebSocket traffic."""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Mapping

from fastapi import FastAPI, Request, WebSocket

_PAYLOAD_PREVIEW_LIMIT = 4096
_SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}
# Paths to skip HTTP request logging (high-frequency internal endpoints)
_QUIET_PATH_PREFIXES = ("/api/v1/proactive-agent/",)
_SENSITIVE_PAYLOAD_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "auth_token",
    "cookie",
    "password",
    "refresh_token",
    "secret",
    "token",
}
_TOKEN_PREVIEW_LENGTH = 12


def _redact_token(token_value: str) -> str:
    """Return a preview of sensitive tokens while hiding the rest."""

    if not isinstance(token_value, str):
        return "***"

    if len(token_value) <= _TOKEN_PREVIEW_LENGTH:
        return "***"

    preview = token_value[:_TOKEN_PREVIEW_LENGTH]
    return f"{preview}***"


def _format_client_address(client: tuple[str, int] | None) -> str:
    if not client:
        return "unknown"
    host, port = client
    return f"{host}:{port}" if port is not None else host


def _format_body_preview(body: bytes) -> str:
    if not body:
        return "<empty>"

    is_truncated = len(body) > _PAYLOAD_PREVIEW_LIMIT
    snippet = body[:_PAYLOAD_PREVIEW_LIMIT]

    try:
        text = snippet.decode("utf-8")
    except UnicodeDecodeError:
        return f"<binary {len(body)} bytes>"

    text = " ".join(text.split())
    if is_truncated:
        return f"{text}… ({len(body)} bytes)"
    return text


def _format_query(query: str) -> str:
    if not query:
        return "<none>"

    lowered = query.lower()
    if "token=" in lowered:
        import urllib.parse

        params = urllib.parse.parse_qs(query, keep_blank_values=True)
        redacted_params: dict[str, list[str]] = {}

        for key, values in params.items():
            if key.lower() in _SENSITIVE_PAYLOAD_KEYS:
                redacted_params[key] = [_redact_token(value) for value in values]
            else:
                redacted_params[key] = values

        return urllib.parse.urlencode(redacted_params, doseq=True)

    return query


def _mask_headers(headers: Iterable[tuple[str, str]]) -> Mapping[str, str]:
    masked: dict[str, str] = {}
    for key, value in headers:
        lower = key.lower()
        if lower in _SENSITIVE_HEADERS:
            masked[key] = "***"
        else:
            masked[key] = value
    return masked


def _redact_payload(value: Any, *, depth: int = 8) -> Any:
    if depth <= 0:
        return "<max depth reached>"

    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str.lower() in _SENSITIVE_PAYLOAD_KEYS:
                redacted[key] = _redact_token(str(item)) if item else "***"
            elif key_str in ("fileNames", "imageLocations") and isinstance(item, list):
                redacted[key] = [
                    (f"{str(x)[:50]}..." if len(str(x)) > 50 else x) for x in item
                ]
            else:
                redacted[key] = _redact_payload(item, depth=depth - 1)
        return redacted

    if isinstance(value, (list, tuple, set)):
        container = list(value) if isinstance(value, set) else value
        return [
            _redact_payload(item, depth=depth - 1) for item in container  # type: ignore[arg-type]
        ]

    return value


def _json_default(value: Any) -> str:
    return repr(value)


def render_payload_preview(payload: Any) -> str:
    """Return a redacted, length-limited preview for debug logging."""

    if payload is None:
        return "<none>"

    if isinstance(payload, bytes):
        return _format_body_preview(payload)

    if isinstance(payload, bytearray):
        return _format_body_preview(bytes(payload))

    if isinstance(payload, str):
        return _format_body_preview(payload.encode("utf-8", errors="ignore"))

    try:
        redacted = _redact_payload(payload)
        serialized = json.dumps(
            redacted,
            default=_json_default,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except Exception:
        serialized = repr(payload)

    return _format_body_preview(serialized.encode("utf-8", errors="ignore"))


def register_http_request_logging(app: FastAPI, *, logger_name: str = "core.http") -> None:
    """Attach middleware that logs every HTTP request."""

    if getattr(app.state, "_http_request_logging_installed", False):  # pragma: no cover - idempotence
        return

    logger = logging.getLogger(logger_name)

    @app.middleware("http")
    async def _log_request(request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        is_quiet = any(path.startswith(prefix) for prefix in _QUIET_PATH_PREFIXES)

        body = await request.body()
        if body:
            request._body = body  # type: ignore[attr-defined]  # Allow downstream handlers to re-read

        if not is_quiet:
            client = request.client
            client_addr = _format_client_address((client.host, client.port) if client else None)
            logger.info("HTTP %s %s from %s", request.method, path, client_addr)

            debug_parts: list[str] = []
            if request.url.query:
                debug_parts.append(f"query={_format_query(request.url.query)}")
            if body:
                debug_parts.append(f"body={render_payload_preview(body)}")

            logger.info(
                "HTTP %s %s payload %s",
                request.method,
                path,
                "; ".join(debug_parts) if debug_parts else "<none>",
            )

        response = await call_next(request)
        return response

    app.state._http_request_logging_installed = True


def log_websocket_request(
    websocket: WebSocket,
    *,
    logger: logging.Logger | None = None,
    label: str | None = None,
) -> None:
    """Log metadata about an inbound WebSocket request."""

    log = logger or logging.getLogger("core.websocket")
    name = label or "WebSocket"
    client = websocket.client
    client_addr = _format_client_address((client.host, client.port) if client else None)
    log.info("%s connection requested for %s from %s", name, websocket.url.path, client_addr)

    debug_parts: list[str] = []
    if websocket.url.query:
        debug_parts.append(f"query={_format_query(websocket.url.query)}")

    headers = _mask_headers(websocket.headers.items())
    if headers:
        debug_parts.append(f"headers={headers}")

    subprotocols = getattr(websocket, "subprotocols", None)
    if subprotocols:
        debug_parts.append(f"subprotocols={list(subprotocols)}")

    if debug_parts:
        log.debug("%s request details: %s", name, "; ".join(debug_parts))


__all__ = ["log_websocket_request", "register_http_request_logging", "render_payload_preview"]
