"""Tests for cc4life subscribe endpoint."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from features.cc4life.routes import router
from features.cc4life.dependencies import get_cc4life_session
from features.cc4life.schemas import SubscribeResponse
from features.cc4life.service import CC4LifeService


class FakeCC4LifeService:
    """Fake service for testing."""

    def __init__(self, response: SubscribeResponse):
        self._response = response

    async def subscribe_user(
        self,
        session: AsyncSession,
        email: str,
        source: str,
        ip_address: str | None,
        user_agent: str | None,
        consent: bool = False,
    ) -> SubscribeResponse:
        return self._response


def _build_app(service_response: SubscribeResponse | None = None) -> FastAPI:
    """Build a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def fake_session() -> AsyncIterator[AsyncSession]:
        mock_session = AsyncMock(spec=AsyncSession)
        yield mock_session

    app.dependency_overrides[get_cc4life_session] = fake_session

    return app


@pytest.mark.asyncio
async def test_subscribe_success(monkeypatch: pytest.MonkeyPatch):
    """Test successful subscription returns success response."""
    app = _build_app()

    fake_service = FakeCC4LifeService(
        SubscribeResponse(
            success=True, message="Check your email to confirm your subscription"
        )
    )
    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/subscribe",
            json={"email": "test@example.com", "source": "coming-soon", "consent": True},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["success"] is True
    assert "confirm" in body["message"].lower()


@pytest.mark.asyncio
async def test_subscribe_already_exists(monkeypatch: pytest.MonkeyPatch):
    """Test duplicate email returns success (privacy protection)."""
    app = _build_app()

    fake_service = FakeCC4LifeService(
        SubscribeResponse(
            success=True, message="Check your email to confirm your subscription"
        )
    )
    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/subscribe",
            json={"email": "existing@example.com", "consent": True},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["success"] is True


@pytest.mark.asyncio
async def test_subscribe_invalid_email(monkeypatch: pytest.MonkeyPatch):
    """Test invalid email returns 422 validation error."""
    app = _build_app()

    fake_service = FakeCC4LifeService(
        SubscribeResponse(success=True, message="Subscribed successfully")
    )
    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/subscribe",
            json={"email": "not-an-email"},
        )

    assert response.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_subscribe_default_source(monkeypatch: pytest.MonkeyPatch):
    """Test that source defaults to 'coming-soon' when not provided."""
    app = _build_app()

    captured_source = None

    class CapturingService:
        async def subscribe_user(
            self,
            session: AsyncSession,
            email: str,
            source: str,
            ip_address: str | None,
            user_agent: str | None,
            consent: bool = False,
        ) -> SubscribeResponse:
            nonlocal captured_source
            captured_source = source
            return SubscribeResponse(
                success=True, message="Check your email to confirm your subscription"
            )

    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: CapturingService())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/subscribe",
            json={"email": "test@example.com", "consent": True},  # No source provided
        )

    assert response.status_code == 200
    assert captured_source == "coming-soon"


@pytest.mark.asyncio
async def test_subscribe_custom_source(monkeypatch: pytest.MonkeyPatch):
    """Test that custom source is passed through."""
    app = _build_app()

    captured_source = None

    class CapturingService:
        async def subscribe_user(
            self,
            session: AsyncSession,
            email: str,
            source: str,
            ip_address: str | None,
            user_agent: str | None,
            consent: bool = False,
        ) -> SubscribeResponse:
            nonlocal captured_source
            captured_source = source
            return SubscribeResponse(
                success=True, message="Check your email to confirm your subscription"
            )

    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: CapturingService())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/subscribe",
            json={"email": "test@example.com", "source": "landing-page", "consent": True},
        )

    assert response.status_code == 200
    assert captured_source == "landing-page"


@pytest.mark.asyncio
async def test_subscribe_consent_passed_to_service(monkeypatch: pytest.MonkeyPatch):
    """Test that consent is passed through to service."""
    app = _build_app()

    captured_consent = None

    class CapturingService:
        async def subscribe_user(
            self,
            session: AsyncSession,
            email: str,
            source: str,
            ip_address: str | None,
            user_agent: str | None,
            consent: bool = False,
        ) -> SubscribeResponse:
            nonlocal captured_consent
            captured_consent = consent
            return SubscribeResponse(
                success=True, message="Check your email to confirm your subscription"
            )

    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: CapturingService())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/subscribe",
            json={"email": "test@example.com", "consent": True},
        )

    assert response.status_code == 200
    assert captured_consent is True


@pytest.mark.asyncio
async def test_subscribe_missing_email(monkeypatch: pytest.MonkeyPatch):
    """Test that missing email returns 422 validation error."""
    app = _build_app()

    fake_service = FakeCC4LifeService(
        SubscribeResponse(success=True, message="Subscribed successfully")
    )
    monkeypatch.setattr("features.cc4life.routes._get_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cc4life/subscribe",
            json={},  # No email provided
        )

    assert response.status_code == 422  # FastAPI validation error
