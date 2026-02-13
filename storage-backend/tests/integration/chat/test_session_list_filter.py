"""Integration tests for session list ai_character_name filter at repository level."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import pytest

from features.chat.db_models import User
from features.chat.repositories import (
    ChatMessageRepository,
    ChatSessionRepository,
)


async def _create_user(session, customer_id: int = 1) -> User:
    password_hash = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode("utf-8")
    user = User(
        customer_id=customer_id,
        username="demo",
        email="demo@example.com",
        password=password_hash,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_list_sessions_filter_by_ai_character_name(session):
    """Verify that passing ai_character_name filters sessions to that agent only."""

    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    # Create sessions for two different agents
    sherlock_session = await session_repo.create_session(
        customer_id=1,
        session_name="Sherlock Chat",
        ai_character_name="sherlock",
    )
    bugsy_session = await session_repo.create_session(
        customer_id=1,
        session_name="Bugsy Chat",
        ai_character_name="bugsy",
    )

    # Both sessions need at least one message to appear in list results
    # (list_customer_sessions excludes empty sessions)
    await message_repo.insert_message(
        session_id=sherlock_session.session_id,
        customer_id=1,
        payload={"sender": "User", "message": "Hello Sherlock"},
        is_ai_message=False,
    )
    await message_repo.insert_message(
        session_id=bugsy_session.session_id,
        customer_id=1,
        payload={"sender": "User", "message": "Hello Bugsy"},
        is_ai_message=False,
    )

    # Filter by sherlock
    sherlock_results = await session_repo.list_sessions(
        customer_id=1,
        ai_character_name="sherlock",
        include_messages=False,
    )
    assert len(sherlock_results) == 1
    assert sherlock_results[0]["ai_character_name"] == "sherlock"
    assert sherlock_results[0]["session_name"] == "Sherlock Chat"

    # Filter by bugsy
    bugsy_results = await session_repo.list_sessions(
        customer_id=1,
        ai_character_name="bugsy",
        include_messages=False,
    )
    assert len(bugsy_results) == 1
    assert bugsy_results[0]["ai_character_name"] == "bugsy"
    assert bugsy_results[0]["session_name"] == "Bugsy Chat"


@pytest.mark.asyncio
async def test_list_sessions_no_filter_returns_all(session):
    """Verify that omitting ai_character_name returns all sessions."""

    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    for agent_name in ("sherlock", "bugsy", "assistant"):
        sess = await session_repo.create_session(
            customer_id=1,
            session_name=f"{agent_name} chat",
            ai_character_name=agent_name,
        )
        await message_repo.insert_message(
            session_id=sess.session_id,
            customer_id=1,
            payload={"sender": "User", "message": f"Hello {agent_name}"},
            is_ai_message=False,
        )

    all_results = await session_repo.list_sessions(
        customer_id=1,
        include_messages=False,
    )
    assert len(all_results) == 3

    # Verify no filter was applied
    agent_names = {r["ai_character_name"] for r in all_results}
    assert agent_names == {"sherlock", "bugsy", "assistant"}


@pytest.mark.asyncio
async def test_list_sessions_filter_nonexistent_agent_returns_empty(session):
    """Verify filtering by a non-existent agent returns no results."""

    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    sess = await session_repo.create_session(
        customer_id=1,
        session_name="Sherlock chat",
        ai_character_name="sherlock",
    )
    await message_repo.insert_message(
        session_id=sess.session_id,
        customer_id=1,
        payload={"sender": "User", "message": "Hello"},
        is_ai_message=False,
    )

    results = await session_repo.list_sessions(
        customer_id=1,
        ai_character_name="nonexistent",
        include_messages=False,
    )
    assert len(results) == 0


@pytest.mark.asyncio
async def test_list_sessions_filter_combined_with_tags(session):
    """Verify ai_character_name filter works together with tag filtering."""

    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    # Sherlock session with 'work' tag
    sherlock_work = await session_repo.create_session(
        customer_id=1,
        session_name="Sherlock Work",
        ai_character_name="sherlock",
        tags=["work"],
    )
    await message_repo.insert_message(
        session_id=sherlock_work.session_id,
        customer_id=1,
        payload={"sender": "User", "message": "Work task"},
        is_ai_message=False,
    )

    # Sherlock session with 'personal' tag
    sherlock_personal = await session_repo.create_session(
        customer_id=1,
        session_name="Sherlock Personal",
        ai_character_name="sherlock",
        tags=["personal"],
    )
    await message_repo.insert_message(
        session_id=sherlock_personal.session_id,
        customer_id=1,
        payload={"sender": "User", "message": "Personal task"},
        is_ai_message=False,
    )

    # Bugsy session with 'work' tag
    bugsy_work = await session_repo.create_session(
        customer_id=1,
        session_name="Bugsy Work",
        ai_character_name="bugsy",
        tags=["work"],
    )
    await message_repo.insert_message(
        session_id=bugsy_work.session_id,
        customer_id=1,
        payload={"sender": "User", "message": "Bugsy work"},
        is_ai_message=False,
    )

    # Filter by sherlock + work tag
    results = await session_repo.list_sessions(
        customer_id=1,
        ai_character_name="sherlock",
        tags=["work"],
        include_messages=False,
    )
    assert len(results) == 1
    assert results[0]["session_name"] == "Sherlock Work"
