# Agentic Workflows Skill

This skill encodes how **agentic workflows** work in BetterAI backend - how LLMs can call internal tools iteratively.

**Tags:** `#agentic` `#agents` `#tool-calling` `#ai-models` `#workflows`

## What is an Agentic Workflow?

An **agentic workflow** lets an LLM:
1. Analyze user request
2. Decide which internal tools to call
3. Execute those tools (image generation, video, browser automation, text)
4. Iterate based on results (up to 10 iterations by default)
5. Return final response

**All workflows are configured and controlled by settings in `config/agentic/`**

## Configuration System (config/agentic/)

### settings.py - Loop Control
```python
# Maximum iterations before stopping
AGENTIC_MAX_ITERATIONS = 10

# Timeout for entire workflow
AGENTIC_TIMEOUT_SECONDS = 300

# Whether agentic mode is enabled
AGENTIC_ENABLED = os.getenv("AGENTIC_ENABLED", "true").lower() == "true"
```

### profiles.py - Tool Availability

```python
AGENTIC_PROFILES = {
    "general": {
        "tools": [
            "text_generation",  # Generate text
        ],
        "description": "General purpose agent",
    },
    "media": {
        "tools": [
            "text_generation",
            "image_generation",
            "video_generation",
        ],
        "description": "Content creation agent",
    },
    "automation": {
        "tools": [
            "text_generation",
            "browser_automation",
            "image_generation",
        ],
        "description": "Task automation agent",
    },
}
```

### prompts.py - Tool Descriptions

```python
AGENTIC_TOOL_PROMPTS = {
    "text_generation": """
Tool for generating text. Use this to:
- Write articles, stories, code
- Answer questions
- Analyze information

Parameters:
- prompt: The text generation prompt
- model: Optional specific model to use
""",
    "image_generation": """
Tool for generating images. Use this to:
- Create illustrations
- Design mockups
- Generate visual content

Parameters:
- prompt: Image description
- model: Optional specific model
- size: Optional image size
""",
    "video_generation": """
Tool for generating videos. Use this to:
- Create video content
- Animate concepts
- Generate demos

Parameters:
- prompt: Video description
- duration: Optional video length
""",
    "browser_automation": """
Tool for web automation. Use this to:
- Extract information from websites
- Fill forms
- Navigate web pages
- Take screenshots

Parameters:
- action: The action to perform (navigate, extract, fill_form, screenshot)
- url: Target website
- instructions: Detailed instructions
""",
}
```

## Tool System (core/tools/)

### Tool Registration

```python
# core/tools/registry.py

# Tools are registered at import time
AVAILABLE_TOOLS = {
    "text_generation": TextGenerationTool(),
    "image_generation": ImageGenerationTool(),
    "video_generation": VideoGenerationTool(),
    "browser_automation": BrowserAutomationTool(),
}

def get_available_tools_for_profile(profile: str) -> list[Tool]:
    """Get tools available for a profile."""
    if profile not in AGENTIC_PROFILES:
        raise ValidationError(f"Unknown profile: {profile}")

    tool_names = AGENTIC_PROFILES[profile]["tools"]
    return [AVAILABLE_TOOLS[name] for name in tool_names if name in AVAILABLE_TOOLS]
```

### Tool Base Class

```python
from abc import ABC, abstractmethod
from typing import Any

class Tool(ABC):
    """Base class for all internal tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the tool."""
        pass
```

### Tool Implementation Example

```python
class ImageGenerationTool(Tool):
    """Tool for image generation."""

    @property
    def name(self) -> str:
        return "image_generation"

    @property
    def description(self) -> str:
        return AGENTIC_TOOL_PROMPTS.get("image_generation", "")

    async def execute(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Generate an image."""
        try:
            # Get appropriate provider
            image_provider = get_image_provider(model_name=model)

            # Generate image
            result = await image_provider.generate(
                prompt=prompt,
                size=size or "1024x1024",
            )

            return {
                "success": True,
                "image_url": result.image_url,
                "model": result.model,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
            }
```

## Agentic Workflow Execution (features/chat/services/streaming/agentic.py)

### Workflow Loop

```python
class AgenticWorkflow:
    """Orchestrates LLM + tool iterations."""

    async def execute(
        self,
        messages: list[dict],
        profile: str = "general",
        completion_token: Optional[CompletionToken] = None,
    ) -> AsyncGenerator[WorkflowEvent, None]:
        """Execute agentic workflow with tool-calling loop."""

        # Get available tools for profile
        tools = get_available_tools_for_profile(profile)

        # Prepare tool descriptions for LLM
        tool_prompts = "\n\n".join([f"- {t.name}: {t.description}" for t in tools])
        system_message = f"You are an helpful AI assistant. You have access to these tools:\n{tool_prompts}"

        current_messages = messages.copy()
        iterations = 0
        max_iterations = AGENTIC_MAX_ITERATIONS

        while iterations < max_iterations:
            iterations += 1

            # Emit iteration start event
            yield WorkflowEvent(
                type="iterationStarted",
                data={"iteration": iterations},
            )

            # Call LLM with tools
            yield WorkflowEvent(type="working", data={})

            # Get LLM response (with tool calls enabled)
            response = await self._call_llm_with_tools(
                messages=current_messages,
                system=system_message,
                tools=tools,
            )

            # Process response
            if response.tool_calls:
                # Handle tool calls
                for tool_call in response.tool_calls:
                    yield WorkflowEvent(
                        type="toolCall",
                        data={
                            "tool_name": tool_call.name,
                            "args": tool_call.arguments,
                        },
                    )

                    # Execute tool
                    tool = next(t for t in tools if t.name == tool_call.name)
                    tool_result = await tool.execute(**tool_call.arguments)

                    yield WorkflowEvent(
                        type="toolResult",
                        data={
                            "tool_name": tool_call.name,
                            "result": tool_result,
                        },
                    )

                    # Append to messages for next iteration
                    current_messages.append({
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": [tool_call],
                    })
                    current_messages.append({
                        "role": "user",
                        "content": json.dumps(tool_result),
                        "tool_call_id": tool_call.id,
                    })

                yield WorkflowEvent(type="iterationCompleted", data={})
                continue

            else:
                # No more tool calls - final response
                yield WorkflowEvent(
                    type="text",
                    data={"content": response.content},
                )
                break

        # Signal completion
        if completion_token:
            await manager.signal_completion(token=completion_token)

        yield WorkflowEvent(type="complete", data={})
```

## Integration with Chat

### WebSocket Flow

```python
@router.websocket("/chat/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket chat endpoint with agentic support."""
    await websocket.accept()

    # ... authentication ...

    # Receive initial request
    initial_data = await websocket.receive_json()
    profile = initial_data.get("agent_profile", "general")
    enable_agent = initial_data.get("enable_agent", True)

    # Create completion token
    token = manager.create_completion_token()

    try:
        # Determine which workflow to use
        if enable_agent and AGENTIC_ENABLED:
            workflow = AgenticWorkflow()
            events = workflow.execute(
                messages=messages,
                profile=profile,
                completion_token=token,
            )
        else:
            # Standard non-agentic workflow
            workflow = StandardWorkflow()
            events = workflow.execute(messages, completion_token=token)

        # Stream events to client
        async for event in events:
            await websocket.send_json(event.to_dict())

    finally:
        # Signal completion if not already
        if not manager.is_completed(token):
            await manager.signal_completion(token=token)
```

## Configuration Best Practices

### Profile Selection
```python
# In service - choose profile based on request
profile = "general"  # Default

if has_image_requests(messages):
    profile = "media"

if has_automation_requests(messages):
    profile = "automation"

await workflow.execute(messages, profile=profile)
```

### Tool Execution Safety
```python
# Validate tool calls before execution
for tool_call in response.tool_calls:
    tool = next((t for t in tools if t.name == tool_call.name), None)
    if not tool:
        # Unknown tool - don't execute
        yield WorkflowEvent(type="error", data={"message": f"Unknown tool: {tool_call.name}"})
        continue

    # Validate arguments
    try:
        await tool.validate_arguments(**tool_call.arguments)
    except ValidationError as exc:
        yield WorkflowEvent(type="toolError", data={"error": str(exc)})
        continue
```

## Limitations & Considerations

1. **Token budget** - Each iteration uses tokens. Monitor usage.
2. **Timeout** - Default 5 minutes. Configure in settings.
3. **Tool failures** - If a tool fails, workflow continues with error info.
4. **Infinite loops** - Max iterations prevents infinite loops.
5. **Cost** - Multiple calls mean higher API costs.

## Testing Agentic Workflows

```python
@pytest.mark.asyncio
async def test_agentic_workflow_single_iteration():
    """Test workflow with single tool call."""
    messages = [{"role": "user", "content": "Generate an image of a cat"}]

    workflow = AgenticWorkflow()
    events = []

    async for event in workflow.execute(messages, profile="media"):
        events.append(event)

    # Verify iteration flow
    assert any(e.type == "iterationStarted" for e in events)
    assert any(e.type == "toolCall" for e in events)
    assert any(e.type == "toolResult" for e in events)
    assert any(e.type == "complete" for e in events)


@pytest.mark.asyncio
async def test_agentic_workflow_multiple_iterations():
    """Test workflow with multiple tool calls."""
    # Mock tools to return results
    # Verify it iterates correctly
    ...
```

## See Also
- `@storage-backend/DocumentationApp/agentic-workflow-handbook.md` - Full handbook
- `@storage-backend/config/agentic/` - Configuration files
- `@storage-backend/core/tools/` - Tool implementations
- `@storage-backend/features/chat/services/streaming/agentic.py` - Execution logic
