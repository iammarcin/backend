import json
from typing import Any, Callable, Dict, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from features.storage.dependencies import get_storage_service
from main import app


@pytest.fixture(autouse=True)
def reset_dependency_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class StubStorageService:
    def __init__(self) -> None:
        self.calls: list[Dict[str, Any]] = []

    async def upload_chat_attachment(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "https://example-bucket.s3.amazonaws.com/1/assets/chat/1/20241028_fake-file.jpg"


def _build_files(
    filename: str,
    content_type: str,
    user_input: Dict[str, Any] | None = None,
) -> Dict[str, tuple[str | None, str | bytes, str | None]]:
    return {
        "file": (filename, b"fake-bytes", content_type),
        "category": (None, "provider.s3"),
        "action": (None, "s3_upload"),
        "user_input": (None, json.dumps(user_input or {})),
        "user_settings": (None, json.dumps({})),
        "customer_id": (None, "1"),
    }


@pytest.mark.anyio
async def test_upload_attachment_returns_url(auth_token_factory: Callable[..., str]) -> None:
    stub = StubStorageService()
    app.dependency_overrides[get_storage_service] = lambda: stub

    files = _build_files("example.jpg", "image/jpeg")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/storage/upload",
            files=files,
            headers={"Authorization": f"Bearer {auth_token_factory()}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["url"].startswith("https://example-bucket")
    assert payload["data"]["result"] == payload["data"]["url"]
    assert stub.calls and stub.calls[0]["filename"] == "example.jpg"
    assert stub.calls[0]["customer_id"] == 1
    assert stub.calls[0]["force_filename"] is False


@pytest.mark.anyio
async def test_upload_attachment_requires_authorization() -> None:
    stub = StubStorageService()
    app.dependency_overrides[get_storage_service] = lambda: stub

    files = _build_files("example.jpg", "image/jpeg")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/storage/upload", files=files)

    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["reason"] == "token_missing"
    assert not stub.calls


@pytest.mark.anyio
async def test_upload_attachment_rejects_invalid_token() -> None:
    stub = StubStorageService()
    app.dependency_overrides[get_storage_service] = lambda: stub

    files = _build_files("example.jpg", "image/jpeg")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/storage/upload",
            files=files,
            headers={"Authorization": "Bearer invalid"},
        )

    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["reason"] == "token_invalid"
    assert not stub.calls


@pytest.mark.anyio
async def test_upload_attachment_rejects_invalid_extension(
    auth_token_factory: Callable[..., str],
) -> None:
    stub = StubStorageService()
    app.dependency_overrides[get_storage_service] = lambda: stub

    files = _build_files("malicious.exe", "application/octet-stream")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/storage/upload",
            files=files,
            headers={"Authorization": f"Bearer {auth_token_factory()}"},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["extension"] == "exe"
    assert not stub.calls


@pytest.mark.anyio
async def test_upload_attachment_invalid_json_returns_400(
    auth_token_factory: Callable[..., str],
) -> None:
    stub = StubStorageService()
    app.dependency_overrides[get_storage_service] = lambda: stub

    files = _build_files("example.jpg", "image/jpeg")
    files["user_input"] = (None, "not-json")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/storage/upload",
            files=files,
            headers={"Authorization": f"Bearer {auth_token_factory()}"},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["field"] == "user_input"
    assert not stub.calls
