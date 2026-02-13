"""Manual script to exercise the UFC fighters query end-to-end."""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter

import os

import pytest

from features.db.ufc.dependencies import get_ufc_session
from features.db.ufc.repositories import build_repositories
from features.db.ufc.schemas import FighterSubscriptionParams
from features.db.ufc.service import UfcService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MANUAL_TESTS") != "1",
    reason="Set RUN_MANUAL_TESTS=1 to run UFC database manual tests",
)


@pytest.mark.asyncio
async def test_query(require_ufc_db) -> None:
    """Execute the fighters-with-subscriptions query and log diagnostics."""

    try:
        service = UfcService(repositories=build_repositories(), queue_service=None)

        async for session in get_ufc_session():
            logger.info("Testing fighters query against UFC database")

            params = FighterSubscriptionParams(
                user_id=1,
                page=1,
                page_size=10,
                search=None,
            )
            logger.info("Params: %s", params.model_dump(exclude_none=True))

            start = perf_counter()
            result = await service.list_fighters_with_subscriptions(session, params)
            duration = perf_counter() - start

            logger.info("SUCCESS: Got %s fighters", len(result.items))
            logger.info("Total: %s", result.total)
            if result.items:
                logger.info("First fighter: %s", result.items[0].model_dump())
            logger.info("Elapsed: %.2fs", duration)
            return
    except Exception as exc:  # pragma: no cover - manual diagnostic script
        logger.error("FAILED: %s: %s", type(exc).__name__, exc, exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(test_query())
