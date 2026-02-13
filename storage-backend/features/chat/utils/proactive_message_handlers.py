"""Message handlers for proactive WebSocket connections.

Re-exports handlers from split modules for backward compatibility.
"""

from .proactive_sync_handler import handle_sync_request
from .proactive_send_handler import handle_send_message

__all__ = ["handle_sync_request", "handle_send_message"]
