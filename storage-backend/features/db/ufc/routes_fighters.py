"""Fighter management endpoints for the UFC feature.

The handlers defined here manage fighter creation, queueing, and updates.
They encapsulate logging, response formatting, and common error handling so
that each endpoint focuses on orchestrating the service layer call.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConfigurationError, DatabaseError, ServiceError, ValidationError
from core.pydantic_schemas import error as api_error, ok as api_ok

from .dependencies import get_ufc_service, get_ufc_session
from .responses import (
    configuration_error_response,
    database_error_response,
    service_error_response,
    validation_error_response,
)
from .schemas import (
    CreateFighterRequest,
    FighterListData,
    FighterListEnvelope,
    FighterListQueryParams,
    FighterMutationEnvelope,
    FighterQueueEnvelope,
    FighterQueueRequest,
    UfcErrorResponse,
    UpdateFighterRequest,
)
from .service import UfcService

logger = logging.getLogger(__name__)


def register_fighter_routes(router: APIRouter) -> None:
    """Attach fighter-related endpoints to ``router``."""

    @router.get(
        "/fighters",
        summary="List fighters with subscription status",
        response_model=FighterListEnvelope,
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": UfcErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def list_fighters_endpoint(
        query: FighterListQueryParams = Depends(),
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Return fighters enriched with the caller's subscription flag."""

        logger.info(
            "List fighters request received",
            extra={"user_id": query.user_id, "search": query.search, "page": query.page},
        )
        logger.debug("Query params resolved", extra={"params": query.model_dump(exclude_none=True)})

        try:
            logger.debug("Calling service.list_fighters_with_subscriptions")
            params = query.to_service_params()
            logger.debug("Service params prepared", extra={"params": params.model_dump(exclude_none=True)})
            result = await service.list_fighters_with_subscriptions(session, params)
            logger.debug(
                "Service returned fighters",
                extra={
                    "count": len(result.items),
                    "total": result.total,
                    "has_more": result.has_more,
                },
            )
        except ValidationError as exc:
            logger.error("Validation error while listing fighters", exc_info=True)
            return validation_error_response(exc)
        except DatabaseError as exc:
            logger.error("Database error while listing fighters", exc_info=True)
            return database_error_response(exc)
        except Exception as exc:  # pragma: no cover - unexpected safeguard
            logger.error("Unexpected error in list_fighters_endpoint", exc_info=True)
            return api_error(
                code=500,
                message="An unexpected error occurred",
                data={"errors": [{"message": str(exc)}]},
            )

        data = FighterListData(
            fighters=result.items,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            has_more=result.has_more,
            search=result.search,
            subscriptions_enabled=result.subscriptions_enabled,
        )

        meta = {
            "total": result.total,
            "page": result.page,
            "pageSize": result.page_size,
            "hasMore": result.has_more,
        }
        if result.search:
            meta["search"] = result.search
        if result.subscriptions_enabled is not None:
            meta["subscriptionsEnabled"] = result.subscriptions_enabled

        return api_ok(
            message=f"Retrieved {len(data.fighters)} fighters",
            data=data.model_dump(mode="json", by_alias=True, exclude_none=True),
            meta=meta,
        )

    @router.post(
        "/fighters",
        summary="Create a UFC fighter",
        response_model=FighterMutationEnvelope,
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": UfcErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def create_fighter_endpoint(
        payload: CreateFighterRequest,
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Create a fighter record while preventing duplicates."""

        logger.info("Create fighter request received", extra={"name": payload.name})

        try:
            result = await service.create_fighter(session, payload)
        except ValidationError as exc:
            return validation_error_response(exc)
        except DatabaseError as exc:
            return database_error_response(exc)

        meta = {"status": result.status, "changed": result.changed}
        data = result.model_dump(mode="json", exclude_none=True)
        return api_ok(message=result.message, data=data, meta=meta)

    @router.post(
        "/fighters/queue",
        summary="Queue a fighter candidate for downstream processing",
        response_model=FighterQueueEnvelope,
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": UfcErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def enqueue_fighter_candidate_endpoint(
        payload: FighterQueueRequest,
        service: UfcService = Depends(get_ufc_service),
    ):
        """Enqueue fighter metadata for asynchronous enrichment."""

        logger.info("Queue fighter candidate request", extra={"full_name": payload.full_name})

        try:
            logger.debug(
                "Enqueue fighter candidate payload",
                extra={"payload": payload.model_dump(exclude_none=True)},
            )
            result = await service.enqueue_fighter_candidate(payload)
        except ValidationError as exc:
            logger.error("Validation error queueing fighter", exc_info=True)
            return validation_error_response(exc)
        except ConfigurationError as exc:
            logger.error("Configuration error queueing fighter", exc_info=True)
            return configuration_error_response(exc)
        except ServiceError as exc:
            logger.error("Service error queueing fighter", exc_info=True)
            return service_error_response(exc)
        except Exception as exc:  # pragma: no cover - unexpected safeguard
            logger.error("Unexpected error queueing fighter", exc_info=True)
            return api_error(
                code=500,
                message="An unexpected error occurred",
                data={"errors": [{"message": str(exc)}]},
            )

        data = result.model_dump(mode="json", exclude_none=True)
        meta = {"queue_url": result.queue_url, "message_id": result.message_id}
        return api_ok(message=result.message, data=data, meta=meta)

    @router.patch(
        "/fighters/{fighter_id}",
        summary="Update a UFC fighter",
        response_model=FighterMutationEnvelope,
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": UfcErrorResponse},
            status.HTTP_404_NOT_FOUND: {"model": UfcErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": UfcErrorResponse},
        },
    )
    async def update_fighter_endpoint(
        fighter_id: int,
        payload: UpdateFighterRequest,
        session: AsyncSession = Depends(get_ufc_session),
        service: UfcService = Depends(get_ufc_service),
    ):
        """Update mutable fighter attributes."""

        logger.info("Update fighter request received", extra={"fighter_id": fighter_id})

        try:
            result = await service.update_fighter(session, fighter_id, payload)
        except ValidationError as exc:
            status_code = (
                status.HTTP_404_NOT_FOUND if exc.field == "fighter_id" else status.HTTP_400_BAD_REQUEST
            )
            return validation_error_response(exc, status_code=status_code)
        except DatabaseError as exc:
            return database_error_response(exc)

        data = result.model_dump(mode="json", exclude_none=True)
        meta = {"status": result.status, "changed": result.changed}
        return api_ok(message=result.message, data=data, meta=meta)


__all__ = ["register_fighter_routes"]

