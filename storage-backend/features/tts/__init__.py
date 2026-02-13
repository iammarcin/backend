"""Package initialisation for text-to-speech feature."""

from .routes import router
from .service import TTSService
from .websocket import websocket_router

__all__ = ["router", "websocket_router", "TTSService"]
