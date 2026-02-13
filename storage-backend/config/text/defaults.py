"""Cross-provider text generation defaults."""

# Global text generation defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TOP_P = 0.95

# Streaming defaults
STREAM_CHUNK_SIZE = 1024  # bytes
STREAM_TIMEOUT = 300  # seconds

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

__all__ = [
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TOP_P",
    "STREAM_CHUNK_SIZE",
    "STREAM_TIMEOUT",
    "MAX_RETRIES",
    "RETRY_DELAY",
]
