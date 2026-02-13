"""Chart generation handler for proactive agent.

Generates charts and pushes them to connected WebSocket clients via the
proactive connection registry. Reuses existing chart infrastructure.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.connections import get_proactive_registry, get_server_id
from core.exceptions import NotFoundError
from core.pydantic_schemas import (
    ChartData,
    ChartOptions,
    ChartPayload,
    ChartToolInput,
    ChartType,
    DataSource,
)
from features.proactive_agent.chart_accumulator import add_chart
from features.proactive_agent.repositories import ProactiveAgentRepository
from features.proactive_agent.schemas import ChartGenerationRequest
from infrastructure.db.fetchers import get_data_fetcher

logger = logging.getLogger(__name__)


class ChartHandler:
    """Handles chart generation requests from proactive agents."""

    def __init__(self, repository: ProactiveAgentRepository) -> None:
        self._repository = repository

    async def generate_chart(
        self,
        request: ChartGenerationRequest,
    ) -> dict[str, Any]:
        """Generate a chart and push it via WebSocket.

        Returns result dict with chart_id and push status.
        """
        # Validate session exists
        session = await self._repository.get_session_by_id(request.session_id)
        if not session:
            raise NotFoundError(f"Session {request.session_id} not found")

        registry = get_proactive_registry()

        # Emit chartGenerationStarted
        await registry.push_to_user(
            request.user_id,
            {
                "type": "custom_event",
                "event_type": "chartGenerationStarted",
                "session_id": request.session_id,
                "content": {
                    "chart_type": request.chart_type.value,
                    "title": request.title,
                },
            },
        )

        try:
            # Build chart payload
            payload = await self._build_chart_payload(request)

            # Push chartGenerated event for real-time display
            chart_payload_dict = payload.model_dump(mode="json")
            pushed = await registry.push_to_user(
                request.user_id,
                {
                    "type": "custom_event",
                    "event_type": "chartGenerated",
                    "session_id": request.session_id,
                    "content": chart_payload_dict,
                },
            )

            # Add to accumulator - will be saved with final message at stream_end
            # This ensures chart is part of the main response, not a separate message
            add_chart(request.session_id, chart_payload_dict)

            logger.info(
                "Chart generated for user=%s session=%s chart_id=%s pushed_ws=%s (accumulated for final message)",
                request.user_id,
                request.session_id[:8],
                payload.chart_id,
                pushed,
            )

            return {
                "success": True,
                "chart_id": payload.chart_id,
                "chart_type": payload.chart_type.value,
                "title": payload.title,
                "pushed_via_ws": pushed,
                "server_id": get_server_id(),
            }

        except Exception as exc:
            error_message = str(exc)
            logger.error(
                "Chart generation failed for user=%s: %s",
                request.user_id,
                error_message,
                exc_info=True,
            )

            # Push chartError event
            await registry.push_to_user(
                request.user_id,
                {
                    "type": "custom_event",
                    "event_type": "chartError",
                    "session_id": request.session_id,
                    "content": {
                        "error": error_message,
                        "chart_type": request.chart_type.value,
                        "title": request.title,
                    },
                },
            )

            return {
                "success": False,
                "error": error_message,
                "server_id": get_server_id(),
            }

    async def _build_chart_payload(
        self,
        request: ChartGenerationRequest,
    ) -> ChartPayload:
        """Build ChartPayload from request, fetching data if needed."""
        chart_data: Optional[ChartData] = request.data
        data_source: Optional[DataSource] = None

        if request.chart_type == ChartType.MERMAID:
            # Mermaid chart - no data needed
            data_source = None
        elif request.data_query:
            # Fetch data from database
            data_source = request.data_query.source
            fetcher = get_data_fetcher(data_source)
            chart_data = await fetcher.fetch(request.data_query)
        elif request.data:
            # Use provided data directly
            data_source = DataSource.GENERATED
        else:
            raise ValueError("No data source provided")

        options = request.options or ChartOptions()

        # Build payload with optional custom chart_id for inline placement
        payload_kwargs = {
            "chart_type": request.chart_type,
            "title": request.title,
            "subtitle": request.subtitle,
            "data": chart_data,
            "mermaid_code": request.mermaid_code,
            "options": options,
            "data_source": data_source,
        }
        # Use custom chart_id if provided (for inline [CHART:id] markers)
        if request.chart_id:
            payload_kwargs["chart_id"] = request.chart_id

        return ChartPayload(**payload_kwargs)


__all__ = ["ChartHandler"]
