"""Integration tests covering chat ORM repositories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import pytest

from core.exceptions import AuthenticationError
from features.chat.db_models import User
from features.chat.mappers import chat_message_to_dict
from features.chat.repositories import (
    ChatMessageRepository,
    ChatSessionRepository,
    PromptRepository,
    UserRepository,
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
async def test_create_session_and_insert_messages(session):
    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    created_session = await session_repo.create_session(
        customer_id=1,
        session_name="Demo Chat",
        tags=["inbox"],
    )

    await message_repo.insert_message(
        session_id=created_session.session_id,
        customer_id=1,
        payload={
            "sender": "User",
            "message": "Hello",
            "image_locations": [],
            "file_locations": [],
        },
        is_ai_message=False,
    )

    await message_repo.insert_message(
        session_id=created_session.session_id,
        customer_id=1,
        payload={
            "sender": "AI",
            "message": "Hi there!",
            "ai_character_name": "assistant",
            "api_text_gen_model_name": "gpt-4o-mini",
            "api_text_gen_settings": {"temperature": 0.5},
            "favorite": True,
        },
        claude_code_data={"steps": []},
        is_ai_message=True,
    )

    messages = await message_repo.get_messages_for_session(created_session.session_id)
    assert [message.sender for message in messages] == ["User", "AI"]
    message_dict = chat_message_to_dict(messages[1])
    assert message_dict["favorite"] is True


@pytest.mark.asyncio
async def test_list_sessions_filters_and_messages(session):
    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    base_time = datetime.now(UTC)
    session_a = await session_repo.create_session(
        customer_id=1,
        session_name="Planning",
        tags=["work"],
        created_at=base_time - timedelta(days=2),
        last_update=base_time - timedelta(days=2),
    )
    await session_repo.create_session(
        customer_id=1,
        session_name="Leisure",
        tags=["personal"],
        created_at=base_time - timedelta(days=1),
        last_update=base_time - timedelta(days=1),
    )

    await message_repo.insert_message(
        session_id=session_a.session_id,
        customer_id=1,
        payload={"sender": "User", "message": "Plan release"},
        is_ai_message=False,
    )

    results = await session_repo.list_sessions(
        customer_id=1,
        start_date=base_time - timedelta(days=3),
        end_date=base_time - timedelta(days=1),
        tags=["work"],
        include_messages=True,
    )

    assert len(results) == 1
    assert results[0]["session_name"] == "Planning"
    assert len(results[0]["messages"]) == 1


@pytest.mark.asyncio
async def test_search_sessions(session):
    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    session_obj = await session_repo.create_session(
        customer_id=1,
        session_name="Travel",
        tags=["planning"],
    )
    await message_repo.insert_message(
        session_id=session_obj.session_id,
        customer_id=1,
        payload={"sender": "AI", "message": "Visit London"},
        is_ai_message=True,
    )

    matches = await session_repo.search_sessions(
        customer_id=1,
        search_text="london",
    )
    assert any(result["session_id"] == session_obj.session_id for result in matches)


@pytest.mark.asyncio
async def test_fetch_favorites_virtual_session(session):
    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    session_obj = await session_repo.create_session(customer_id=1)
    await message_repo.insert_message(
        session_id=session_obj.session_id,
        customer_id=1,
        payload={"sender": "AI", "message": "Saved", "favorite": True},
        is_ai_message=True,
    )

    virtual_session = await message_repo.fetch_favorites(customer_id=1)
    assert virtual_session is not None
    assert virtual_session["session_name"] == "Favorite Messages"
    assert len(virtual_session["messages"]) == 1


@pytest.mark.asyncio
async def test_fetch_messages_with_files(session):
    await _create_user(session)

    session_repo = ChatSessionRepository(session)
    message_repo = ChatMessageRepository(session)

    session_obj = await session_repo.create_session(customer_id=1)
    await message_repo.insert_message(
        session_id=session_obj.session_id,
        customer_id=1,
        payload={
            "sender": "AI",
            "message": "See audio",
            "file_locations": ["clip.wav", "notes.txt"],
        },
        is_ai_message=True,
    )
    await message_repo.insert_message(
        session_id=session_obj.session_id,
        customer_id=1,
        payload={
            "sender": "AI",
            "message": "image attachment",
            "image_locations": ["frame.png"],
        },
        is_ai_message=True,
    )

    wav_results = await message_repo.fetch_messages_with_files(
        customer_id=1,
        file_extension=".wav",
        ai_only=True,
    )
    assert len(wav_results) == 1
    assert wav_results[0]["file_locations"] == ["clip.wav", "notes.txt"]

    image_results = await message_repo.fetch_messages_with_files(
        customer_id=1,
        file_extension=".png",
        check_image_locations=True,
    )
    assert len(image_results) == 1
    assert image_results[0]["image_locations"] == ["frame.png"]


@pytest.mark.asyncio
async def test_prompt_repository_crud(session):
    await _create_user(session)

    prompt_repo = PromptRepository(session)

    prompt = await prompt_repo.add_prompt(customer_id=1, title="Welcome", prompt_text="Hello there")
    prompts = await prompt_repo.list_prompts(customer_id=1)
    assert len(prompts) == 1
    assert prompts[0]["title"] == "Welcome"

    await prompt_repo.update_prompt(prompt_id=prompt.prompt_id, prompt_text="Updated")
    prompts_after_update = await prompt_repo.list_prompts(customer_id=1)
    assert prompts_after_update[0]["prompt"] == "Updated"

    removed = await prompt_repo.delete_prompt(prompt_id=prompt.prompt_id)
    assert removed is True
    assert await prompt_repo.list_prompts(customer_id=1) == []


@pytest.mark.asyncio
async def test_verify_credentials(session):
    await _create_user(session)
    user_repo = UserRepository(session)

    user = await user_repo.verify_credentials(customer_id=1, username="demo@example.com", password="secret")
    assert user.customer_id == 1

    with pytest.raises(AuthenticationError):
        await user_repo.verify_credentials(customer_id=1, username="demo@example.com", password="wrong")
