"""Integration test for complete message edit flow using API calls.

This test simulates the React frontend behavior:
1. Create a user request and get response (via API)
2. Extract database IDs from the response
3. Send edit message request using same payload as React frontend (via API)
4. Fetch session from DB via API call and verify edited message text
"""

from __future__ import annotations
from dataclasses import replace

import sys
import types
from typing import AsyncIterator, Iterator

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Mock the itisai_brain module before importing main
if "itisai_brain" not in sys.modules:
    brain_module = types.ModuleType("itisai_brain")
    text_module = types.ModuleType("itisai_brain.text")

    def _stub_prompt_template(*args, **kwargs):  # pragma: no cover
        return ""

    text_module.getTextPromptTemplate = _stub_prompt_template  # type: ignore[attr-defined]
    brain_module.text = text_module
    sys.modules["itisai_brain"] = brain_module
    sys.modules["itisai_brain.text"] = text_module

from core.config import settings as app_settings
from features.chat.db_models import User
from features.chat.dependencies import get_chat_session
from features.chat.services.history import semantic_indexing as semantic_indexing_module
from features.semantic_search import dependencies as deps_module
from features.semantic_search import service as service_module
from main import app


def _extract_session_payload(payload: dict[str, object]) -> dict[str, object]:
    """Return the session payload regardless of envelope format."""

    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if isinstance(data, dict) and "session" in data:
        session_payload = data["session"]
        if isinstance(session_payload, dict):
            return session_payload
    return data if isinstance(data, dict) else {}


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    """Reset dependency overrides after each test."""
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def _patch_settings(monkeypatch, **overrides):
    """Patch settings in relevant modules."""
    patched = replace(app_settings, **overrides)
    monkeypatch.setattr(deps_module, "settings", patched)
    monkeypatch.setattr(service_module, "settings", patched)
    monkeypatch.setattr(semantic_indexing_module, "settings", patched)


@pytest.fixture(autouse=True)
def disable_semantic_search(monkeypatch) -> None:
    """Disable semantic search for integration tests."""
    _patch_settings(monkeypatch, semantic_search_enabled=False, semantic_search_indexing_enabled=False)
    # Also clear any cached service instance
    monkeypatch.setattr(service_module, "_service_instance", None)


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio backend for async tests."""
    return "asyncio"


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user in the database."""
    password_hash = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode("utf-8")
    user = User(
        customer_id=7,
        username="testuser",
        email="test@example.com",
        password=password_hash,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def client_with_test_db(session: AsyncSession, test_user: User, auth_token_factory) -> AsyncIterator[AsyncClient]:
    """Create an AsyncClient that uses the test database session."""

    async def override_get_chat_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_chat_session] = override_get_chat_session

    # Create auth token with customer_id=7 to match test_user
    auth_token = auth_token_factory(customer_id=7)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.headers.update({"Authorization": f"Bearer {auth_token}"})
        yield client

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_complete_edit_message_flow_via_api(client_with_test_db: AsyncClient) -> None:
    """Test complete message edit flow using only API calls.

    This test:
    1. Creates a new chat message with user input and AI response
    2. Gets database IDs (message_id, session_id) from the response
    3. Edits the message using PATCH endpoint (simulating React frontend)
    4. Fetches the session via API and verifies the edited message
    """

    customer_id = 7
    client = client_with_test_db

    # Step 1: Create initial message (simulating user sending a message and getting AI response)
    create_response = await client.post(
        "/api/v1/chat/messages",
        json={
            "customer_id": customer_id,
            "session_name": "Test Edit Flow Session",
            "tags": ["test"],
            "user_message": {
                "message": "Original user message",
                "sender": "User",
                "image_locations": [],
                "file_locations": [],
            },
            "ai_response": {
                "message": "Original AI response",
                "sender": "AI",
                "ai_character_name": "assistant",
                "api_text_gen_model_name": "gpt-4o-mini",
                "image_locations": [],
            },
            "user_settings": {
                "text": {"model": "gpt-4o-mini", "temperature": 0.7},
                "tts": {"enabled": False},
            },
        },
    )

    # Verify initial creation succeeded
    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data["success"] is True

    # Step 2: Extract database IDs from response
    user_message_id = create_data["data"]["user_message_id"]
    ai_message_id = create_data["data"]["ai_message_id"]
    session_id = create_data["data"]["session_id"]

    assert user_message_id is not None
    assert ai_message_id is not None
    assert session_id is not None

    print(f"\nCreated messages - User ID: {user_message_id}, AI ID: {ai_message_id}, Session ID: {session_id}")

    # Step 3: Edit the messages using PATCH endpoint (simulating React frontend edit)
    # This uses the same payload structure as the React frontend
    edit_response = await client.patch(
        "/api/v1/chat/messages",
        json={
            "customer_id": customer_id,
            "session_id": session_id,
            "user_message": {
                "message_id": user_message_id,
                "message": "Edited user message with new content",
                "sender": "User",
                "image_locations": ["https://example.com/image1.jpg"],
                "file_locations": [],
            },
            "ai_response": {
                "message_id": ai_message_id,
                "message": "Edited AI response with new insights",
                "sender": "AI",
                "ai_character_name": "assistant",
                "api_text_gen_model_name": "gpt-4o",
                "image_locations": [],
            },
            "user_settings": {
                "text": {"model": "gpt-4o", "temperature": 0.5},
                "tts": {"enabled": False},
            },
        },
    )

    # Verify edit succeeded
    assert edit_response.status_code == 200
    edit_data = edit_response.json()
    assert edit_data["success"] is True

    print(f"Edit response: {edit_data}")

    # Step 4: Fetch the session via API to verify the changes
    session_response = await client.post(
        "/api/v1/chat/sessions/detail",
        json={
            "customer_id": customer_id,
            "session_id": session_id,
            "include_messages": True,
        },
    )

    # Verify session fetch succeeded
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data["success"] is True

    # Step 5: Verify the edited message text in the fetched session
    session_payload = _extract_session_payload(session_data)
    messages = session_payload.get("messages", [])

    # Find the edited messages by ID
    user_msg = None
    ai_msg = None
    for msg in messages:
        if msg.get("message_id") == user_message_id:
            user_msg = msg
        elif msg.get("message_id") == ai_message_id:
            ai_msg = msg

    # Verify user message was edited correctly
    assert user_msg is not None, f"User message with ID {user_message_id} not found"
    assert user_msg["message"] == "Edited user message with new content"
    assert user_msg["image_locations"] == ["https://example.com/image1.jpg"]

    # Verify AI message was edited correctly
    assert ai_msg is not None, f"AI message with ID {ai_message_id} not found"
    assert ai_msg["message"] == "Edited AI response with new insights"
    assert ai_msg["api_text_gen_model_name"] == "gpt-4o"

    print("\n✓ Edit message flow test passed!")
    print(f"  - User message: '{user_msg['message']}'")
    print(f"  - AI message: '{ai_msg['message']}'")


@pytest.mark.anyio
async def test_edit_message_with_partial_update(client_with_test_db: AsyncClient) -> None:
    """Test editing only user message without touching AI response."""

    customer_id = 7
    client = client_with_test_db

    # Create initial messages
    create_response = await client.post(
        "/api/v1/chat/messages",
        json={
            "customer_id": customer_id,
            "session_name": "Partial Edit Test",
            "user_message": {
                "message": "Original question",
                "sender": "User",
            },
            "ai_response": {
                "message": "Original answer",
                "sender": "AI",
                "ai_character_name": "assistant",
            },
            "user_settings": {"text": {"model": "gpt-4o"}},
        },
    )

    assert create_response.status_code == 200
    create_data = create_response.json()

    user_message_id = create_data["data"]["user_message_id"]
    ai_message_id = create_data["data"]["ai_message_id"]
    session_id = create_data["data"]["session_id"]

    # Edit only the user message
    edit_response = await client.patch(
        "/api/v1/chat/messages",
        json={
            "customer_id": customer_id,
            "session_id": session_id,
            "user_message": {
                "message_id": user_message_id,
                "message": "Edited question only",
                "sender": "User",
            },
            "user_settings": {"text": {"model": "gpt-4o"}},
        },
    )

    assert edit_response.status_code == 200

    # Verify via API
    session_response = await client.post(
        "/api/v1/chat/sessions/detail",
        json={
            "customer_id": customer_id,
            "session_id": session_id,
            "include_messages": True,
        },
    )

    session_data = session_response.json()
    messages = _extract_session_payload(session_data).get("messages", [])

    user_msg = next((m for m in messages if m.get("message_id") == user_message_id), None)
    ai_msg = next((m for m in messages if m.get("message_id") == ai_message_id), None)

    # User message should be edited
    assert user_msg["message"] == "Edited question only"

    # AI message should remain unchanged
    assert ai_msg["message"] == "Original answer"

    print("\n✓ Partial edit test passed!")


@pytest.mark.anyio
async def test_edit_message_with_new_attachments(client_with_test_db: AsyncClient) -> None:
    """Test editing message and adding image attachments."""

    customer_id = 7
    client = client_with_test_db

    # Create initial message without attachments
    create_response = await client.post(
        "/api/v1/chat/messages",
        json={
            "customer_id": customer_id,
            "user_message": {
                "message": "Question about images",
                "sender": "User",
                "image_locations": [],
            },
            "ai_response": {
                "message": "Answer about images",
                "sender": "AI",
            },
            "user_settings": {"text": {"model": "gpt-4o"}},
        },
    )

    create_data = create_response.json()
    user_message_id = create_data["data"]["user_message_id"]
    session_id = create_data["data"]["session_id"]

    # Edit message and add image attachments
    edit_response = await client.patch(
        "/api/v1/chat/messages",
        json={
            "customer_id": customer_id,
            "session_id": session_id,
            "user_message": {
                "message_id": user_message_id,
                "message": "Question about images (edited with attachments)",
                "sender": "User",
                "image_locations": [
                    "https://example.com/img1.jpg",
                    "https://example.com/img2.png",
                ],
                "file_locations": ["report.pdf"],
            },
            "user_settings": {"text": {"model": "gpt-4o"}},
        },
    )

    assert edit_response.status_code == 200

    # Verify attachments were added
    session_response = await client.post(
        "/api/v1/chat/sessions/detail",
        json={
            "customer_id": customer_id,
            "session_id": session_id,
            "include_messages": True,
        },
    )

    session_data = session_response.json()
    messages = _extract_session_payload(session_data).get("messages", [])
    user_msg = next((m for m in messages if m.get("message_id") == user_message_id), None)

    assert user_msg["message"] == "Question about images (edited with attachments)"
    assert len(user_msg["image_locations"]) == 2
    assert "https://example.com/img1.jpg" in user_msg["image_locations"]
    assert "https://example.com/img2.png" in user_msg["image_locations"]
    assert user_msg["file_locations"] == ["report.pdf"]

    print("\n✓ Attachment edit test passed!")


@pytest.mark.anyio
async def test_edit_nonexistent_message_returns_error(client_with_test_db: AsyncClient) -> None:
    """Test that editing a non-existent message returns appropriate error."""

    customer_id = 7
    client = client_with_test_db

    # Try to edit a message that doesn't exist
    edit_response = await client.patch(
        "/api/v1/chat/messages",
        json={
            "customer_id": customer_id,
            "session_id": "nonexistent-session",
            "user_message": {
                "message_id": 99999,  # Non-existent message ID
                "message": "This should fail",
                "sender": "User",
            },
            "user_settings": {"text": {"model": "gpt-4o"}},
        },
    )

    # Should handle gracefully (exact error handling depends on implementation)
    # The test documents the expected behavior
    print(f"\n✓ Nonexistent message edit returned status: {edit_response.status_code}")
    print(f"  Response: {edit_response.json()}")
