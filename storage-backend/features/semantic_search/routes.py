"""FastAPI routes for semantic search administration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ProviderError, ValidationError
from core.pydantic_schemas import error as api_error, ok as api_ok
from features.chat.dependencies import get_chat_session
from features.chat.repositories import ChatMessageRepository, ChatSessionRepository
from features.semantic_search.dependencies import SemanticSearchServiceDep
from features.semantic_search.rate_limiter import get_rate_limiter
from features.semantic_search.repositories import SessionSummaryRepository
from features.semantic_search.services import SessionSummaryService
from features.semantic_search.services.session_indexing_service import SessionIndexingService
from features.semantic_search.services.summary_update_service import SummaryUpdateService
from features.semantic_search.services.summary_health_service import SummaryHealthService
from core.providers.semantic.embeddings import get_cache_stats


router = APIRouter()
semantic_router = APIRouter(prefix="/api/v1/semantic", tags=["semantic"])
admin_router = APIRouter(prefix="/api/v1/admin/summaries", tags=["semantic-admin"])


@semantic_router.get("/health")
async def semantic_health(service: SemanticSearchServiceDep):
    """Return semantic search health, cache, and rate limiter stats."""

    if not service:
        return {"healthy": False, "error": "Semantic search disabled"}

    provider_health = await service.health_check()
    cache_stats = get_cache_stats()
    rate_stats = get_rate_limiter().get_stats()

    return {
        **provider_health,
        "cache": cache_stats,
        "rate_limiter": rate_stats,
    }


def _build_summary_service(db: AsyncSession) -> SessionSummaryService:
    summary_repo = SessionSummaryRepository(db)
    message_repo = ChatMessageRepository(db)
    return SessionSummaryService(summary_repo, message_repo)


def _build_update_service(db: AsyncSession) -> tuple[SummaryUpdateService, SessionIndexingService]:
    summary_repo = SessionSummaryRepository(db)
    session_repo = ChatSessionRepository(db)
    message_repo = ChatMessageRepository(db)
    summary_service = SessionSummaryService(summary_repo, message_repo)
    indexing_service = SessionIndexingService(summary_repo)
    update_service = SummaryUpdateService(
        summary_repo=summary_repo,
        session_repo=session_repo,
        message_repo=message_repo,
        summary_service=summary_service,
        indexing_service=indexing_service,
    )
    return update_service, indexing_service


@admin_router.post("/generate")
async def generate_session_summary(
    session_id: str = Query(..., description="Chat session ID to summarize"),
    db: AsyncSession = Depends(get_chat_session),
):
    """Generate or regenerate a summary for a single session."""

    service = _build_summary_service(db)
    session_repo = ChatSessionRepository(db)
    chat_session = await session_repo.get_by_id(session_id)
    if not chat_session:
        return api_error(404, f"Session {session_id} not found")

    try:
        result = await service.generate_summary_for_session(session_id, chat_session.customer_id)
        await db.commit()
        return api_ok("Summary generated successfully", data={"summary": result})
    except ValidationError as exc:
        await db.rollback()
        return api_error(400, f"Failed to generate summary: {exc}")
    except ProviderError as exc:
        await db.rollback()
        return api_error(502, f"Provider error generating summary: {exc}")
    except Exception as exc:  # pragma: no cover - defensive
        await db.rollback()
        return api_error(500, f"Unexpected error generating summary: {exc}")


@admin_router.get("/{session_id}")
async def get_session_summary(
    session_id: str,
    db: AsyncSession = Depends(get_chat_session),
):
    """Return an existing summary for inspection."""

    service = _build_summary_service(db)
    summary = await service.get_summary_for_session(session_id)
    if not summary:
        return api_error(404, f"No summary found for session {session_id}")
    return api_ok("Summary retrieved", data={"summary": summary})


@admin_router.post("/regenerate")
async def regenerate_summaries(
    session_id: str | None = Query(None, description="Specific session ID to refresh"),
    customer_id: int | None = Query(None, description="Filter batch by customer"),
    limit: int | None = Query(None, description="Max stale sessions to process"),
    batch_size: int = Query(10, description="Concurrent batch size"),
    use_batch: bool = Query(False, description="Use Batch API for 50% cost savings (async, returns job ID)"),
    db: AsyncSession = Depends(get_chat_session),
):
    """Regenerate summaries on demand or via cron.

    When use_batch=true, submits requests to Batch API for 50% cost savings.
    Returns batch_job_id for later retrieval. Results available after batch completes.
    """

    update_service, indexing_service = _build_update_service(db)

    # Batch API mode - submit asynchronously
    if use_batch and not session_id:
        from scripts.backfill_session_summaries_batch import backfill_summaries_batch

        try:
            result = await backfill_summaries_batch(
                customer_id=customer_id,
                limit=limit,
                wait_for_completion=False,
            )
            return api_ok(
                "Batch job submitted (50% cost savings)",
                data={
                    "batch_job_id": result["batch_job_id"],
                    "session_count": result["session_count"],
                    "status": "submitted",
                    "note": "Results will be available after batch completes. Check batch status via /api/v1/batch/{job_id}"
                }
            )
        except Exception as exc:
            return api_error(500, f"Batch submission failed: {exc}")
        finally:
            await indexing_service.close()

    # Standard mode - immediate processing
    try:
        if session_id:
            result = await update_service.regenerate_summary(session_id)
            if result.get("success"):
                await db.commit()
                return api_ok("Summary regenerated", data=result)
            await db.rollback()
            return api_error(500, f"Failed to regenerate summary: {result.get('error')}")

        result = await update_service.auto_update_stale(
            customer_id=customer_id,
            limit=limit,
            batch_size=batch_size,
        )
        await db.commit()
        return api_ok("Batch regeneration complete", data=result)
    except Exception as exc:
        await db.rollback()
        return api_error(500, f"Regeneration failed: {exc}")
    finally:
        await indexing_service.close()


@admin_router.get("/stale")
async def list_stale_summaries(
    customer_id: int | None = Query(None),
    limit: int | None = Query(100, description="Max sessions to list"),
    db: AsyncSession = Depends(get_chat_session),
):
    """List session IDs with stale summaries."""

    update_service, indexing_service = _build_update_service(db)
    try:
        session_ids = await update_service.find_stale_summaries(
            customer_id=customer_id,
            limit=limit,
        )
        return api_ok("Stale summaries retrieved", data={"sessions": session_ids, "count": len(session_ids)})
    finally:
        await indexing_service.close()


@admin_router.get("/health")
async def get_summary_health(
    customer_id: int | None = Query(None),
    db: AsyncSession = Depends(get_chat_session),
):
    """Return summary coverage metrics."""

    summary_repo = SessionSummaryRepository(db)
    health_service = SummaryHealthService(summary_repo)
    metrics = await health_service.get_metrics(customer_id)
    return api_ok("Summary health", data=metrics)


router.include_router(semantic_router)
router.include_router(admin_router)

__all__ = ["router"]
