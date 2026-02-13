from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from features.semantic_search.services.summary_update_service import SummaryUpdateService


@pytest.mark.asyncio
async def test_auto_update_stale_triggers_batch(monkeypatch):
    service = SummaryUpdateService.__new__(SummaryUpdateService)
    service.find_stale_summaries = AsyncMock(return_value=["s1", "s2", "s3"])
    service.regenerate_batch = AsyncMock(return_value={"regenerated": 3, "failed": 0})

    result = await SummaryUpdateService.auto_update_stale(
        service,
        customer_id=1,
        limit=None,
        batch_size=2,
    )

    assert result == {"found": 3, "regenerated": 3, "failed": 0}
    service.regenerate_batch.assert_awaited_with(["s1", "s2", "s3"], batch_size=2)
