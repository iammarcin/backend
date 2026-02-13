# Edit Message Flow Integration Tests

## Overview

The `test_edit_message_flow.py` file contains comprehensive integration tests for the message editing functionality. These tests simulate the React frontend behavior by making real API calls to the backend and verifying the results through the database.

## What's Being Tested

1. **Complete Edit Flow**: Creates a message, edits both user and AI messages, and verifies changes via API
2. **Partial Edit**: Edits only the user message while leaving AI response unchanged
3. **Attachment Editing**: Adds/modifies image attachments and files during message editing
4. **Error Handling**: Tests behavior when editing non-existent messages

## Key Features

- **API-Based Testing**: All operations use HTTP API calls (POST, PATCH) - no direct database queries
- **Real Database**: Uses an in-memory SQLite database for true integration testing
- **Frontend Simulation**: Payloads match exactly what the React frontend sends

## Running the Tests

### Inside Docker Container

```bash
docker compose exec storage-backend pytest tests/integration/chat/test_edit_message_flow.py -v
```

### Outside Docker Container

The tests use an in-memory SQLite database and can run outside Docker:

```bash
cd docker/storage-backend
pytest tests/integration/chat/test_edit_message_flow.py -v
```

### Run Specific Test

```bash
# Inside Docker
docker compose exec storage-backend pytest tests/integration/chat/test_edit_message_flow.py::test_complete_edit_message_flow_via_api -v

# Outside Docker
pytest tests/integration/chat/test_edit_message_flow.py::test_complete_edit_message_flow_via_api -v
```

### With Output Capture

```bash
# Save results to file
docker compose exec storage-backend pytest tests/integration/chat/test_edit_message_flow.py -v > test_results.txt 2>&1
```

## Test Architecture

### Fixtures

- `test_user`: Creates a test user with customer_id=7
- `client_with_test_db`: Provides an AsyncClient connected to the test database
- `session`: In-memory SQLite database session (from conftest.py)

### API Endpoints Used

1. **POST /api/v1/chat/messages** - Create new messages
2. **PATCH /api/v1/chat/messages** - Edit existing messages
3. **POST /api/v1/chat/sessions/detail** - Fetch session with messages

### Data Flow

```
1. Create Message (POST)
   ↓
2. Extract IDs (session_id, message_id) from response
   ↓
3. Edit Message (PATCH) with same payload as React frontend
   ↓
4. Fetch Session (POST) to verify changes
   ↓
5. Assert edited message text matches expected value
```

## Example Test Flow

```python
# 1. Create initial message
response = await client.post("/api/v1/chat/messages", json={
    "customer_id": 7,
    "user_message": {"message": "Original text"},
    "ai_response": {"message": "Original AI response"},
    "user_settings": {...}
})

# 2. Get IDs from response
message_id = response.json()["data"]["user_message_id"]
session_id = response.json()["data"]["session_id"]

# 3. Edit the message
await client.patch("/api/v1/chat/messages", json={
    "customer_id": 7,
    "session_id": session_id,
    "user_message": {
        "messageId": message_id,
        "message": "Edited text"
    }
})

# 4. Verify via API
session_response = await client.post("/api/v1/chat/sessions/detail", json={
    "customer_id": 7,
    "session_id": session_id,
    "include_messages": True
})

# 5. Assert
messages = session_response.json()["data"]["session"]["messages"]
assert messages[0]["message"] == "Edited text"
```

## Payload Structure

### Create Message Request

```json
{
  "customer_id": 7,
  "session_name": "Test Session",
  "tags": ["test"],
  "user_message": {
    "message": "User input",
    "sender": "User",
    "image_locations": [],
    "file_locations": []
  },
  "ai_response": {
    "message": "AI response",
    "sender": "AI",
    "ai_character_name": "assistant",
    "api_text_gen_model_name": "gpt-4o-mini"
  },
  "user_settings": {
    "text": {"model": "gpt-4o-mini", "temperature": 0.7},
    "tts": {"enabled": false}
  }
}
```

### Edit Message Request (PATCH)

```json
{
  "customer_id": 7,
  "session_id": "sess-123",
  "user_message": {
    "message_id": 5,
    "message": "Edited user input",
    "sender": "User",
    "image_locations": ["https://example.com/img.jpg"]
  },
  "ai_response": {
    "message_id": 6,
    "message": "Edited AI response",
    "sender": "AI",
    "api_text_gen_model_name": "gpt-4o"
  },
  "user_settings": {
    "text": {"model": "gpt-4o"}
  }
}
```

## Dependencies

The tests require:
- `pytest`
- `pytest-asyncio`
- `httpx`
- `sqlalchemy[asyncio]`
- `aiosqlite` (for in-memory SQLite)
- `bcrypt`

These are typically already installed in the Docker container and in the project's dev dependencies.

## Troubleshooting

### Test Fails with "Module not found"

Ensure you're running from the correct directory:
```bash
cd docker/storage-backend
pytest tests/integration/chat/test_edit_message_flow.py -v
```

### Database Connection Errors

The tests use an in-memory database and don't require a real database connection. If you see database errors, check that the `session` fixture from `conftest.py` is being properly loaded.

### Import Errors

The tests mock the `itisai_brain` module. If you see import errors, ensure the mocking code is executed before other imports.

## Future Enhancements

Potential improvements to consider:
- Add tests for concurrent message edits
- Test websocket-based message editing
- Add tests for message history/audit trail
- Test editing messages with complex attachments (PDFs, videos)
- Add performance tests for editing large messages
