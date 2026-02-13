# Edit Message Integration Tests

## Overview

These tests verify the edit message functionality that ensures editing a message **updates** the existing database record instead of creating a new one. This is critical for matching React frontend behavior with Kotlin frontend behavior.

## Test File

`test_edit_message_flow.py` - Comprehensive integration tests for the edit message flow

## Tests Included

### 1. `test_new_message_creates_session_and_messages`

**Purpose:** Verify baseline - new messages create session and message records correctly

**Flow:**
1. Send new message via WebSocket
2. Collect `dbOperationExecuted` event
3. Verify session created in database
4. Verify both user and AI messages created
5. Verify message count is 1

**Validates:**
- Session creation works
- Message IDs are returned correctly
- Database persistence works

---

### 2. `test_edit_message_updates_existing_record` ⭐

**Purpose:** THE CRITICAL TEST - Verify editing updates records instead of inserting new ones

**Flow:**
1. Send initial message: "Original message"
2. Collect session ID and message IDs from `dbOperationExecuted`
3. Verify initial message count = 1
4. Send edit message with:
   - `is_edited_message: true`
   - `messageId` fields populated
   - Same session ID
5. Collect second `dbOperationExecuted`
6. Verify **SAME IDs** returned (not new IDs)
7. Query database and verify:
   - Message count still = 1 (UPDATE not INSERT)
   - User message text = "Edited message"
   - AI message updated with new response

**Validates:**
- `is_edited_message` flag triggers UPDATE path
- Message IDs are used to find existing records
- No duplicate messages created
- Both user and AI messages updated

**This is the test that would have caught the React bug!**

---

### 3. `test_multiple_messages_in_same_session`

**Purpose:** Verify session tracking fix - multiple messages share same session

**Flow:**
1. Send first message (creates session)
2. Collect session ID from `dbOperationExecuted`
3. Send second message WITH session_id populated
4. Verify second message returns **SAME session ID**
5. Query database and verify both messages in same session

**Validates:**
- Session ID tracking works (the second bug we fixed)
- Chat history properly includes previous messages
- Multiple messages link to same session

---

### 4. `test_edit_middle_message_preserves_later_messages`

**Purpose:** Verify editing doesn't affect unrelated messages

**Flow:**
1. Send message A
2. Send message B
3. Edit message A
4. Verify message B still exists unchanged

**Validates:**
- Edit operation is isolated
- Later messages not affected
- Message count remains correct

---

## Running the Tests

### Run All Edit Message Tests

```bash
# Inside container or on host with pytest
pytest tests/integration/chat/test_edit_message_flow.py -v
```

### Run Specific Test

```bash
# Run just the critical edit test
pytest tests/integration/chat/test_edit_message_flow.py::test_edit_message_updates_existing_record -v

# Run session tracking test
pytest tests/integration/chat/test_edit_message_flow.py::test_multiple_messages_in_same_session -v
```

### Run with Coverage

```bash
pytest tests/integration/chat/test_edit_message_flow.py --cov=features.chat --cov-report=html
```

### Run All Chat Integration Tests

```bash
pytest tests/integration/chat/ -v
```

## Expected Output

### Successful Run

```
tests/integration/chat/test_edit_message_flow.py::test_new_message_creates_session_and_messages PASSED
tests/integration/chat/test_edit_message_flow.py::test_edit_message_updates_existing_record PASSED
tests/integration/chat/test_edit_message_flow.py::test_multiple_messages_in_same_session PASSED
tests/integration/chat/test_edit_message_flow.py::test_edit_message_updates_existing_record PASSED

========== 4 passed in 2.34s ==========
```

### If Edit Functionality Breaks

The tests will fail with clear messages:

```
AssertionError: Edit should UPDATE existing message, not create new one
Expected: 1 message
Got: 2 messages
```

## Test Database

These tests use an **in-memory SQLite database** (from `conftest.py` fixture):
- Created fresh for each test
- No persistence between tests
- No cleanup needed
- Fast execution

Database schema is created automatically using `prepare_database(engine)`.

## Payload Structure

The tests use the exact payload structure from the React frontend after the fix:

```json
{
  "requestType": "text",
  "userInput": {
    "prompt": [{"type": "text", "text": "..."}],
    "chat_history": [...],
    "session_id": "uuid-here",
    "userMessage": {
      "message": "...",
      "isUserMessage": true,
      "messageId": 9036,  // ← Present when editing
      ...
    },
    "aiResponse": {
      "message": "",
      "isUserMessage": false,
      "messageId": 9037,  // ← Present when editing
      ...
    },
    "is_edited_message": true,  // ← Key flag
    "customer_id": 1
  },
  "userSettings": {...}
}
```

## Stub Provider

Tests use `EditMessageStubProvider` which:
- Returns predictable responses: "Response 1", "Response 2", etc.
- Supports streaming
- Counts calls to verify edit generates new response
- Fast execution (no real API calls)

## What These Tests Catch

### ✅ Would Have Caught

1. **Missing `is_edited_message` flag** → `test_edit_message_updates_existing_record` would fail with 2 messages instead of 1
2. **Session ID not tracked** → `test_multiple_messages_in_same_session` would fail with different session IDs
3. **MessageIds not used** → Edit test would create new records instead of updating

### ✅ Prevents Regressions

- Editing creates duplicates
- Session tracking breaks
- Message IDs not returned
- Database persistence fails

### ✅ Documents Expected Behavior

- New message: `is_edited_message: false`, no messageIds
- Edit message: `is_edited_message: true`, messageIds populated
- Multiple messages: Same session_id used

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Run Edit Message Tests
  run: |
    docker exec backend pytest tests/integration/chat/test_edit_message_flow.py -v
```

Or with docker-compose:

```bash
docker-compose exec backend pytest tests/integration/chat/test_edit_message_flow.py -v
```

## Debugging Failed Tests

### Test Fails with "No dbOperationExecuted event"

**Cause:** Backend not sending the event or test not collecting it

**Fix:**
1. Check backend logs: `docker logs backend`
2. Verify `history_persistence.py` sends event
3. Ensure WebSocket message handler in `api.websocket.js` parses it

### Test Fails with "Message count = 2"

**Cause:** Edit is creating new record instead of updating

**Fix:**
1. Verify `is_edited_message: true` in payload
2. Check backend edit detection logic
3. Verify messageIds are being used to find records

### Test Fails with "Different session IDs"

**Cause:** Session ID not being passed correctly

**Fix:**
1. Verify `session_id` in payload
2. Check frontend stores `db_session_id` after first message
3. Verify frontend passes stored ID with second message

## Future Enhancements

Potential additional tests:

1. **Edit with attachments** - Verify images/files preserved
2. **Edit after character switch** - Verify character name updated
3. **Concurrent edits** - Verify last-write-wins
4. **Edit permissions** - Verify user can only edit their messages
5. **Edit history** - If implementing edit history, verify all versions stored

## Related Files

**Backend:**
- `features/chat/utils/history_persistence.py` - DB persistence logic
- `features/chat/repositories/message.py` - Message CRUD operations
- `features/chat/utils/websocket_workflows.py` - Workflow handlers

**Frontend (React):**
- `storage-react/src/services/call.chat.api.js` - Payload building
- `storage-react/src/utils/streamingUtils.js` - Payload preparation
- `storage-react/src/services/api.websocket.js` - WebSocket handling

**Documentation:**
- `/DocumentationResearch/react-edit-message-fix-*.md` - Full analysis and fix
- `/DocumentationResearch/HOTFIX-v2-session-id-tracking.md` - Session ID fix

## Questions?

If tests fail or behavior is unexpected:

1. Check this README for debugging steps
2. Review backend logs for errors
3. Compare payload structure with working Kotlin frontend
4. Consult the documentation in `/DocumentationResearch/`
