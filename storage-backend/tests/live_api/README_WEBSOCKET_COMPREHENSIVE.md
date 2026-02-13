# Comprehensive WebSocket Live API Tests

## Overview

This test suite validates WebSocket functionality using **real WebSocket connections** (not TestClient). After implementing the cancellation feature, TestClient-based WebSocket tests began hanging due to concurrent task processing incompatibility.

## Tests Included

1. **Basic Chat Flow** - Text streaming, completion events
2. **Chat with TTS Events** - TTS coordination, event ordering
3. **Tool Call Event Ordering** - Agentic workflows, tool execution

## Running the Tests

```bash
# Run from HOST machine (not inside Docker container)
RUN_MANUAL_TESTS=1 pytest tests/live_api/test_websocket_comprehensive.py -v -s

# Or with requires_docker marker
RUN_MANUAL_TESTS=1 pytest -m requires_docker -v -s
```

## Requirements

- Backend must be running: `docker-compose up -d backend`
- Valid JWT token (tests use `auth_token_factory` fixture)
- Backend accessible at `ws://localhost:8000/chat/ws` (or set `BACKEND_WS_URL`)

## Expected Output

```
🔗 Test 1: Basic Chat Flow
   Connecting to: ws://localhost:8000/chat/ws
   ✅ WebSocket connected
   Session ID: abc-123-def
   📤 Sending chat request...
   ✅ Received 15 text chunks
   ✅ Full text: Hello! How can I help...
   ✅ Events: websocketReady → working → text → text → ...

🔗 Test 2: Chat with TTS Events
   Connecting to: ws://localhost:8000/chat/ws
   ✅ WebSocket connected
   📤 Sending chat request with TTS enabled...
   ✅ Text events: True
   ✅ TTS coordination: True
   ✅ Event sequence: websocketReady → working → text → ...

🔗 Test 3: Tool Call Event Ordering
   Connecting to: ws://localhost:8000/chat/ws
   ✅ WebSocket connected
   📤 Sending agentic request...
   1. websocketReady
   2. working
   3. customEvent → TOOL: generate_image
   4. customEvent → RESULT: success
   ...
   📊 Total events: 45
   📊 Tool events: 2
   ✅ Tool calls detected: 1
   ✅ Tool results received: 1
   ✅ Tools used: ['generate_image']
   ✅ Event ordering validated

============================================================
✅ ALL WEBSOCKET TESTS PASSED
============================================================
```

## Replaced Tests

This comprehensive test replaces the following TestClient-based tests that hang:

- `tests/features/chat/test_chat_xai_endpoints.py::test_websocket_flow_emits_ordered_tool_call_events`
- `tests/integration/test_websocket_chat.py::test_websocket_chat`
- `tests/integration/test_websocket_chat.py::test_websocket_chat_with_tts_events`

## Why Not TestClient?

TestClient's WebSocket implementation doesn't handle the concurrent task-based message processing introduced in the cancellation feature. The pattern:

```python
asyncio.create_task(workflow)
asyncio.create_task(receive_message)
await asyncio.wait([...], return_when=FIRST_COMPLETED)
```

This causes TestClient to hang indefinitely. Real WebSocket connections work correctly.

## Troubleshooting

### Connection Refused
```
❌ Connection failed: invalid status code
```
→ Backend not running or JWT expired

### Timeout
```
⏱️  Timeout waiting for events
```
→ Backend hung or request failed silently

### No Tool Calls
```
Expected tool calls. Received N events but 0 tool calls
```
→ Agentic workflow not triggering tools (check model, settings, prompt)

### Wrong Event Types
```
Expected 'custom_event' with event_type='toolUse'
```
→ Backend event structure changed, update test expectations

## Related Files

- `tests/manual/test_anthropic_agentic_manual.py` - Manual Anthropic test
- `tests/manual/test_session_persistence_manual.py` - Session persistence test
- `tests/live_api/test_anthropic_agentic_real_websockets.py` - Anthropic pytest version
