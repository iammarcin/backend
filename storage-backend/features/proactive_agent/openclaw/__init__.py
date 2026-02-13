"""OpenClaw Gateway integration module.

This module provides a WebSocket client for communicating with
OpenClaw Gateway, enabling the Sherlock character to use OpenClaw
instead of Claude Code SDK.

Components:
- client.py: WebSocket client for gateway communication
- auth.py: Device authentication and signature generation
- adapter.py: Chat message adapter
- config.py: Configuration loading
- session.py: Shared connection management
- router.py: Message routing
"""

from .adapter import OpenClawAdapter
from .stream_types import StreamContext
from .auth import DeviceAuth
from .client import OpenClawClient
from .exceptions import (
    OpenClawError,
    ProtocolError,
    RequestError,
)
from .config import OpenClawConfig, get_openclaw_config, is_openclaw_enabled
from .router import (
    send_message_to_openclaw,
    abort_openclaw_stream,
)
from .session import (
    OpenClawSessionManager,
    get_openclaw_session_manager,
    close_openclaw_session,
)

__all__ = [
    # Auth
    "DeviceAuth",
    # Adapter
    "OpenClawAdapter",
    "StreamContext",
    # Client
    "OpenClawClient",
    "OpenClawError",
    "ProtocolError",
    "RequestError",
    # Config
    "OpenClawConfig",
    "get_openclaw_config",
    "is_openclaw_enabled",
    # Router
    "send_message_to_openclaw",
    "abort_openclaw_stream",
    # Session
    "OpenClawSessionManager",
    "get_openclaw_session_manager",
    "close_openclaw_session",
]
