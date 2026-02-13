from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.exceptions import DatabaseError
from features.db.blood.schemas import BloodTestFilterParams
from features.db.blood.service import BloodService


@pytest.fixture
def anyio_backend() -> str:
    """Force pytest-anyio to use asyncio for async tests."""

    return "asyncio"


@pytest.mark.anyio
async def test_list_tests_returns_response_with_metadata():
    repo = AsyncMock()
    repo.list_tests.return_value = [
        {
            "id": 1,
            "test_definition_id": 10,
            "test_date": date(2024, 1, 10),
            "result_value": "5.6",
            "result_unit": "mmol/L",
            "reference_range": "4.0-6.0",
            "category": "Metabolic",
            "test_name": "Glucose",
            "short_explanation": "Fasting glucose",
            "long_explanation": None,
        },
        {
            "id": 2,
            "test_definition_id": 11,
            "test_date": date(2024, 2, 5),
            "result_value": "12.3",
            "result_unit": "g/dL",
            "reference_range": "13-17",
            "category": "Haematology",
            "test_name": "Haemoglobin",
            "short_explanation": "Red cell count",
            "long_explanation": None,
        },
    ]

    service = BloodService(tests_repo=repo)
    session = SimpleNamespace()

    result = await service.list_tests(session, BloodTestFilterParams(limit=1))

    repo.list_tests.assert_awaited_once_with(session)
    assert result.total_count == 2
    assert result.latest_test_date == date(2024, 2, 5)
    assert len(result.items) == 1
    assert result.items[0].id == 1
    assert result.filters and result.filters.limit == 1


@pytest.mark.anyio
async def test_list_tests_applies_filters():
    repo = AsyncMock()
    repo.list_tests.return_value = [
        {
            "id": 1,
            "test_definition_id": 10,
            "test_date": date(2024, 1, 10),
            "result_value": None,
            "result_unit": None,
            "reference_range": None,
            "category": "Metabolic",
            "test_name": None,
            "short_explanation": None,
            "long_explanation": None,
        },
        {
            "id": 2,
            "test_definition_id": 11,
            "test_date": date(2024, 2, 15),
            "result_value": None,
            "result_unit": None,
            "reference_range": None,
            "category": "Haematology",
            "test_name": None,
            "short_explanation": None,
            "long_explanation": None,
        },
    ]

    service = BloodService(tests_repo=repo)
    session = SimpleNamespace()
    filters = BloodTestFilterParams(
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 28),
        category="Haematology",
    )

    result = await service.list_tests(session, filters)

    assert result.total_count == 1
    assert result.items[0].id == 2
    assert result.latest_test_date == date(2024, 2, 15)


@pytest.mark.anyio
async def test_list_tests_handles_empty_dataset():
    repo = AsyncMock()
    repo.list_tests.return_value = []

    service = BloodService(tests_repo=repo)
    session = SimpleNamespace()

    result = await service.list_tests(session)

    assert result.total_count == 0
    assert result.latest_test_date is None
    assert result.items == []


@pytest.mark.anyio
async def test_list_tests_propagates_repository_errors():
    repo = AsyncMock()
    repo.list_tests.side_effect = DatabaseError("boom", operation="blood.tests.list")

    service = BloodService(tests_repo=repo)
    session = SimpleNamespace()

    with pytest.raises(DatabaseError):
        await service.list_tests(session)
