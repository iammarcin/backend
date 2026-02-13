"""Tests for cc4life contact endpoint."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from features.cc4life.routes import router
from features.cc4life.dependencies import get_cc4life_session
from features.cc4life.schemas import ContactResponse


class FakeContactService:
    """Fake service for testing contact endpoint."""

    def __init__(self, response: ContactResponse):
        self._response = response

    async def save_contact(
        self,
        session: AsyncSession,
        name: str,
        email: str,
        message: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> ContactResponse:
        return self._response


def _build_app() -> FastAPI:
    """Build a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def fake_session() -> AsyncIterator[AsyncSession]:
        mock_session = AsyncMock(spec=AsyncSession)
        yield mock_session

    app.dependency_overrides[get_cc4life_session] = fake_session

    return app


@pytest.mark.asyncio
async def test_contact_success(monkeypatch: pytest.MonkeyPatch):
    """Test successful contact form submission."""
    app = _build_app()

    fake_service = FakeContactService(
        ContactResponse(success=True, message="Message sent successfully")
    )
    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/contact",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "message": "Hello, I want to learn more!",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["success"] is True
    assert "Message sent successfully" in body["message"]


@pytest.mark.asyncio
async def test_contact_invalid_email(monkeypatch: pytest.MonkeyPatch):
    """Test invalid email returns 422 validation error."""
    app = _build_app()

    fake_service = FakeContactService(
        ContactResponse(success=True, message="Message sent successfully")
    )
    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/contact",
            json={
                "name": "John Doe",
                "email": "not-an-email",
                "message": "Hello!",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_contact_missing_name(monkeypatch: pytest.MonkeyPatch):
    """Test missing name returns 422 validation error."""
    app = _build_app()

    fake_service = FakeContactService(
        ContactResponse(success=True, message="Message sent successfully")
    )
    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/contact",
            json={
                "email": "john@example.com",
                "message": "Hello!",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_contact_missing_message(monkeypatch: pytest.MonkeyPatch):
    """Test missing message returns 422 validation error."""
    app = _build_app()

    fake_service = FakeContactService(
        ContactResponse(success=True, message="Message sent successfully")
    )
    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/contact",
            json={
                "name": "John Doe",
                "email": "john@example.com",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_contact_captures_metadata(monkeypatch: pytest.MonkeyPatch):
    """Test that IP and user agent are captured."""
    app = _build_app()

    captured_data = {}

    class CapturingService:
        async def save_contact(
            self,
            session: AsyncSession,
            name: str,
            email: str,
            message: str,
            ip_address: str | None,
            user_agent: str | None,
        ) -> ContactResponse:
            captured_data["name"] = name
            captured_data["email"] = email
            captured_data["message"] = message
            captured_data["ip_address"] = ip_address
            captured_data["user_agent"] = user_agent
            return ContactResponse(success=True, message="Message sent successfully")

    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: CapturingService())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/contact",
            json={
                "name": "Jane Doe",
                "email": "jane@example.com",
                "message": "Test message",
            },
            headers={"User-Agent": "TestBrowser/1.0"},
        )

    assert response.status_code == 200
    assert captured_data["name"] == "Jane Doe"
    assert captured_data["email"] == "jane@example.com"
    assert captured_data["message"] == "Test message"
    assert captured_data["user_agent"] == "TestBrowser/1.0"
