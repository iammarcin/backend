"""Integration tests for task metadata on chat sessions (Phase 2, Step 4)."""

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


async def _create_session_with_message(
    session_repo: ChatSessionRepository,
    message_repo: ChatMessageRepository,
    customer_id: int = 1,
    **kwargs,
):
    """Helper: create a session and insert a message so it appears in list queries."""
    sess = await session_repo.create_session(customer_id=customer_id, **kwargs)
    await message_repo.insert_message(
        session_id=sess.session_id,
        customer_id=customer_id,
        payload={"sender": "User", "message": "Hello"},
        is_ai_message=False,
    )
    return sess


# ---------------------------------------------------------------------------
# Task CRUD via repository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_with_task_fields(session):
    """Verify task columns are persisted and retrievable."""

    await _create_user(session)
    repo = ChatSessionRepository(session)

    sess = await repo.create_session(
        customer_id=1,
        session_name="Task session",
        ai_character_name="sherlock",
    )
    # Set task fields directly on the ORM object
    sess.task_status = "active"
    sess.task_priority = "high"
    sess.task_description = "Investigate the case"
    await session.flush()

    loaded = await repo.get_by_id(sess.session_id, customer_id=1)
    assert loaded is not None
    assert loaded.task_status == "active"
    assert loaded.task_priority == "high"
    assert loaded.task_description == "Investigate the case"


@pytest.mark.asyncio
async def test_update_session_task_fields(session):
    """Verify task fields can be updated via update_session_metadata."""

    await _create_user(session)
    repo = ChatSessionRepository(session)

    sess = await repo.create_session(
        customer_id=1,
        session_name="Normal session",
        ai_character_name="sherlock",
    )

    # Promote to task
    updated = await repo.update_session_metadata(
        session_id=sess.session_id,
        customer_id=1,
        task_status="active",
        task_priority="medium",
        task_description="New task description",
    )
    assert updated.task_status == "active"
    assert updated.task_priority == "medium"
    assert updated.task_description == "New task description"

    # Update task status to done
    updated2 = await repo.update_session_metadata(
        session_id=sess.session_id,
        customer_id=1,
        task_status="done",
    )
    assert updated2.task_status == "done"
    # Priority and description unchanged
    assert updated2.task_priority == "medium"
    assert updated2.task_description == "New task description"


@pytest.mark.asyncio
async def test_session_without_task_fields_returns_null(session):
    """Verify existing sessions without task metadata return None."""

    await _create_user(session)
    repo = ChatSessionRepository(session)

    sess = await repo.create_session(
        customer_id=1,
        session_name="Regular session",
        ai_character_name="bugsy",
    )

    loaded = await repo.get_by_id(sess.session_id, customer_id=1)
    assert loaded is not None
    assert loaded.task_status is None
    assert loaded.task_priority is None
    assert loaded.task_description is None


# ---------------------------------------------------------------------------
# Task status filter on session list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_filter_task_status_exact(session):
    """Verify exact task_status filter (active, waiting, done)."""

    await _create_user(session)
    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    # Create active task
    active_sess = await _create_session_with_message(
        session_repo, message_repo,
        session_name="Active Task",
        ai_character_name="sherlock",
    )
    active_sess.task_status = "active"
    active_sess.task_priority = "high"
    await session.flush()

    # Create done task
    done_sess = await _create_session_with_message(
        session_repo, message_repo,
        session_name="Done Task",
        ai_character_name="sherlock",
    )
    done_sess.task_status = "done"
    await session.flush()

    # Create non-task session
    await _create_session_with_message(
        session_repo, message_repo,
        session_name="Normal Session",
        ai_character_name="sherlock",
    )

    # Filter active
    active_results = await session_repo.list_sessions(
        customer_id=1, task_status="active", include_messages=False,
    )
    assert len(active_results) == 1
    assert active_results[0]["session_name"] == "Active Task"
    assert active_results[0]["task_status"] == "active"

    # Filter done
    done_results = await session_repo.list_sessions(
        customer_id=1, task_status="done", include_messages=False,
    )
    assert len(done_results) == 1
    assert done_results[0]["session_name"] == "Done Task"


@pytest.mark.asyncio
async def test_list_sessions_filter_task_status_any(session):
    """Verify 'any' filter returns all sessions with task_status set."""

    await _create_user(session)
    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    # Create task
    task_sess = await _create_session_with_message(
        session_repo, message_repo,
        session_name="Task",
        ai_character_name="sherlock",
    )
    task_sess.task_status = "active"
    await session.flush()

    # Create non-task
    await _create_session_with_message(
        session_repo, message_repo,
        session_name="Regular",
        ai_character_name="sherlock",
    )

    results = await session_repo.list_sessions(
        customer_id=1, task_status="any", include_messages=False,
    )
    assert len(results) == 1
    assert results[0]["task_status"] == "active"


@pytest.mark.asyncio
async def test_list_sessions_filter_task_status_none(session):
    """Verify 'none' filter returns only sessions without task_status."""

    await _create_user(session)
    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    # Create task
    task_sess = await _create_session_with_message(
        session_repo, message_repo,
        session_name="Task",
        ai_character_name="sherlock",
    )
    task_sess.task_status = "waiting"
    await session.flush()

    # Create non-task
    await _create_session_with_message(
        session_repo, message_repo,
        session_name="Regular",
        ai_character_name="bugsy",
    )

    results = await session_repo.list_sessions(
        customer_id=1, task_status="none", include_messages=False,
    )
    assert len(results) == 1
    assert results[0]["session_name"] == "Regular"
    assert results[0]["task_status"] is None


@pytest.mark.asyncio
async def test_list_sessions_no_task_filter_returns_all(session):
    """Verify omitting task_status returns all sessions (tasks + non-tasks)."""

    await _create_user(session)
    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    task_sess = await _create_session_with_message(
        session_repo, message_repo,
        session_name="Task",
        ai_character_name="sherlock",
    )
    task_sess.task_status = "active"
    await session.flush()

    await _create_session_with_message(
        session_repo, message_repo,
        session_name="Regular",
        ai_character_name="bugsy",
    )

    results = await session_repo.list_sessions(
        customer_id=1, include_messages=False,
    )
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Task metadata appears in serialised output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_session_to_dict_includes_task_fields(session):
    """Verify the mapper includes task fields in the serialised dict."""

    await _create_user(session)
    repo = ChatSessionRepository(session)

    sess = await repo.create_session(
        customer_id=1,
        session_name="Task session",
        ai_character_name="sherlock",
    )
    sess.task_status = "waiting"
    sess.task_priority = "low"
    sess.task_description = "Review documents"
    await session.flush()

    from features.chat.mappers import chat_session_to_dict

    result = chat_session_to_dict(sess, include_messages=False)
    assert result["task_status"] == "waiting"
    assert result["task_priority"] == "low"
    assert result["task_description"] == "Review documents"


@pytest.mark.asyncio
async def test_chat_session_to_dict_null_task_fields(session):
    """Verify the mapper returns None for task fields when not set."""

    await _create_user(session)
    repo = ChatSessionRepository(session)

    sess = await repo.create_session(
        customer_id=1,
        session_name="Normal session",
    )

    from features.chat.mappers import chat_session_to_dict

    result = chat_session_to_dict(sess, include_messages=False)
    assert result["task_status"] is None
    assert result["task_priority"] is None
    assert result["task_description"] is None
