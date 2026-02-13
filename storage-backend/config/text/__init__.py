"""Text generation configuration aggregation."""

from .defaults import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    MAX_RETRIES,
    RETRY_DELAY,
    STREAM_CHUNK_SIZE,
    STREAM_TIMEOUT,
)


def __getattr__(name: str):
    """Lazy import to avoid circular imports."""
    if name == "MODEL_CONFIGS":
        from .providers import MODEL_CONFIGS
        return MODEL_CONFIGS
    if name == "providers":
        from . import providers
        return providers
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TOP_P",
    "MAX_RETRIES",
    "RETRY_DELAY",
    "STREAM_CHUNK_SIZE",
    "STREAM_TIMEOUT",
    "providers",
]
