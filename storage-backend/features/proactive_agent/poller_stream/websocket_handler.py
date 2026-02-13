"""WebSocket endpoint for poller NDJSON streaming.

This module handles WebSocket connections from the Python poller,
receiving raw NDJSON lines from Claude CLI and queuing them for processing.

Protocol:
1. Poller connects with API key (header or query param)
2. Poller sends init message with session context
3. Poller streams NDJSON lines from Claude
4. Poller sends complete or error message
5. Connection closes
"""

import logging
from typing import Optional

from fastapi import APIRouter, Header, Query, WebSocket, WebSocketDisconnect

from config.proactive_agent import INTERNAL_API_KEY

from .event_emitter import EventEmitter
from .heartbeat_emitter import HeartbeatEmitter
from .schemas import InitMessage
from .stream_session import PollerStreamSession  # Re-exported for backwards compatibility

from ..dependencies import get_db_session_direct

# Re-export PollerStreamSession for backwards compatibility
__all__ = ["router", "PollerStreamSession"]
from ..repositories import ProactiveAgentRepository
from ..services.chart_handler import ChartHandler
from ..services.deep_research_handler import DeepResearchHandler
from .tts_helpers import build_tts_handlers

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/poller-stream")
async def poller_stream_websocket(
    websocket: WebSocket,
    x_internal_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None),
) -> None:
    """WebSocket endpoint for poller NDJSON streaming."""
    # Validate API key
    provided_key = x_internal_api_key or api_key
    if provided_key != INTERNAL_API_KEY:
        await websocket.close(code=4001, reason="Invalid API key")
        return

    await websocket.accept()
    logger.info("Poller stream connection accepted")

    try:
        # Wait for init message
        init_data = await websocket.receive_text()
        init_msg = InitMessage.model_validate_json(init_data)

        logger.info(
            f"Poller stream initialized: user={init_msg.user_id} "
            f"session={init_msg.session_id} character={init_msg.ai_character_name}"
        )

        # Create dependencies and session within DB context
        async with get_db_session_direct() as db:
            repository = ProactiveAgentRepository(db)

            # Heartbeat mode: silent accumulation, no frontend streaming
            if init_msg.source == "heartbeat":
                emitter = HeartbeatEmitter(
                    init_data=init_msg,
                    repository=repository,
                )
            else:
                # Normal mode: full streaming with TTS, charts, research
                chart_handler = ChartHandler(repository)
                research_handler = DeepResearchHandler(repository)
                start_tts, complete_tts, cancel_tts = build_tts_handlers(repository)

                emitter = EventEmitter(
                    init_data=init_msg,
                    repository=repository,
                    chart_handler=chart_handler,
                    research_handler=research_handler,
                    create_message_func=repository.create_message,
                    start_tts_func=start_tts,
                    complete_tts_func=complete_tts,
                    cancel_tts_func=cancel_tts,
                )

            session = PollerStreamSession(websocket, init_msg, emitter)
            await session.run()

    except WebSocketDisconnect:
        logger.info("Poller disconnected before init")
    except Exception as e:
        logger.exception("Poller stream error")
        try:
            await websocket.close(code=1011, reason=str(e)[:100])
        except Exception:
            pass
