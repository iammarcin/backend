**Tags:** `#backend` `#semantic-search` `#vector-database` `#qdrant` `#embeddings` `#openai-embeddings` `#bm25` `#hybrid-search` `#rag` `#context-enhancement`

# Semantic Search Feature

Vector-based semantic search system using Qdrant Cloud with OpenAI embeddings for intelligent context retrieval. Provides hybrid search combining dense vectors (semantic) and sparse vectors (BM25 keyword matching).

## System Context

Part of the **storage-backend** FastAPI service. Automatically indexes chat messages and enhances user prompts with relevant historical context based on semantic similarity. Integrates with chat feature for context-aware conversations.

## Architecture Overview

**Hybrid Search with RRF:**
```
User Query
    ↓
├─ Dense Vector (OpenAI embedding) ──┐
│                                     ├─ Qdrant Query with RRF Fusion
└─ Sparse Vector (BM25) ──────────────┘
                                      ↓
                          Ranked Results → Context Formatting
```

## Key Capabilities

- **Hybrid Search** - Dense + sparse vectors with Reciprocal Rank Fusion
- **Automatic Indexing** - Chat messages indexed on creation
- **Prompt Enhancement** - Prepend relevant history to user prompts
- **Advanced Filtering** - Tags, date ranges, message types, sessions
- **Token Budgeting** - Enforced context size limits
- **Caching** - LRU embedding cache (1000 entries ≈ 2MB)
- **Circuit Breaker** - Prevents cascading failures
- **Rate Limiting** - Per-customer request throttling

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/semantic/health` | GET | Health check, cache stats, rate limiter |

## Search Flow

```
1. User prompt + settings → enhance_prompt_with_semantic_context()
2. Parse settings → SemanticSearchSettings
3. Rate limit check
4. Generate embeddings (dense + sparse)
5. Qdrant hybrid search with filters
6. Format results as context
7. Prepend to user prompt
8. Emit WebSocket event (semanticContextAdded)
```

## Service Architecture

```
features/semantic_search/
├── routes.py                  # Health endpoint
├── dependencies.py            # FastAPI DI
├── rate_limiter.py            # Sliding window limiter
├── prompt_enhancement.py      # Main enhancement logic
├── prompt_enhancement_*.py    # Events, prompt handling
├── service/
│   ├── __init__.py            # SemanticSearchService
│   ├── base.py                # Provider wiring
│   ├── search.py              # Search mixin
│   ├── indexing.py            # Indexing mixin
│   └── bulk.py                # Bulk operations
└── utils/
    ├── context_formatter.py   # Result formatting
    ├── metadata_builder.py    # Indexing metadata
    ├── settings_parser.py     # Settings extraction
    ├── token_counter.py       # tiktoken counting
    └── parsers.py             # Query parsing

core/providers/semantic/
├── qdrant.py                  # QdrantSemanticProvider
├── embeddings.py              # OpenAI embeddings
├── bm25.py                    # Sparse vectors
├── circuit_breaker.py         # Resilience
└── schemas.py                 # SearchRequest/Result
```

## Configuration

**User Settings (WebSocket payload):**
```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "hybrid",
    "limit": 5,
    "threshold": 0.1,
    "tags": ["tag1", "tag2"],
    "date_range": {
      "start": "2025-01-01",
      "end": "2025-12-31"
    },
    "message_type": "user",
    "session_ids": [123, 456],
    "top_sessions": 3,
    "messages_per_session": 5
  }
}
```

> Old `general.semantic_*` fields are deprecated. Use the consolidated `semantic.*` structure going forward.

**Environment Variables:**
| Variable | Default | Purpose |
|----------|---------|---------|
| `SEMANTIC_SEARCH_ENABLED` | true | Feature flag |
| `OPENAI_API_KEY` | required | Embedding generation |
| `QDRANT_URL` | required | Vector database |
| `QDRANT_API_KEY` | optional | Qdrant auth |
| `QDRANT_COLLECTION_NAME` | "messages" | Collection name |
| `SEMANTIC_EMBEDDING_MODEL` | "text-embedding-3-small" | Model |
| `SEMANTIC_EMBEDDING_DIMENSIONS` | 384 | Vector dimensions |
| `SEMANTIC_SEARCH_DEFAULT_LIMIT` | 10 | Default results |
| `SEMANTIC_SEARCH_DEFAULT_THRESHOLD` | 0.1 | Score threshold |
| `SEMANTIC_SEARCH_CONTEXT_MAX_TOKENS` | 4000 | Context budget |

## Indexing

**Automatic Indexing (chat integration):**
- User messages indexed on creation
- AI responses indexed on persistence
- Metadata: customer_id, session_id, tags, timestamp

**Message Metadata:**
```python
{
  "message_id": 123,
  "customer_id": 1,
  "session_id": 456,
  "message_type": "user" | "assistant",
  "session_name": "Project Discussion",
  "tags": ["work", "ai"],
  "timestamp": "2025-01-20T10:30:00Z"
}
```

## Context Formatting

**Output Format:**
```
Based on your previous conversations, here are relevant discussions:

## Project Planning (2025-01-20)

**User:** What are the main features we need?
**Assistant:** Based on requirements, you need authentication...

## Daily Standup (2025-01-19)

**User:** What did you accomplish yesterday?
```

## Resilience Features

**Circuit Breaker:**
- Opens after 5 consecutive failures
- 60-second timeout before retry
- Auto-recovers on success

**Rate Limiting:**
- Sliding window (60 requests/minute default)
- Per-customer tracking

**Caching:**
- LRU embedding cache (1000 entries)
- Prevents redundant OpenAI API calls

## WebSocket Events

**semanticContextAdded:**
```json
{
  "type": "customEvent",
  "content": {
    "type": "semanticContextAdded",
    "resultCount": 5,
    "tokensUsed": 1250,
    "timestamp": "2025-01-20T10:30:00Z",
    "filtersApplied": {
      "tags": ["work"],
      "dateRange": {"start": "...", "end": "..."}
    }
  }
}
```

## Dependencies

- `qdrant-client` - Vector database client
- `openai` - Embedding generation
- `tiktoken` - Token counting
- `core/clients/semantic.py` - Qdrant client factory
