"""Deep research handler for proactive agent.

Executes deep research workflow and pushes events via proactive connection
registry. Always runs asynchronously (non-blocking) to allow conversation to continue.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config.proactive_agent import (
    DEFAULT_PRIMARY_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_RESEARCH_MODEL,
    ESTIMATED_RESEARCH_TIME_SECONDS,
    MAX_CONCURRENT_JOBS_PER_USER,
    RESEARCH_RESULTS_DIR,
)
from core.connections import get_proactive_registry, get_server_id
from features.proactive_agent.repositories import ProactiveAgentRepository
from features.proactive_agent.schemas import DeepResearchRequest
from features.proactive_agent.services.streaming_adapter import (
    ProactiveStreamingAdapter,
    can_start_job,
    register_job,
    slugify,
    unregister_job,
)

logger = logging.getLogger(__name__)


class DeepResearchHandler:
    """Handles deep research requests from proactive agents.

    Always runs asynchronously - returns immediately and runs research in background.
    Results are saved to file and user is notified via WebSocket when complete.
    """

    def __init__(self, repository: ProactiveAgentRepository) -> None:
        self._repository = repository

    async def execute_research(
        self,
        request: DeepResearchRequest,
    ) -> dict[str, Any]:
        """Execute deep research asynchronously.

        Returns immediately with job_id. Background task runs research,
        saves result to file, and notifies via WebSocket on completion.
        """
        # Check rate limit
        if not can_start_job(request.user_id):
            return {
                "success": False,
                "error": f"Max {MAX_CONCURRENT_JOBS_PER_USER} concurrent jobs allowed",
                "server_id": get_server_id(),
            }

        # Generate job ID and file path
        job_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = slugify(request.query)
        filename = f"{timestamp}_{slug}.md"
        file_path = RESEARCH_RESULTS_DIR / filename

        # Ensure directory exists
        RESEARCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        # Register job
        register_job(request.user_id, job_id)

        # Spawn background task
        asyncio.create_task(
            self._run_research(
                request=request,
                job_id=job_id,
                file_path=file_path,
            )
        )

        logger.info(
            "Deep research started job_id=%s user=%s query=%s",
            job_id,
            request.user_id,
            request.query[:50],
        )

        return {
            "success": True,
            "job_id": job_id,
            "status": "started",
            "file_path": str(file_path),
            "estimated_time_seconds": ESTIMATED_RESEARCH_TIME_SECONDS,
            "message": f"Research started. Results will be saved to {filename}",
            "server_id": get_server_id(),
        }

    async def _run_research(
        self,
        request: DeepResearchRequest,
        job_id: str,
        file_path: Path,
    ) -> None:
        """Background task: run research, save file, notify via WebSocket."""
        start_time = time.time()
        registry = get_proactive_registry()

        try:
            # Create adapter to collect chunks
            adapter = ProactiveStreamingAdapter(request.user_id, request.session_id)

            # Build settings and prompt
            settings = self._build_research_settings(request.reasoning_effort)
            prompt = [{"type": "text", "text": request.query}]
            customer_id = request.customer_id or request.user_id

            # Import and run workflow
            from features.chat.services.streaming.deep_research import (
                stream_deep_research_response,
            )

            outcome = await stream_deep_research_response(
                prompt=prompt,
                settings=settings,
                customer_id=customer_id,
                manager=adapter,  # type: ignore[arg-type]
                session_id=request.session_id,
            )

            # Collect result text from adapter
            result_text = adapter.get_collected_text()
            duration = time.time() - start_time

            # Write markdown file
            self._write_research_file(
                file_path=file_path,
                query=request.query,
                result_text=result_text,
                citations=outcome.citations,
                stage_timings=outcome.stage_timings,
            )

            logger.info(
                "Deep research completed job_id=%s file=%s citations=%d duration=%.1fs",
                job_id,
                file_path.name,
                len(outcome.citations),
                duration,
            )

            # Push completion notification
            await registry.push_to_user(
                user_id=request.user_id,
                message={
                    "type": "custom_event",
                    "event_type": "deepResearch",
                    "content": {
                        "type": "deepResearchCompleted",
                        "job_id": job_id,
                        "query": request.query,
                        "file_path": str(file_path),
                        "citations_count": len(outcome.citations),
                        "duration_seconds": int(duration),
                    },
                    "session_id": request.session_id,
                },
                session_scoped=False,
            )

        except Exception as exc:
            duration = time.time() - start_time
            error_message = str(exc)
            logger.error(
                "Deep research failed job_id=%s: %s",
                job_id,
                error_message,
                exc_info=True,
            )

            # Push error notification
            await registry.push_to_user(
                user_id=request.user_id,
                message={
                    "type": "custom_event",
                    "event_type": "deepResearch",
                    "content": {
                        "type": "deepResearchError",
                        "job_id": job_id,
                        "query": request.query,
                        "error": error_message,
                        "duration_seconds": int(duration),
                    },
                    "session_id": request.session_id,
                },
                session_scoped=False,
            )

        finally:
            unregister_job(request.user_id, job_id)

    def _write_research_file(
        self,
        file_path: Path,
        query: str,
        result_text: str,
        citations: List[Dict[str, Any]],
        stage_timings: Dict[str, float],
    ) -> None:
        """Write research results to markdown file."""
        content_parts = [
            f"# Research: {query}",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Stage Timings:** {stage_timings}",
            "",
            "---",
            "",
            "## Findings",
            "",
            result_text,
            "",
        ]

        if citations:
            content_parts.extend([
                "---",
                "",
                "## Citations",
                "",
            ])
            for i, citation in enumerate(citations, 1):
                url = citation.get("url", "N/A")
                content_parts.append(f"{i}. {url}")

        content = "\n".join(content_parts)
        file_path.write_text(content, encoding="utf-8")

    def _build_research_settings(self, reasoning_effort: str | None) -> Dict[str, Any]:
        """Build settings dict for deep research workflow.

        Uses DEFAULT_REASONING_EFFORT (env-based: low for non-prod, medium for prod)
        when reasoning_effort is not provided.
        """
        effort = reasoning_effort or DEFAULT_REASONING_EFFORT
        return {
            "text": {
                "model": DEFAULT_PRIMARY_MODEL,
                "deep_research_enabled": True,
                "deep_research_model": DEFAULT_RESEARCH_MODEL,
                "deep_research_reasoning_effort": effort,
            },
            "general": {
                "ai_agent_enabled": False,
            },
        }


__all__ = [
    "DeepResearchHandler",
    "DEFAULT_REASONING_EFFORT",
    "RESEARCH_RESULTS_DIR",
]
