"""Tests for cc4life service layer."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from features.cc4life.db_models import CC4LifeUser
from features.cc4life.service import CC4LifeService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def service() -> CC4LifeService:
    """Create a CC4LifeService instance."""
    return CC4LifeService()


@pytest.mark.asyncio
async def test_subscribe_user_without_consent_returns_error(
    service: CC4LifeService, mock_session: AsyncMock
):
    """Test that subscribing without consent returns an error."""
    result = await service.subscribe_user(
        session=mock_session,
        email="test@example.com",
        source="website",
        ip_address="127.0.0.1",
        user_agent="test-agent",
        consent=False,
    )

    assert result.success is False
    assert "consent" in result.message.lower()
    # Should not have queried the database
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_subscribe_user_with_consent_saves_to_db(
    service: CC4LifeService, mock_session: AsyncMock
):
    """Test that subscribing with consent saves to database."""
    # Mock that no existing user exists
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with patch.object(service, "_forward_to_buttondown", new_callable=AsyncMock):
        result = await service.subscribe_user(
            session=mock_session,
            email="test@example.com",
            source="website",
            ip_address="127.0.0.1",
            user_agent="test-agent",
            consent=True,
        )

    assert result.success is True
    assert "confirm" in result.message.lower()
    # Should have executed queries (select + insert)
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_subscribe_user_existing_user_returns_success(
    service: CC4LifeService, mock_session: AsyncMock
):
    """Test that existing user returns success without inserting."""
    # Mock that user already exists
    existing_user = MagicMock(spec=CC4LifeUser)
    existing_user.email = "existing@example.com"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user
    mock_session.execute.return_value = mock_result

    result = await service.subscribe_user(
        session=mock_session,
        email="existing@example.com",
        source="website",
        ip_address="127.0.0.1",
        user_agent="test-agent",
        consent=True,
    )

    assert result.success is True
    assert "confirm" in result.message.lower()
    # Should only have executed the select query
    assert mock_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_forward_to_buttondown_success(service: CC4LifeService):
    """Test successful Buttondown API call."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = '{"id": "123"}'

    with patch("features.cc4life.service.BUTTONDOWN_API_KEY", "test-api-key"):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await service._forward_to_buttondown(
                email="test@example.com",
                source="website",
                consent_timestamp=datetime.now(UTC),
            )

            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["email_address"] == "test@example.com"
            assert "source" in call_kwargs["json"]["metadata"]


@pytest.mark.asyncio
async def test_forward_to_buttondown_no_api_key(service: CC4LifeService):
    """Test that missing API key skips Buttondown call."""
    with patch("features.cc4life.service.BUTTONDOWN_API_KEY", ""):
        with patch("httpx.AsyncClient") as mock_client_class:
            await service._forward_to_buttondown(
                email="test@example.com",
                source="website",
                consent_timestamp=datetime.now(UTC),
            )

            mock_client_class.assert_not_called()


@pytest.mark.asyncio
async def test_forward_to_buttondown_400_does_not_raise(service: CC4LifeService):
    """Test that 400 response (already subscribed) doesn't raise an exception."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error": "already subscribed"}'

    with patch("features.cc4life.service.BUTTONDOWN_API_KEY", "test-api-key"):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Should not raise - just return gracefully
            await service._forward_to_buttondown(
                email="test@example.com",
                source="website",
                consent_timestamp=datetime.now(UTC),
            )

            # Verify the API was called
            mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_forward_to_buttondown_network_error_does_not_raise(
    service: CC4LifeService,
):
    """Test that network errors don't raise exceptions."""
    with patch("features.cc4life.service.BUTTONDOWN_API_KEY", "test-api-key"):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.RequestError("Connection failed")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Should not raise - just return gracefully
            await service._forward_to_buttondown(
                email="test@example.com",
                source="website",
                consent_timestamp=datetime.now(UTC),
            )

            # Verify the API was attempted
            mock_client.post.assert_called_once()
