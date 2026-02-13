from __future__ import annotations

"""BetterAI Backend v2 - Main Application Entry Point
This is the FastAPI application factory for the BetterAI multi-provider AI backend.
Architecture Overview:
    - Multi-provider AI system supporting text, image, video, audio, and realtime generation
    - Feature-based modular architecture (see features/ directory)
    - Provider registry pattern for dynamic AI model resolution
    - WebSocket-based streaming for real-time communication
    - Four separate MySQL databases (main, Garmin, blood, UFC)
Entry Points:
    - /health - Health check endpoint
    - /chat/ws - Main chat WebSocket (routes to standard or realtime)
    - /api/v1/* - RESTful API endpoints for various features
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from core.utils.env import is_production
# Track startup time in non-production environments
start_time = time.time() if not is_production() else None

import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.auth import AuthenticationError
from core.clients.semantic import close_qdrant_client
from core.exceptions import ConfigurationError
from core.logging import setup_logging
from core.observability import register_http_request_logging
from core.pydantic_schemas import error as api_error
from features.admin.routes import router as admin_router
from features.audio.routes import router as audio_router
from features.batch.routes import router as batch_router
from features.chat.routes import router as chat_router
from features.db.blood.routes import router as blood_router
from features.db.ufc.routes import router as ufc_router
from features.image.routes import router as image_router
from features.legacy_compat import router as legacy_compat_router
from features.realtime.routes import (
    router as realtime_router,
    websocket_router as realtime_websocket_router,
)
from features.storage import router as storage_router
from features.tts import router as tts_router
from features.tts import websocket_router as tts_websocket_router
from features.video.routes import router as video_router
from features.semantic_search.routes import router as semantic_router
from features.automation.routes import router as automation_router
from features.proactive_agent.routes import router as proactive_agent_router
from features.journal.routes import router as journal_router
from features.cc4life.routes import router as cc4life_router

# Only import Garmin in production to speed up dev reloads
from features.garmin.routes import router as garmin_router

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan - startup and shutdown events."""
    # Startup
    yield
    # Shutdown
    logger.info("Application shutting down...")
    await close_qdrant_client()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Application factory returning a configured FastAPI instance."""

    app = FastAPI(
        title="BetterAI Backend v2",
        description="Refactored FastAPI backend with clean architecture",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Database session dependencies from ``infrastructure.db.mysql`` will be
    # integrated alongside the forthcoming Garmin and UFC feature routers.

    # Configure CORS based on environment
    if is_production():
        # Production: Allow all origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Development: Allow all localhost origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:9003",
                "http://127.0.0.1:9003",
            ],
            # Allow any localhost port in dev (React/Vite/etc.)
            allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(request: Request, exc: AuthenticationError):
        """Return a structured 401 envelope for authentication failures."""

        payload = api_error(
            code=exc.code,
            message=exc.message,
            data={"reason": exc.reason} if exc.reason else None,
        )
        return JSONResponse(
            status_code=exc.code,
            content=payload,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(request: Request, exc: ConfigurationError):
        """Return a structured API envelope for configuration errors."""

        payload = api_error(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(exc),
            data={"key": exc.key} if getattr(exc, "key", None) else None,
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy", "version": "2.0.0"}

    register_http_request_logging(app)

    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(legacy_compat_router)  # Legacy compatibility for old mobile app
    app.include_router(chat_router)
    app.include_router(audio_router)
    app.include_router(image_router)
    app.include_router(storage_router)
    app.include_router(video_router)
    app.include_router(garmin_router)
    app.include_router(blood_router)
    app.include_router(ufc_router)
    app.include_router(tts_router)
    app.include_router(tts_websocket_router)
    app.include_router(realtime_router)
    app.include_router(realtime_websocket_router)
    app.include_router(semantic_router)
    app.include_router(batch_router)
    app.include_router(automation_router)
    app.include_router(proactive_agent_router)
    app.include_router(journal_router)
    app.include_router(cc4life_router)

    # Build status message
    routers_list = "chat, audio, image, video, Garmin, Blood, UFC, TTS, realtime, semantic, batch, automation, and proactive-agent routers"

    # Add timing info for non-production
    timing_info = ""
    if start_time is not None:
        elapsed = time.time() - start_time
        timing_info = f" (loaded in {elapsed:.2f}s)"

    logger.info(f"Application created with {routers_list}{timing_info}")
    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
