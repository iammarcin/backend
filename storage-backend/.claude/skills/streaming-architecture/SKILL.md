# Streaming Architecture Skill

This skill encodes the **StreamingManager** and **token-based completion ownership** pattern for managing WebSocket/SSE streams.

**Tags:** `#streaming` `#websocket` `#sse` `#token-ownership` `#architecture`

## Problem We're Solving

**Challenge**: In a workflow with multiple consumers (WebSocket, TTS, etc.), who decides when the stream ends?

**Solution**: Token-based completion ownership - only the code holding the token can signal completion.

## Token-Based Completion Pattern

### The Rule: One Token Per Workflow

```python
# Top-level dispatcher creates ONCE
token = manager.create_completion_token()

# Token is passed down the call stack
await workflow.execute(messages, completion_token=token)

# Only token holder can complete
await manager.signal_completion(token=token)
```

### Token Lifecycle

```
1. Dispatcher creates token
   token = manager.create_completion_token()

2. Dispatcher passes token to workflow
   await workflow.execute(..., completion_token=token)

3. Workflow passes token to sub-workflows
   await sub_workflow.execute(..., completion_token=token)

4. Leaf operations DON'T call signal_completion()
   - They stream events and return
   - They pass token to anything they call

5. Dispatcher completes (after all sub-operations)
   await manager.signal_completion(token=token)
```

## Implementation

### StreamingManager Class

```python
# core/streaming/manager.py
import uuid
from typing import Optional

class StreamingManager:
    """Manages token-based completion ownership for streams."""

    def __init__(self):
        self._active_tokens: set[str] = set()
        self._completed_tokens: set[str] = set()

    def create_completion_token(self) -> str:
        """Create a new completion token (call once per workflow)."""
        token = str(uuid.uuid4())
        self._active_tokens.add(token)
        return token

    async def signal_completion(self, token: str) -> None:
        """Signal that workflow is complete (only token holder)."""
        if token not in self._active_tokens:
            raise CompletionOwnershipError(
                f"Token {token} is not active. Already completed or invalid."
            )

        self._active_tokens.discard(token)
        self._completed_tokens.add(token)

        # Notify all listeners
        await self._notify_completion(token)

    def is_completed(self, token: str) -> bool:
        """Check if token workflow has completed."""
        return token in self._completed_tokens

    async def _notify_completion(self, token: str) -> None:
        """Internal - notify all listeners of completion."""
        # Broadcast to WebSocket connections, TTS processors, etc.
        pass

# Global manager instance
manager = StreamingManager()
```

### Exception Type

```python
# core/exceptions.py
class CompletionOwnershipError(Exception):
    """Raised when attempting to complete without proper token ownership."""
    pass
```

## Usage in WebSocket Endpoint

### WebSocket Handler Pattern

```python
# features/chat/routes.py
from core.streaming.manager import manager

@router.websocket("/chat/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket chat endpoint."""
    await websocket.accept()

    # ... authentication, initial setup ...

    # CREATE TOKEN ONCE for this WebSocket connection
    completion_token = manager.create_completion_token()

    try:
        # Get initial request
        request_data = await websocket.receive_json()
        messages = request_data["messages"]

        # Execute workflow, passing token
        workflow = ChatWorkflow()
        async for event in workflow.execute(
            messages=messages,
            completion_token=completion_token,
        ):
            # Stream events to client
            await websocket.send_json(event.to_dict())

        # Send final completion events (BEFORE signal_completion)
        await websocket.send_json({
            "type": "textCompleted",
            "data": {"total_tokens": ...},
        })
        await websocket.send_json({"type": "complete"})

        # NOW signal completion (only we hold the token)
        await manager.signal_completion(token=completion_token)

    except WebSocketDisconnect:
        await manager.signal_completion(token=completion_token)
    except Exception as exc:
        # Send error event
        await websocket.send_json({
            "type": "error",
            "data": {"message": str(exc)},
        })
        await manager.signal_completion(token=completion_token)
```

## Usage in Workflow Layers

### Top-Level Workflow

```python
# features/chat/services/streaming/chat_workflow.py
class ChatWorkflow:
    """Top-level chat workflow."""

    async def execute(
        self,
        messages: list[dict],
        completion_token: str,  # Receives token from dispatcher
    ) -> AsyncGenerator[WorkflowEvent, None]:
        """Execute chat with optional agents."""

        # Determine sub-workflow
        enable_agent = settings.agentic_enabled
        if enable_agent:
            sub_workflow = AgenticWorkflow()
        else:
            sub_workflow = StandardWorkflow()

        # PASS TOKEN DOWN (don't call signal_completion here)
        async for event in sub_workflow.execute(
            messages=messages,
            completion_token=completion_token,  # Pass it along
        ):
            yield event

        # Return (don't complete - dispatcher will)
```

### Intermediate Workflow

```python
# features/chat/services/streaming/agentic_workflow.py
class AgenticWorkflow:
    """Agentic workflow - iterates with tools."""

    async def execute(
        self,
        messages: list[dict],
        completion_token: str,  # Receives token
    ) -> AsyncGenerator[WorkflowEvent, None]:
        """Execute agentic iterations."""

        current_messages = messages.copy()

        for iteration in range(MAX_ITERATIONS):
            # Call LLM
            response = await self._call_llm_with_tools(...)

            yield WorkflowEvent(type="text", data={"content": response.content})

            if not response.has_tool_calls:
                # Done iterating
                break

            # Execute tools (but don't complete)
            for tool_call in response.tool_calls:
                tool_result = await self._execute_tool(tool_call)
                yield WorkflowEvent(type="toolResult", data={...})

                # Append to messages for next iteration
                current_messages.append({...})

        # Return (don't complete - dispatcher will)
```

### Leaf Operation (TTS, etc.)

```python
# features/tts/services/tts_service.py
class TTSService:
    """Text-to-speech service."""

    async def synthesize_and_stream(
        self,
        text: str,
        completion_token: str,  # Receives but doesn't use to complete
    ) -> AsyncGenerator[AudioChunk, None]:
        """Synthesize text to speech and stream."""

        provider = get_tts_provider()

        async for chunk in provider.synthesize_stream(text):
            yield chunk

        # Return (DON'T call manager.signal_completion - we don't own the token)
```

## Event Contract

**CRITICAL**: Workflows must send proper completion events in `finally` blocks:

```python
async def execute(self, ..., completion_token: str) -> AsyncGenerator:
    try:
        # ... do work ...
        async for event in sub_workflow.execute(..., completion_token=completion_token):
            yield event

        # Workflow succeeded - send completion event
        yield WorkflowEvent(type="textCompleted")
        yield WorkflowEvent(type="complete")

    except Exception as exc:
        # Error - send error event
        yield WorkflowEvent(type="error", data={"message": str(exc)})
        yield WorkflowEvent(type="textNotRequested")

    finally:
        # Never call signal_completion here unless you own token
        # Dispatcher will call it
        pass
```

## Common Event Types

### Lifecycle Events
- `working` - Workflow is processing
- `iterationStarted` - Agentic iteration started
- `iterationCompleted` - Agentic iteration completed

### Content Events
- `text` - Text chunk
- `textCompleted` - Text generation complete
- `textNotRequested` - Text generation was skipped
- `audio` - Audio chunk
- `ttsCompleted` - TTS complete
- `ttsNotRequested` - TTS was skipped

### Tool Events
- `toolCall` - Tool was invoked
- `toolResult` - Tool result available

### Completion Events
- `complete` - All work done
- `fullProcessComplete` - Full workflow complete
- `error` - Error occurred

## Testing Patterns

### Testing Token Ownership

```python
import pytest
from core.streaming.manager import manager, CompletionOwnershipError

@pytest.mark.asyncio
async def test_completion_ownership():
    """Test that only token owner can complete."""
    token = manager.create_completion_token()

    # Correct: owner completes
    await manager.signal_completion(token=token)

    # Incorrect: using token after completion
    with pytest.raises(CompletionOwnershipError):
        await manager.signal_completion(token=token)

@pytest.mark.asyncio
async def test_multiple_tokens():
    """Test multiple independent workflows."""
    token1 = manager.create_completion_token()
    token2 = manager.create_completion_token()

    # Each can complete independently
    await manager.signal_completion(token=token1)
    assert manager.is_completed(token1)
    assert not manager.is_completed(token2)

    await manager.signal_completion(token=token2)
    assert manager.is_completed(token2)
```

### Testing Event Streaming

```python
@pytest.mark.asyncio
async def test_workflow_events():
    """Test workflow emits correct event sequence."""
    token = manager.create_completion_token()

    events = []
    async for event in workflow.execute(
        messages=[...],
        completion_token=token,
    ):
        events.append(event)

    # Verify event order
    assert events[0].type == "working"
    assert any(e.type == "text" for e in events)
    assert events[-1].type == "complete"
```

## Migration Guide

### Old Pattern (Don't Do This)

```python
# ❌ Multiple places calling signal_completion
async def workflow(messages):
    result = await llm.generate(messages)
    yield {"type": "text", "data": result}
    await manager.signal_completion()  # ❌ Wrong

async def websocket():
    async for event in workflow(messages):
        send(event)
    await manager.signal_completion()  # ❌ Wrong - called twice
```

### New Pattern (Correct)

```python
# ✅ Single completion point (dispatcher)
async def workflow(messages, completion_token):
    result = await llm.generate(messages)
    yield {"type": "text", "data": result}
    # Don't complete - return and let dispatcher do it

async def websocket():
    token = manager.create_completion_token()
    async for event in workflow(messages, completion_token=token):
        send(event)
    await manager.signal_completion(token=token)  # ✅ Correct - single point
```

## Troubleshooting

### Issue: "CompletionOwnershipError"
**Cause**: Multiple places trying to complete, or completing twice
**Solution**: Trace call stack - only dispatcher should complete

### Issue: Stream doesn't close
**Cause**: Dispatcher forgot to call signal_completion
**Solution**: Check WebSocket handler has try/finally with completion call

### Issue: Events arriving after completion
**Cause**: Events yielded after completion signal
**Solution**: Send completion events BEFORE calling signal_completion

## See Also
- `@storage-backend/CLAUDE.md` - Full backend architecture
- `@storage-backend/DocumentationApp/websocket-events-handbook.md` - Event contract
- `@storage-backend/core/streaming/manager.py` - Implementation
- `@storage-backend/features/chat/services/streaming/` - Usage examples
