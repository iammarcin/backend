from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DatabaseError, OperationalError

from core.exceptions import ValidationError
from features.chat.dependencies import get_chat_history_service
from main import app


@pytest.fixture
def legacy_client():
    app.dependency_overrides[get_chat_history_service] = lambda: MagicMock()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_chat_history_service, None)


def _post_legacy_request(client: TestClient, token: str) -> tuple[int, dict]:
    response = client.post(
        "/api/db",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "action": "db_search_messages",
            "userInput": {},
            "customerId": 1,
            "userSettings": {},
        },
    )
    return response.status_code, response.json()


def test_legacy_db_returns_503_on_operational_error(
    legacy_client: TestClient, auth_token_factory
):
    error = OperationalError("SELECT 1", {}, Exception("connection refused"))

    with patch(
        "features.legacy_compat.routes.handle_db_search_messages",
        new=AsyncMock(side_effect=error),
    ):
        status, payload = _post_legacy_request(
            legacy_client, auth_token_factory(customer_id=1)
        )

    assert status == 503
    assert payload["success"] is False
    assert payload["code"] == 503
    assert payload["message"]["status"] == "fail"
    assert "Database temporarily unavailable" in payload["message"]["result"]
    assert "pymysql" not in payload["message"]["result"]


def test_legacy_db_returns_400_on_validation_error(
    legacy_client: TestClient, auth_token_factory
):
    with patch(
        "features.legacy_compat.routes.handle_db_search_messages",
        new=AsyncMock(side_effect=ValidationError("invalid input")),
    ):
        status, payload = _post_legacy_request(
            legacy_client, auth_token_factory(customer_id=1)
        )

    assert status == 400
    assert payload["success"] is False
    assert payload["code"] == 400
    assert payload["message"]["status"] == "fail"
    assert payload["message"]["result"] == "invalid input"


def test_legacy_db_returns_503_on_database_error(
    legacy_client: TestClient, auth_token_factory
):
    error = DatabaseError("SELECT 1", {}, Exception("db error"))

    with patch(
        "features.legacy_compat.routes.handle_db_search_messages",
        new=AsyncMock(side_effect=error),
    ):
        status, payload = _post_legacy_request(
            legacy_client, auth_token_factory(customer_id=1)
        )

    assert status == 503
    assert payload["success"] is False
    assert payload["code"] == 503
    assert payload["message"]["status"] == "fail"
    assert "Database temporarily unavailable" in payload["message"]["result"]
    assert "db error" not in payload["message"]["result"]
