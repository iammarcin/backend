"""Centralised logging configuration for the BetterAI backend."""
from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Dict

from core.utils.env import get_env

_PATH_TRIM_PREFIXES = ("/app/",)
_ORIGINAL_LOG_RECORD_FACTORY = logging.getLogRecordFactory()
_LOG_RECORD_FACTORY_CONFIGURED = False

_LOGGING_CONFIGURED = False


class _NoBinaryFilter(logging.Filter):
    """Filter Deepgram websocket noise that prints raw binary payloads."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - behaviourally trivial
        return "BINARY" not in record.getMessage()


class _WebsocketConnectionFilter(logging.Filter):
    """Filter specific websocket connection closed messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Check if the message is exactly "connection closed" AND originates from the specific websockets path
        is_connection_closed = record.getMessage() == "connection closed"
        is_websockets_origin = "websockets/legacy/server.py" in record.pathname and record.lineno == 264
        # Return False (filter out) if BOTH conditions are true
        return not (is_connection_closed and is_websockets_origin)


class _WebsocketProtocolFilter(logging.Filter):
    """Filter all websocket protocol-level debug messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        # If the log originates from any websockets module path
        if "websockets" in record.pathname:
            # Only allow WARNING and above (suppress DEBUG and INFO)
            return record.levelno >= logging.WARNING
        return True

class _NoPingPongFilter(logging.Filter):
    """Filter websocket keepalive ping/pong chatter."""

    _BLACKLIST = (
        "% sending keepalive ping",
        "> PING",
        "< PONG",
        "keepalive pong",
    )

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - behaviourally trivial
        message = record.getMessage()
        return not any(token in message for token in self._BLACKLIST)


def _resolve_level(value: str, default: str) -> str:
    value = (value or "").strip().upper()
    if value and getattr(logging, value, None) is not None:
        return value
    return default


def _install_log_record_factory() -> None:
    """Install a log record factory that exposes trimmed paths."""

    global _LOG_RECORD_FACTORY_CONFIGURED
    if _LOG_RECORD_FACTORY_CONFIGURED:
        return

    def factory(*args, **kwargs):
        record = _ORIGINAL_LOG_RECORD_FACTORY(*args, **kwargs)
        pathname = getattr(record, "pathname", "") or ""
        for prefix in _PATH_TRIM_PREFIXES:
            if pathname.startswith(prefix):
                record.shortpathname = pathname[len(prefix):]
                break
        else:
            record.shortpathname = pathname
        return record

    logging.setLogRecordFactory(factory)
    _LOG_RECORD_FACTORY_CONFIGURED = True


def setup_logging(force: bool = False) -> None:
    """Configure root/application loggers for both console and file output."""

    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED and not force:
        return

    node_env = get_env("NODE_ENV")
    inside_docker = bool(node_env)

    log_level = _resolve_level(get_env("BACKEND_LOG_LEVEL", default="INFO"), "INFO")
    console_level = _resolve_level(
        get_env("BACKEND_LOG_CONSOLE_LEVEL", default=log_level), log_level
    )
    file_level = _resolve_level(get_env("BACKEND_LOG_FILE_LEVEL", default=log_level), log_level)

    handlers: Dict[str, object] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": console_level,
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
    }
    root_handlers = ["console"]
    uvicorn_handlers = ["console"]

    if inside_docker:
        log_dir = Path(get_env("BACKEND_LOG_DIR", default="/storage/logs") or "/storage/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / (get_env("BACKEND_LOG_FILE", default="backend.log") or "backend.log")
        handlers["file"] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": file_level,
            "formatter": "standard",
            "filename": str(log_file),
            "when": "midnight",
            "backupCount": int(get_env("BACKEND_LOG_RETENTION", default="7") or "7"),
            "encoding": "utf-8",
        }
        root_handlers.append("file")
        uvicorn_handlers = ["console", "file"]

    use_milliseconds = (
        (get_env("BACKEND_LOG_TIME_MS", default="false") or "false").lower()
        in {"1", "true", "yes", "on"}
    )
    location_fmt = "%(shortpathname)s:%(lineno)d"
    if use_milliseconds:
        fmt = "%(asctime)s.%(msecs)03d %(levelname)s [{location}] - %(message)s".format(location=location_fmt)
    else:
        fmt = "%(asctime)s %(levelname)s [{location}] - %(message)s".format(location=location_fmt)
    datefmt = "%Y-%m-%d %H:%M:%S"

    access_level = _resolve_level(get_env("BACKEND_ACCESS_LOG_LEVEL"), log_level)

    config: Dict[str, object] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": fmt,
                "datefmt": datefmt,
            },
        },
        "handlers": handlers,
        "root": {
            "level": log_level,
            "handlers": root_handlers,
        },
        "loggers": {
            "uvicorn": {
                "level": "CRITICAL",
                "handlers": uvicorn_handlers,
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "CRITICAL",
                "handlers": uvicorn_handlers,
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "CRITICAL",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    _install_log_record_factory()

    logging.config.dictConfig(config)
    logging.captureWarnings(True)

    # Apply filters to suppress noisy websocket chatter
    for name in (
        "websockets",
        "websockets.client",
        "websockets.server",
        "websockets.protocol",
        "websockets.legacy",
        "websockets.legacy.client",
        "websockets.legacy.server",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Suppress debug logs from third-party libraries
    # Keep openai, anthropic at DEBUG - they're core functionality
    # Suppress google and grpc logs as they are noisy
    for name in (
        # Image processing
        "PIL",
        "PIL.PngImagePlugin",
        "PIL.Image",
        # HTTP clients
        "httpcore",
        "httpcore.http11",
        "httpcore.connection",
        "httpx",
        "urllib3",
        "urllib3.connectionpool",
        "requests",
        "requests_oauthlib",
        "oauthlib",
        # AWS SDKs
        "botocore",
        "botocore.credentials",
        "botocore.httpsession",
        "botocore.hooks",
        "botocore.parsers",
        "boto3",
        "aioboto3",
        "s3transfer",
        # Database
        "aiomysql",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "aiosqlite",
        # Utilities
        # Multipart form parsing (python-multipart)
        "multipart",
        "python_multipart",
        "python_multipart.multipart",
        "h11",
        # Openai
        "openai",
        "openai._base_client",
        "anthropic",
        "anthropic._base_client",
        # Suppress noisy external packages
        "grpc",
        "google",
        "google.genai"
    ):
        if name in ("google", "google.genai"):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        else:
            logging.getLogger(name).setLevel(logging.WARNING)

    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.addFilter(_NoBinaryFilter())
    uvicorn_error_logger.addFilter(_NoPingPongFilter())
    uvicorn_error_logger.addFilter(_WebsocketConnectionFilter())
    uvicorn_error_logger.addFilter(_WebsocketProtocolFilter())

    logging.getLogger("h11").addFilter(_NoBinaryFilter())

    _LOGGING_CONFIGURED = True


__all__ = ["setup_logging"]
