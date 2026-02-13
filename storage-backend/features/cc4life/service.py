"""Service layer for cc4life feature."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from features.cc4life.db_models import CC4LifeContact, CC4LifeUser
from features.cc4life.schemas import ContactResponse, SubscribeResponse

logger = logging.getLogger(__name__)

BUTTONDOWN_API_KEY = os.getenv("BUTTONDOWN_API_KEY", "")
BUTTONDOWN_API_URL = "https://api.buttondown.com/v1/subscribers"


class CC4LifeService:
    """Business logic for cc4life operations."""

    async def subscribe_user(
        self,
        session: AsyncSession,
        email: str,
        source: str,
        ip_address: str | None,
        user_agent: str | None,
        consent: bool = False,
    ) -> SubscribeResponse:
        """
        Subscribe a user to cc4life notifications.

        Uses PostgreSQL upsert to handle duplicates gracefully.
        If email already exists, returns success without updating.
        Forwards to Buttondown API to trigger confirmation email.
        """
        # Validate consent
        if not consent:
            return SubscribeResponse(success=False, message="Consent required")

        # Check if user already exists
        stmt = select(CC4LifeUser).where(CC4LifeUser.email == email)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.info(f"User already subscribed: {email}")
            return SubscribeResponse(
                success=True,
                message="Check your email to confirm your subscription",
            )

        # Insert new subscriber using PostgreSQL upsert
        consent_timestamp = datetime.now(UTC)
        insert_stmt = pg_insert(CC4LifeUser).values(
            email=email,
            subscription_source=source,
            ip_address=ip_address,
            user_agent=user_agent,
            is_subscribed=True,
            consent=consent,
        )

        # On conflict (duplicate email), do nothing
        upsert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=["email"])

        await session.execute(upsert_stmt)
        logger.info(f"New subscriber added: {email} from source={source}")

        # Forward to Buttondown API
        await self._forward_to_buttondown(email, source, consent_timestamp)

        return SubscribeResponse(
            success=True,
            message="Check your email to confirm your subscription",
        )

    async def _forward_to_buttondown(
        self,
        email: str,
        source: str,
        consent_timestamp: datetime,
    ) -> None:
        """Forward subscriber to Buttondown API for confirmation email."""
        if not BUTTONDOWN_API_KEY:
            logger.warning("BUTTONDOWN_API_KEY not configured, skipping API call")
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    BUTTONDOWN_API_URL,
                    headers={
                        "Authorization": f"Token {BUTTONDOWN_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "email_address": email,
                        "metadata": {
                            "source": source,
                            "consent_timestamp": consent_timestamp.isoformat(),
                        },
                    },
                )

                if response.status_code == 201:
                    logger.info(f"Buttondown subscriber created: {email}")
                elif response.status_code == 400:
                    # Already subscribed or invalid - log but don't fail
                    logger.info(f"Buttondown returned 400 for {email}: {response.text}")
                else:
                    logger.warning(
                        f"Buttondown API returned {response.status_code}: {response.text}"
                    )
        except httpx.RequestError as e:
            # Buttondown failed but local save succeeded - log and continue
            logger.error(f"Buttondown API error for {email}: {e}")

    async def save_contact(
        self,
        session: AsyncSession,
        name: str,
        email: str,
        message: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> ContactResponse:
        """
        Save a contact form submission.

        Stores the message in the database for later review.
        """
        contact = CC4LifeContact(
            name=name,
            email=email,
            message=message,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(contact)
        await session.flush()

        logger.info(f"Contact form submission saved: {name} <{email}>")

        return ContactResponse(success=True, message="Message sent successfully")


__all__ = ["CC4LifeService"]
