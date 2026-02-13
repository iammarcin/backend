# Semantic Search Settings Guide

## Overview

Semantic search is configured per-request via `userSettings.semantic` in the WebSocket payload. Every field lives inside that namespace, making it easy for frontend clients to toggle semantic search, choose a mode, and apply filters without backend changes.

## Quick Reference

```javascript
{
  "semantic": {
    "enabled": true,
    "search_mode": "hybrid",
    "limit": 10,
    "threshold": 0.1,
    "tags": ["work", "project"],
    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
    "message_type": "user",
    "session_ids": [123, "abc"],
    "top_sessions": 3,
    "messages_per_session": 5
  }
}
```

> **Hybrid + multi-tier note:** Reciprocal Rank Fusion (RRF) scores are rank-based, so `threshold` is ignored for `hybrid`, `session_hybrid`, and `multi_tier`. Use `limit` instead to control the number of rows returned.

## Mode Support Matrix

| `search_mode` | `limit` | `threshold` | `tags` | `date_range` | `message_type` | `session_ids` | `top_sessions` | `messages_per_session` |
|---------------|---------|-------------|--------|--------------|----------------|----------------|----------------|------------------------|
| `hybrid` | ✅ | ❌ (ignored) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| `semantic` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| `keyword` | ✅ | ❌ (BM25) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| `session_hybrid` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `session_semantic` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `multi_tier` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |

Legend: ✅ = supported, ❌ = ignored/N/A. Session modes only respect `limit`; message-level filters have no effect. Multi-tier mode ignores every field except `top_sessions` and `messages_per_session` because its pipeline orchestrates both tiers on the backend.

## Field Reference

### Core Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `false` | Master toggle per request. When `false`, semantic search is skipped entirely. |
| `search_mode` | string | `"hybrid"` | One of `semantic`, `hybrid`, `keyword`, `session_semantic`, `session_hybrid`, `multi_tier`. |
| `limit` | integer | `SEMANTIC_SEARCH_DEFAULT_LIMIT` (10) | Max number of results/messages to retrieve (1-100). |
| `threshold` | float | `SEMANTIC_SEARCH_DEFAULT_SCORE_THRESHOLD` (0.1) | Minimum similarity score used by semantic modes. Ignored for hybrid/keyword. |

### Filter Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tags` | string[] | `null` | Session tags filter. Matches sessions containing **any** of the provided tags. |
| `date_range` | object | `null` | `{start: "YYYY-MM-DD", end: "YYYY-MM-DD"}`. Both fields required; inclusive filtering. |
| `message_type` | string | `"both"` | Restrict to `"user"`, `"assistant"`, or `"both"`. |
| `session_ids` | (string \| int)[] | `null` | Search within specific conversation IDs. Useful for continuing threads. |

### Multi-Tier Settings

Used only when `search_mode="multi_tier"`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `top_sessions` | integer | 3 | Number of sessions returned in tier one. |
| `messages_per_session` | integer | 5 | Messages retrieved inside each top session. |

## Usage Examples

### 1. Basic Hybrid Search

```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "hybrid"
  }
}
```

### 2. Personal Knowledge Base (User Messages Only)

```json
{
  "semantic": {
    "enabled": true,
    "message_type": "user",
    "limit": 12
  }
}
```

### 3. Work Conversations in Q4

```json
{
  "semantic": {
    "enabled": true,
    "tags": ["work", "project"],
    "date_range": {
      "start": "2024-10-01",
      "end": "2024-12-31"
    }
  }
}
```

### 4. Resume Specific Sessions

```json
{
  "semantic": {
    "enabled": true,
    "session_ids": ["session-alpha", 987]
  }
}
```

### 5. Multi-Tier Deep Dive

```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "multi_tier",
    "top_sessions": 4,
    "messages_per_session": 6
  }
}
```

## Platform Implementation

### React / TypeScript

```typescript
const userSettings = {
  semantic: {
    enabled: true,
    search_mode: "hybrid",
    limit: 10,
    threshold: 0.1,
    tags: ["work", "project"],
    date_range: { start: "2024-01-01", end: "2024-12-31" },
    message_type: "user",
    session_ids: ["session-123"],
    top_sessions: 3,
    messages_per_session: 5,
  },
};

socket.send(JSON.stringify({
  requestType: "text",
  userInput: { prompt: [{ type: "text", text: "Summarize our OKR talks" }] },
  userSettings,
}));
```

### Kotlin (Android)

```kotlin
data class SemanticSettings(
    val enabled: Boolean = false,
    val search_mode: String? = null,
    val limit: Int? = null,
    val threshold: Double? = null,
    val tags: List<String>? = null,
    val date_range: DateRange? = null,
    val message_type: String? = null,
    val session_ids: List<String>? = null,
    val top_sessions: Int? = null,
    val messages_per_session: Int? = null,
)

data class DateRange(val start: String, val end: String)

val settings = SemanticSettings(
    enabled = true,
    search_mode = "session_hybrid",
    tags = listOf("project-alpha"),
    message_type = "assistant"
)
```

### Python Scripts

```python
from features.semantic_search.prompt_enhancement import enhance_prompt_with_semantic_context

user_settings = {
    "semantic": {
        "enabled": True,
        "search_mode": "keyword",
        "limit": 5,
        "tags": ["ideas"],
    }
}

result = await enhance_prompt_with_semantic_context(
    prompt="Remind me what the AI suggested",
    customer_id=42,
    user_settings=user_settings,
)
```

## WebSocket Events

When semantic search succeeds, the backend emits a `semanticContextAdded` custom event:

```json
{
  "type": "custom_event",
  "content": {
    "type": "semanticContextAdded",
    "resultCount": 5,
    "tokensUsed": 150,
    "timestamp": "2025-01-12T10:30:00Z",
    "filtersApplied": {
      "tags": ["work"],
      "dateRange": {"start": "2024-01-01", "end": "2024-12-31"},
      "messageType": "user"
    }
  }
}
```

## Best Practices

1. **Start with defaults** – send `{ semantic: { enabled: true } }` and adjust limit/filters gradually.
2. **Use limit, not threshold, to control noise** in hybrid and multi-tier searches.
3. **Normalize tags** in your UI so users pick from a consistent list.
4. **Validate date ranges** before sending them (both start and end must be present).
5. **Monitor context size** – more results = more tokens consumed (bounded by `SEMANTIC_SEARCH_CONTEXT_MAX_TOKENS`).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No context added | Ensure `semantic.enabled` is `true` and remove filters temporarily. |
| Too many irrelevant results | Lower `limit`, add tags/date filters, or switch to `semantic` mode. |
| Backend logs show "Semantic search disabled" | Check `.env` (`SEMANTIC_SEARCH_ENABLED=true`) and payload `semantic.enabled`. |
| Rate limited | Backend returns `rate_limited: true`; wait for the configured window (default 60 requests/min). |

## Related Docs

- `DocumentationApp/semantic-search-handbook.md`
- `DocumentationApp/websocket-events-handbook.md`
- `DocumentationApp/session-level-semantic-search-context.md`
