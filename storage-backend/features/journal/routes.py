"""FastAPI routes for journal feature."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.pydantic_schemas import ok as api_ok
from features.journal.dependencies import get_journal_session
from features.journal.repository import JournalRepository
from features.journal.service import JournalService
from features.journal.schemas import ImageDescriptionUpdate, JournalResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/journal", tags=["journal"])

# Production and non-prod journal session IDs
JOURNAL_SESSIONS = {
    "prod": "35e97867-0ab3-4257-80c6-0767fbeb3edd",
    "non-prod": "7ce7538e-4fdb-405d-bf14-ef0dc88fbba3",
}


def _get_service(db: AsyncSession) -> JournalService:
    repository = JournalRepository(db)
    return JournalService(repository)


@router.get("/entries")
async def get_journal_entries(
    session_id: Optional[str] = Query(
        None, description="Journal session ID (defaults to prod session)"
    ),
    env: str = Query("prod", description="Environment: 'prod' or 'non-prod'"),
    target_date: Optional[str] = Query(
        None, description="Specific date (YYYY-MM-DD). If not provided, returns today status."
    ),
    entry_type: Optional[str] = Query(
        None, description="Filter by entry type: 'sleep' or 'meals'"
    ),
    days: int = Query(7, ge=1, le=30, description="Number of days for sleep/meals history"),
    db: AsyncSession = Depends(get_journal_session),
) -> dict:
    """
    Get journal entries for Sherlock.

    Default behavior (no params): Returns today's sleep + yesterday's meals.
    With target_date: Returns all entries for that specific date.
    With entry_type='sleep': Returns sleep entries from last N days.
    With entry_type='meals': Returns meal entries from last N days.
    """
    # Resolve session ID
    resolved_session_id = session_id or JOURNAL_SESSIONS.get(env, JOURNAL_SESSIONS["prod"])

    service = _get_service(db)

    try:
        if target_date:
            # Specific date query
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            result = await service.get_entries_for_date(resolved_session_id, parsed_date)
        elif entry_type == "sleep":
            result = await service.get_sleep_entries(resolved_session_id, days)
        elif entry_type == "meals":
            result = await service.get_meals_entries(resolved_session_id, days)
        else:
            # Default: today's status
            result = await service.get_today_status(resolved_session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    try:
        return api_ok("Journal entries retrieved", data=result.model_dump())
    except Exception as e:
        logger.exception(f"Error serializing result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/needs-description")
async def get_messages_needing_description(
    session_id: Optional[str] = Query(None),
    env: str = Query("prod"),
    limit: int = Query(50, ge=1, le=100),
    force: bool = Query(False, description="If true, return all messages with images regardless of existing description"),
    db: AsyncSession = Depends(get_journal_session),
) -> dict:
    """Get messages with images that need descriptions (for cron job)."""
    resolved_session_id = session_id or JOURNAL_SESSIONS.get(env, JOURNAL_SESSIONS["prod"])
    service = _get_service(db)
    try:
        result = await service.get_messages_needing_description(resolved_session_id, limit, force)
        return api_ok("Messages needing description retrieved", data=result)
    except Exception as e:
        logger.exception(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/message/{message_id}")
async def get_message_by_id(
    message_id: int,
    db: AsyncSession = Depends(get_journal_session),
) -> dict:
    """Get a single message by ID (for testing image description)."""
    service = _get_service(db)
    try:
        result = await service.get_message_by_id(message_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")
        return api_ok("Message retrieved", data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image-description")
async def update_image_description(
    request: ImageDescriptionUpdate,
    db: AsyncSession = Depends(get_journal_session),
) -> dict:
    """Update image description for a message (called by cron job)."""
    service = _get_service(db)
    try:
        success = await service.update_image_description(
            request.message_id, request.image_description
        )
        return api_ok("Image description updated", data={"success": success, "message_id": request.message_id})
    except Exception as e:
        logger.exception(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
