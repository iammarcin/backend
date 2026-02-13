"""Integration coverage for the Blood repositories."""

from __future__ import annotations

from datetime import date

import pytest


pytestmark = pytest.mark.requires_docker

from features.db.blood.db_models import BloodTest, TestDefinition
from features.db.blood.repositories.tests import BloodTestRepository


@pytest.mark.asyncio
async def test_list_tests_returns_joined_rows(session) -> None:
    repo = BloodTestRepository()

    iron_def = TestDefinition(
        category="Iron Panel",
        test_name="Ferritin",
        short_explanation="Measures iron stores",
        long_explanation="Ferritin levels indicate the amount of stored iron in the body.",
    )
    metabolic_def = TestDefinition(
        category="Metabolic",
        test_name="Glucose",
        short_explanation="Measures blood sugar",
        long_explanation="Fasting glucose identifies metabolic health issues.",
    )

    session.add_all([iron_def, metabolic_def])
    await session.flush()

    recent_test = BloodTest(
        test_definition_id=iron_def.id,
        test_date=date(2024, 3, 1),
        result_value="120",
        result_unit="ng/mL",
        reference_range="30-400",
    )
    older_test = BloodTest(
        test_definition_id=metabolic_def.id,
        test_date=date(2024, 1, 15),
        result_value="4.5",
        result_unit="mmol/L",
        reference_range="3.5-5.0",
    )
    session.add_all([recent_test, older_test])
    await session.flush()

    rows = await repo.list_tests(session)

    assert [row["test_name"] for row in rows] == ["Ferritin", "Glucose"]
    assert rows[0]["test_date"] == date(2024, 3, 1)
    assert rows[0]["category"] == "Iron Panel"
    assert rows[0]["result_unit"] == "ng/mL"
    assert rows[0]["test_definition_id"] == iron_def.id
    assert rows[1]["test_date"] == date(2024, 1, 15)
    assert rows[1]["reference_range"] == "3.5-5.0"


@pytest.mark.asyncio
async def test_list_tests_returns_empty_when_no_rows(session) -> None:
    repo = BloodTestRepository()

    rows = await repo.list_tests(session)

    assert rows == []
