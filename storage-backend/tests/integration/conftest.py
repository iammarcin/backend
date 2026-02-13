from __future__ import annotations

from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient
from urllib.parse import urlencode

@pytest.fixture()
def chat_test_client() -> Iterator[TestClient]:
    """Provide a FastAPI client with the chat websocket registered."""

    from tests.integration.chat.conftest import _build_chat_test_app

    app = _build_chat_test_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def websocket_url_factory(auth_token_factory):
    """Build websocket URLs that include a valid JWT."""

    def _factory(token: str | None = None, **params: Any) -> str:
        actual_token = token or auth_token_factory()
        query: dict[str, Any] = {"token": actual_token}
        query.update({key: value for key, value in params.items() if value is not None})
        return "/chat/ws?" + urlencode(query)

    return _factory
