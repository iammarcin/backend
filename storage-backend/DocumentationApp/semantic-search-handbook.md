# Semantic Search Developer Handbook

## Overview

Semantic search enhances the BetterAI backend with intelligent context retrieval using **dual-index architecture** supporting both message-level and session-level search. When enabled, user prompts are automatically enriched with relevant content from previous conversations, creating a powerful "memory" system for AI interactions.

**Key capabilities:**
- **Dual-index architecture**: Message-level (individual messages) + Session-level (conversation summaries)
- Real-time indexing of all chat messages and session summaries (user and AI responses)
- **Hybrid search** combining dense vectors (OpenAI embeddings) + sparse vectors (BM25)
- **Reciprocal Rank Fusion (RRF)** for optimal result ranking
- Advanced filtering (tags, dates, message types, sessions)
- Automatic context enhancement with token budget management
- Non-blocking, resilient architecture with circuit breakers
- Zero-cost storage (Qdrant free 1GB tier)
- Minimal embedding costs (~$0.02/10K messages)

**Typical workflow:**
1. User sends message via WebSocket
2. If `userSettings.semantic.enabled` is true, the system performs search based on the selected mode (message-level, session-level, or multi-tier)
3. Dense (semantic) and sparse (keyword) vectors are searched in parallel
4. Results are fused using RRF and relevant context is prepended to the prompt
5. LLM receives enriched prompt with historical context
6. Message is indexed asynchronously with both vector types for future searches
7. Session summaries are generated and indexed periodically for session-level search

## Search Modes

The semantic search system supports multiple strategies tailored to different query types and use cases. Modes operate on either message-level (individual messages) or session-level (conversation summaries) indexes.

### Message-Level Modes

#### Hybrid Mode (Default)

- **Collection:** `chat_messages_prod_hybrid`
- **How it works:** combines dense vectors (OpenAI) with sparse vectors (BM25), merging them via Reciprocal Rank Fusion (RRF).
- **Best for:** general-purpose search where queries mix vague concepts and exact keywords.
- **Scores:** rank-based (0.5 best → 0.1 poor). Always returns ranked results.
- **Supported options:** `limit`, `tags`, `date_range.start`, `date_range.end`, `message_type` (user-only toggle), and `session_ids` (internal drill-down). `threshold` is ignored because ranking is fusion-based.

```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "hybrid"
  }
}
```

#### Semantic Mode

- **Collection:** `chat_messages_prod`
- **How it works:** dense vectors only; pure cosine similarity with strict thresholding.
- **Best for:** conceptual questions and scenarios where "no results" is preferred over noise.
- **Scores:** cosine similarity (0.0–1.0). Typical range 0.9+ (excellent) → 0.5 (fair).
- **Supported options:** `limit`, `threshold`, `tags`, `date_range.start`, `date_range.end`, `message_type`, and `session_ids`.

```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "semantic",
    "threshold": 0.7
  }
}
```

#### Keyword Mode

- **Collection:** `chat_messages_prod_hybrid`
- **How it works:** sparse vectors only (BM25). No embedding generation required.
- **Best for:** exact term matching, code lookups, IDs, and performance-critical queries.
- **Scores:** BM25 relevance (higher is better; unbounded scale).
- **Supported options:** `limit`, `tags`, `date_range.start`, `date_range.end`, `message_type`, and `session_ids`. `threshold` is ignored for this mode.

```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "keyword"
  }
}
```

### Session-Level Modes

#### Session Hybrid Mode

- **Collection:** `chat_sessions_summary_prod`
- **How it works:** combines dense vectors (OpenAI) with sparse vectors (BM25) over session summaries, merged via Reciprocal Rank Fusion (RRF).
- **Best for:** finding conversations by topic or theme (e.g., "business ideas discussions").
- **Scores:** rank-based (0.5 best → 0.1 poor). Always returns ranked results.
- **Supported options:** `limit` only. Message-level filters (`threshold`, `tags`, `date_range`, `message_type`, `session_ids`) are ignored for session searches.

```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "session_hybrid"
  }
}
```

#### Session Semantic Mode

- **Collection:** `chat_sessions_summary_prod`
- **How it works:** dense vectors only over session summaries; pure cosine similarity.
- **Best for:** conceptual topic search where precision matters more than recall.
- **Scores:** cosine similarity (0.0–1.0). Typical range 0.9+ (excellent) → 0.5 (fair).
- **Supported options:** `limit` only. Session search does not look at message filters (`threshold`, `tags`, `date_range`, `message_type`, `session_ids`).

```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "session_semantic",
    "threshold": 0.7
  }
}
```

### Multi-Tier Mode

- **Strategy:** Session search → Message drill-down
- **How it works:** First searches session summaries to find relevant conversations, then drills into top sessions to retrieve specific messages.
- **Best for:** comprehensive topic discovery with detailed message-level results.
- **Configuration:** `top_sessions` (default: 3), `messages_per_session` (default: 5)
- **Supported options:** `top_sessions` and `messages_per_session`. Other semantic settings (`limit`, `threshold`, filters) are ignored because the pipeline owns both tiers internally.

```json
{
  "semantic": {
    "enabled": true,
    "search_mode": "multi_tier",
    "top_sessions": 3,
    "messages_per_session": 5
  }
}
```

### Mode Comparison

| Feature | Message Semantic | Message Hybrid | Message Keyword | Session Semantic | Session Hybrid | Multi-Tier |
|---------|------------------|----------------|-----------------|------------------|----------------|------------|
| **Speed** | ~200 ms | ~250 ms | ~50 ms | ~150 ms | ~180 ms | ~300 ms |
| **OpenAI Cost** | ✅ | ✅ | ❌ | ✅ | ✅ | ✅✅ |
| **Exact match strength** | ❌ | ✅ | ✅✅ | ❌ | ✅ | ✅ |
| **Semantic understanding** | ✅✅ | ✅ | ❌ | ✅✅ | ✅ | ✅✅ |
| **Empty results possible?** | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Best for** | Concepts, vague prompts | General message search | IDs, code, keywords | Topic concepts | Topic discovery | Comprehensive topics |

### Mode → Option Matrix

| Mode | `limit` | `threshold` | `tags` | `date_range` | `message_type` | `session_ids` | `top_sessions` | `messages_per_session` |
|------|---------|-------------|--------|--------------|----------------|----------------|----------------|------------------------|
| **hybrid** | ✅ | ❌ (ignored) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **semantic** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **keyword** | ✅ | ❌ (BM25) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **session_hybrid** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **session_semantic** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **multi_tier** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |

Legend: ✅ = supported, ❌ = ignored/N/A. Session modes only honor the request `limit`; their pipelines ignore message-level filters. Multi-tier mode owns both tiers internally, so only `top_sessions` and `messages_per_session` apply.

## Architecture

### Dual-Index Architecture

The system maintains two parallel vector indexes for comprehensive search capabilities:

| Tier | Collection | Granularity | Use Cases | Storage |
|------|------------|-------------|-----------|---------|
| **Message-Level** | `chat_messages_prod_hybrid` | Individual messages | Fact retrieval, quotes, documentation | Qdrant |
| **Session-Level** | `chat_sessions_summary_prod` | Conversation summaries | Topic discovery, conversation retrieval | MySQL + Qdrant |

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    Dual-Index Architecture                        │
└─────────────────────────────────────────────────────────────────┘

Tier 1: Message-Level (EXISTING)
├── Collection: chat_messages_prod_hybrid
├── Granularity: Individual messages
├── Search modes: semantic, hybrid, keyword
└── Use cases: Fact retrieval, documentation, exact quotes

Tier 2: Session-Level (NEW)
├── Collection: chat_sessions_summary_prod
├── Granularity: Entire conversation summaries
├── Search modes: session_semantic, session_hybrid
└── Use cases: Topic discovery, conversation retrieval

Tier 3: Multi-Tier (NEW)
├── Strategy: Session search → Message drill-down
├── Search mode: multi_tier
└── Use case: Hierarchical conversation discovery
```

### Search Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     WebSocket Request                        │
│  { prompt, userSettings: { semantic: { enabled: true } } }   │
└────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│           features/chat/utils/websocket_dispatcher.py        │
│                                                               │
│  1. Parse userSettings.semantic.enabled                      │
│  2. Parse search_mode (hybrid/session_hybrid/etc)            │
│  3. Call enhance_prompt_with_semantic_context()              │
│  4. Send semanticContextAdded event (if context found)       │
└────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│      features/semantic_search/prompt_enhancement.py          │
│                                                               │
│  1. Extract semantic settings & filters                      │
│  2. Route to appropriate search service based on mode        │
│  3. Format results with ContextFormatter                     │
│  4. Return enhanced prompt + metadata                        │
└────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│      features/semantic_search/service/ (mixins)              │
│                                                               │
│  Message-Level:                                               │
│  ├── SemanticSearchQueryMixin (dense/sparse/hybrid)          │
│  Session-Level:                                               │
│  ├── SessionSearchQueryMixin (session_semantic/hybrid)       │
│  Multi-Tier:                                                  │
│  └── MultiTierSearchMixin (session → message drill-down)     │
└────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│         core/providers/semantic/                             │
│                                                               │
│  Message Providers:                                          │
│  ├── qdrant.py (hybrid search over messages)                 │
│  Session Providers:                                          │
│  ├── session_search_provider.py (search over summaries)      │
│                                                               │
│  HYBRID SEARCH with RRF Fusion:                              │
│  1. Generate dense embedding (OpenAI)                        │
│  2. Generate sparse embedding (BM25)                         │
│  3. Build Qdrant filter from metadata                        │
│  4. Execute query_points with prefetch:                      │
│     - Sparse vector search (BM25 keywords)                   │
│     - Dense vector search (semantic similarity)              │
│  5. Apply RRF fusion to combine results                      │
│  6. Return ranked results                                    │
└────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Qdrant Cloud                              │
│    Message Collection:                                       │
│    ├── Named vectors: "dense" + "sparse"                     │
│    └── Payload: message metadata                             │
│                                                             │
│    Session Collection:                                       │
│    ├── Named vectors: "dense" + "sparse"                     │
│    └── Payload: summary metadata                             │
└─────────────────────────────────────────────────────────────┘


                     ┌──── Indexing Flows ────┐

┌─────────────────────────────────────────────────────────────┐
│      features/chat/services/history/semantic_indexing.py     │
│                                                               │
│  queue_semantic_indexing_tasks() after message persist       │
└────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│      core/providers/semantic/qdrant_indexing.py              │
│                                                               │
│  1. Check if indexing enabled (SEMANTIC_INDEXING_ENABLED)    │
│  2. Generate dense vector (OpenAI embedding)                 │
│  3. Generate sparse vector (BM25 tokenization)               │
│  4. Build metadata (customer_id, session_id, tags, etc.)     │
│  5. Upsert to Qdrant message collection                      │
└────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│      features/semantic_search/services/session_summary_service.py │
│                                                               │
│  1. Gather all messages in session                           │
│  2. Call configured model (config/semantic/session_summary.yaml) │
│  3. Generate structured summary with topics/entities         │
│  4. Store in MySQL session_summaries table                   │
└────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│      features/semantic_search/services/session_indexing_service.py │
│                                                               │
│  1. Generate dense vector from summary text                  │
│  2. Generate sparse vector from summary + topics + entities  │
│  3. Build metadata (session_id, customer_id, etc.)           │
│  4. Upsert to Qdrant session collection                      │
└────────────────────────┬────────────────────────────────────┘
```

### Hybrid Search Explained

The system uses **hybrid search** combining two complementary approaches:

| Approach | Vector Type | Provider | Strengths |
|----------|-------------|----------|-----------|
| **Semantic** | Dense (384 dims) | OpenAI `text-embedding-3-small` | Understands meaning, handles synonyms, vague queries |
| **Keyword** | Sparse (BM25) | `BM25SparseVectorProvider` | Exact matches, technical terms, proper nouns |

**Reciprocal Rank Fusion (RRF)** combines results from both searches:
- Each search returns ranked results
- RRF formula: `score(d) = Σ 1/(k + rank)` where k=2 (Qdrant default)
- Documents appearing highly in both lists get boosted
- Final ranking balances semantic similarity and keyword matching

**Why hybrid search?**
- Dense vectors alone may miss exact keyword matches
- Sparse vectors alone miss semantic relationships
- RRF fusion gets the best of both worlds without requiring score normalization

### Component Structure

```
core/
├── providers/semantic/          # Provider layer (infrastructure)
│   ├── __init__.py              # Registration
│   ├── base.py                  # BaseSemanticProvider (abstract)
│   ├── schemas.py               # SearchRequest, SearchResult dataclasses
│   ├── embeddings.py            # EmbeddingProvider, OpenAIEmbeddingProvider
│   ├── bm25.py                  # BM25SparseVectorProvider (sparse vectors)
│   ├── qdrant.py                # QdrantSemanticProvider (hybrid search)
│   ├── qdrant_filters.py        # Filter builders for Qdrant queries
│   ├── qdrant_indexing.py       # Message indexing with dual vectors
│   ├── qdrant_health.py         # Health check logic
│   ├── circuit_breaker.py       # Resilience pattern
│   └── factory.py               # get_semantic_provider()
│
├── clients/
│   └── semantic.py              # Qdrant client singleton
│
├── config/
│   └── semantic_search/         # Semantic search configuration
│       ├── __init__.py
│       ├── defaults.py          # Search defaults and thresholds
│       ├── embeddings.py        # Embedding model configuration
│       ├── qdrant.py            # Qdrant connection settings
│       ├── schemas.py           # Configuration dataclasses
│       ├── session_summary.yaml # Session summary settings
│       ├── session_summary_prompt.txt # Summarization prompt
│       └── utils/
│           ├── __init__.py
│           └── collection_resolver.py # Collection resolution helpers

features/
├── semantic_search/             # Feature layer (business logic)
│   ├── __init__.py
│   ├── routes.py                # FastAPI router (/api/v1/semantic/health)
│   ├── dependencies.py          # FastAPI dependency injection
│   ├── rate_limiter.py          # Sliding window rate limiter
│   ├── prompt_enhancement.py    # enhance_prompt_with_semantic_context()
│   ├── prompt_enhancement_*.py  # Supporting modules for prompt enhancement
│   │
│   ├── service/                 # Service layer (mixin pattern)
│   │   ├── __init__.py          # SemanticSearchService (facade)
│   │   ├── base.py              # Base service with provider wiring
│   │   ├── search.py            # SemanticSearchQueryMixin
│   │   ├── indexing.py          # SemanticSearchIndexingMixin
│   │   └── bulk.py              # SemanticSearchBulkMixin
│   │
│   ├── schemas/
│   │   └── __init__.py          # Request/response models
│   │
│   └── utils/
│       ├── context_formatter.py # Format results for LLM context
│       ├── metadata_builder.py  # Build Qdrant metadata
│       ├── settings_parser.py   # Parse userSettings.semantic
│       ├── parsers.py           # Helper parsing functions
│       └── token_counter.py     # Token counting (tiktoken)
│
└── chat/
    ├── utils/
    │   └── websocket_dispatcher.py  # Integration point (context enhancement)
    │
    └── services/history/
        └── semantic_indexing.py     # Integration point (auto-indexing)
```

## Content Deduplication

Quality suffers when identical content is indexed multiple times, so duplicates are handled proactively.

### Pre-Insertion Guard

- Each message content is hashed with SHA-256 before indexing.
- `content_hash_exists()` verifies if the hash already exists for the customer.
- Duplicates are skipped and logged, preventing index bloat.
- Implemented in `core/providers/semantic/qdrant_indexing.py`.

### Cleanup Script

Use the maintenance script to remove historical duplicates:

```bash
# Preview deletions
python scripts/qdrant_deduplicate.py --dry-run

# Execute deletion
python scripts/qdrant_deduplicate.py --no-dry-run

# Scope to a single customer
python scripts/qdrant_deduplicate.py --customer-id 42 --no-dry-run
```

The script groups points by content hash, keeps the earliest occurrence, removes the rest, and outputs summary statistics.

## Dual Indexing Strategy

The system maintains two parallel indexing strategies:

### Message-Level Indexing

To support every message-level search mode seamlessly, each message is indexed into both collections:

1. **`chat_messages_prod`** – semantic-only (dense vectors, strict thresholds)
2. **`chat_messages_prod_hybrid`** – hybrid (dense + sparse vectors via RRF)

`MultiCollectionSemanticProvider` wraps the base Qdrant provider and ensures:

- Dense embeddings are generated once and reused for both collections.
- Hybrid and semantic upserts run in parallel via `asyncio.gather`.
- Deletes and updates propagate to both collections.
- Bulk indexing deduplicates first, then syncs both targets.

Need to populate the semantic collection from the hybrid one? Run:

```bash
python scripts/backfill_semantic_collection.py
```

This scrolls the hybrid collection, extracts dense vectors, and upserts them into the semantic collection.

### Session-Level Indexing

Session summaries are indexed separately for topic-based search:

1. **`chat_sessions_summary_prod`** – session summaries (dense + sparse vectors)
2. **MySQL `session_summaries`** – source of truth for summaries with metadata

Session indexing involves:

- Generating dense embeddings from summary text
- Creating sparse vectors from summary + key topics + main entities
- Storing in Qdrant with session metadata
- Automatic regeneration when sessions are updated

Need to backfill session summaries? Run:

```bash
# Standard mode (immediate results)
python scripts/backfill_session_summaries.py --all

# Batch API mode (50% cost savings, recommended for production)
python scripts/backfill_session_summaries_batch.py --all
```

The Batch API variant provides **50% cost savings** on all token usage and is recommended for production bulk processing. See `DocumentationApp/session-summary-batch-guide.md` for complete details.

## Configuration

All semantic search configuration is in `config/semantic_search/` and controlled via environment variables.

### Master Switches

**Control semantic search globally:**

```bash
# Enable/disable semantic search (default: true)
SEMANTIC_SEARCH_ENABLED=true

# Enable/disable automatic indexing (default: true)
SEMANTIC_INDEXING_ENABLED=true
```

**Important:**
- Set `SEMANTIC_SEARCH_ENABLED=false` to disable search without removing Qdrant credentials
- Set `SEMANTIC_INDEXING_ENABLED=false` to prevent indexing (e.g., non-prod environments)
- Both flags work independently - you can disable search but keep indexing, or vice versa

### Qdrant Configuration

**Required for semantic search to work:**

```bash
# Qdrant Cloud connection (required)
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your-api-key-here

# Collection name (default: chat_messages)
QDRANT_COLLECTION_NAME=chat_messages
```

**Obtaining credentials:**
1. Sign up at https://cloud.qdrant.io (free 1GB tier)
2. Create a cluster
3. Create an API key (Dashboard → API Keys)
4. Copy cluster URL and API key to `.env`

### Embedding Configuration

**OpenAI embedding settings:**

```bash
# Model (environment-specific)
# Production: text-embedding-3-large
# Non-production: text-embedding-3-small
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-large

# Dimensions (must match model)
# text-embedding-3-small: 384 (default)
# text-embedding-3-large: 1536 (default) or 3072 for max quality
SEMANTIC_EMBEDDING_DIMENSIONS=1536

# Timeout for embedding generation (seconds, default: 5.0)
SEMANTIC_EMBEDDING_TIMEOUT=5.0
```

**Cost optimization:**
- Production (`text-embedding-3-large` @ 1536 dims): $0.13 per 1M tokens (~7,700 messages)
- Non-production (`text-embedding-3-small` @ 384 dims): $0.02 per 1M tokens (~10,000 messages)
- Batch API pricing (both): 50% discount on standard pricing

### Search Defaults

**Default search parameters:**

```bash
# Default number of results (default: 10)
SEMANTIC_SEARCH_DEFAULT_LIMIT=10

# Default similarity threshold 0.0-1.0 (default: 0.1)
SEMANTIC_SEARCH_DEFAULT_THRESHOLD=0.1

# Max tokens for context (default: 4000)
SEMANTIC_SEARCH_CONTEXT_MAX_TOKENS=4000
```

**Threshold tuning:**
Note: RRF (Reciprocal Rank Fusion) scores are rank-based, not similarity scores.
      Lower threshold → more results | Higher threshold → fewer results

### Timeouts & Rate Limits

**Performance and resilience:**

```bash
# Qdrant search timeout (seconds, default: 10.0)
SEMANTIC_SEARCH_TIMEOUT=10.0

# Total operation timeout (seconds, default: 15.0)
SEMANTIC_TOTAL_TIMEOUT=15.0

# Rate limiting (requests per window, default: 60)
SEMANTIC_RATE_LIMIT_REQUESTS=60

# Rate limit window (seconds, default: 60.0)
SEMANTIC_RATE_LIMIT_WINDOW=60.0
```

### Complete .env Example

```bash
# Semantic Search Configuration
SEMANTIC_SEARCH_ENABLED=true
SEMANTIC_INDEXING_ENABLED=true
QDRANT_URL=https://abc123-example.cloud.qdrant.io
QDRANT_API_KEY=your-api-key-here
QDRANT_COLLECTION_NAME=chat_messages

# Embedding settings (optional - uses defaults if not set)
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small
SEMANTIC_EMBEDDING_DIMENSIONS=384

# Search defaults (optional)
SEMANTIC_SEARCH_DEFAULT_LIMIT=10
SEMANTIC_SEARCH_DEFAULT_THRESHOLD=0.1
SEMANTIC_SEARCH_CONTEXT_MAX_TOKENS=4000
```

## User Settings & Filters

Semantic search behavior is controlled **per-request** via `userSettings.semantic` in the WebSocket payload. This allows dynamic configuration from the frontend without backend changes.

### Settings Structure

```javascript
{
  "semantic": {
    "enabled": true,                // Master switch per request
    "search_mode": "hybrid",        // Mode: semantic | hybrid | keyword | session_semantic | session_hybrid | multi_tier
    "limit": 10,                    // Max results per search (1-100)
    "threshold": 0.1,               // Score threshold (semantic/session modes only)

    // Optional filters
    "tags": ["work", "project"],    // Session tags (array of strings, OR logic)
    "date_range": {                 // Created_at window (inclusive)
      "start": "2024-01-01",
      "end": "2024-12-31"
    },
    "message_type": "user",         // "user" | "assistant" | "both"
    "session_ids": [123, "abc"],    // Session IDs to narrow results

    // Multi-tier only
    "top_sessions": 3,
    "messages_per_session": 5
  }
}
```

> **Important note on thresholds:** Hybrid and multi-tier searches use Reciprocal Rank Fusion (RRF). These scores are rank-based (0.5, 0.33, 0.25…), so `threshold` is ignored for those modes. Use `limit` to control returned items.

### Filter Options

#### 1. Message Type Filter

Filter by who sent the message:

```javascript
{
  "semantic": {
    "enabled": true,
    "message_type": "user" // or "assistant", "both"
  }
}
```

#### 2. Tags Filter

Filter by session tags that you apply when creating sessions:

```javascript
{
  "semantic": {
    "enabled": true,
    "tags": ["work", "business"]
  }
}
```

Tags must be arrays in the new structure; whitespace is trimmed automatically, and empty strings are ignored.

#### 3. Date Range Filter

Filter by message timestamp:

```javascript
{
  "semantic": {
    "enabled": true,
    "date_range": {
      "start": "2024-11-01",
      "end": "2024-11-30"
    }
  }
}
```

Both `start` and `end` are required; omit the entire object to disable the filter.

#### 4. Session IDs Filter

Target specific conversation threads:

```javascript
{
  "semantic": {
    "enabled": true,
    "session_ids": ["session-abc", "session-def"]
  }
}
```

#### Filter Combinations

Combine filters for precise queries:

```javascript
// User messages about work from last quarter
{
  "semantic": {
    "enabled": true,
    "limit": 20,
    "tags": ["work", "project"],
    "message_type": "user",
    "date_range": {
      "start": "2024-09-01",
      "end": "2024-11-30"
    }
  }
}
```

**📖 For a full field reference and usage notes, see `DocumentationApp/semantic-search-settings-guide.md`.**

## How It Works

### 1. Message Indexing (Automatic)

**Triggered when:**
- New message created (`features/chat/services/history/messages.py::create_message()`)
- Message edited (`features/chat/services/history/messages.py::edit_message()`)

**Process:**

```python
# In features/chat/services/history/messages.py

async def create_message(...) -> Message:
    # 1. Save message to database
    message = await repository.create_message(...)

    # 2. Index asynchronously (non-blocking)
    await index_message_async(
        message_id=message.id,
        content=message.content,
        customer_id=message.customer_id,
        session_id=message.session_id,
        message_type=message.message_type,
        tags=session.tags,  # From session
    )

    return message
```

**Non-blocking guarantee:**
- `index_message_async()` uses `asyncio.create_task()` - returns immediately
- Indexing happens in background without blocking WebSocket response
- Failures are logged but don't affect message creation

**What gets indexed:**
- Message ID (unique identifier)
- Message content (text only - attachments ignored)
- Customer ID (for multi-tenancy)
- Session ID (for session-specific search)
- Message type (`user` or `assistant`)
- Tags (from session.tags)
- Timestamp (created_at)

### 2. Context Enhancement (On-Demand)

**Triggered when:**
- User sends WebSocket request with `userSettings.semantic.enabled: true`

**Process:**

```python
# In features/chat/utils/websocket_dispatcher.py

async def dispatch_workflow(...):
    # 1. Check if enabled
    if user_settings.get("semantic", {}).get("enabled"):

        # 2. Enhance prompt with context
        enhancement_result = await enhance_prompt_with_semantic_context(
            prompt=prompt,
            customer_id=customer_id,
            user_settings=user_settings,
            manager=manager,
        )

        # 3. Send event if context added
        if enhancement_result.context_added:
            await manager.send_event({
                "type": "custom_event",
                "content": {
                    "type": "semanticContextAdded",
                    "resultCount": enhancement_result.result_count,
                    "tokensUsed": enhancement_result.tokens_used,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    # ... metadata
                }
            })

        # 4. Use enhanced prompt for LLM
        prompt = enhancement_result.enhanced_prompt
```

**Context format example:**

```
<semantic_context>
You are continuing a conversation. Here is relevant context from previous discussions:

## Session: "Project Planning" (2024-11-10)
**You asked:** "What should be our Q4 priorities?"
**AI suggested:** "Focus on product stability and user onboarding improvements..."

## Session: "Architecture Review" (2024-11-08)
**You said:** "We need to refactor the authentication system"
**AI responded:** "Consider implementing OAuth 2.0 with refresh tokens..."

</semantic_context>

[Original user prompt follows...]
```

**Token budget management:**
- `ContextFormatter` uses `tiktoken` to count tokens
- Results are added until `SEMANTIC_SEARCH_CONTEXT_MAX_TOKENS` limit reached
- Most relevant results prioritized (highest similarity scores first)
- Graceful truncation if too many results

### 3. WebSocket Events

**Event sent when context is added:**

```javascript
{
  "type": "custom_event",
  "content": {
    "type": "semanticContextAdded",
    "resultCount": 5,              // Number of messages found
    "tokensUsed": 150,             // Tokens used for context
    "timestamp": "2024-11-15T12:34:56.789Z",

    // Only present if filters were used
    "filtersApplied": {
      "messageType": "user",
      "tags": ["work"],
      "dateRange": {
        "start": "2024-01-01",
        "end": "2024-12-31"
      }
    }
  }
}
```

**Frontend can use this to:**
- Display "Using context from X previous messages"
- Show which filters were applied
- Track semantic search usage

## Key Implementation Files

### Provider Layer (Core Infrastructure)

**`core/providers/semantic/qdrant.py`**
- Main provider implementation with **hybrid search**
- Uses `query_points` API with prefetch for RRF fusion
- Key methods: `search()`, `index()`, `bulk_index()`, `health_check()`
- Implements circuit breaker pattern for resilience

**`core/providers/semantic/bm25.py`**
- `BM25SparseVectorProvider` - generates sparse vectors for keyword matching
- Hash-based token IDs for consistency between indexing and search
- Configurable k1 (term frequency saturation) and b (length normalization)

**`core/providers/semantic/embeddings.py`**
- `OpenAIEmbeddingProvider` - generates dense vectors
- LRU cache (1000 entries) for performance
- Handles OpenAI API calls with timeout/retry

**`core/providers/semantic/qdrant_indexing.py`**
- `index_message()` - indexes with both dense and sparse vectors
- `bulk_index()` - batch indexing for backfill operations
- `create_collection()` - creates collection with named vector configs

**`core/providers/semantic/qdrant_filters.py`**
- `build_filter()` - constructs Qdrant filters from SearchRequest
- Handles customer_id, tags, session_ids, date_range, message_type

**`core/providers/semantic/circuit_breaker.py`**
- Resilience pattern implementation
- Opens after 5 consecutive failures, 60-second recovery timeout

**`core/providers/semantic/factory.py`**
- `get_semantic_provider()` - main entry point with singleton caching
- Wires embedding provider, sparse provider, and Qdrant client

**`core/clients/semantic.py`**
- Qdrant client singleton with connection pooling
- Prefers gRPC (port 6334) for performance

### Feature Layer (Business Logic)

**`features/semantic_search/service/`** (mixin pattern)
- `SemanticSearchService` - facade combining all mixins
- `SemanticSearchQueryMixin` - search and format context
- `SemanticSearchIndexingMixin` - single message indexing
- `SemanticSearchBulkMixin` - batch operations

**`features/semantic_search/prompt_enhancement.py`**
- `enhance_prompt_with_semantic_context()` - main entry point
- Parses user settings, applies rate limiting
- Returns `SemanticEnhancementResult` with metadata

**`features/semantic_search/rate_limiter.py`**
- Sliding window rate limiter (per customer)
- Default: 60 requests/minute

**`features/semantic_search/utils/context_formatter.py`**
- `ContextFormatter` - formats results for LLM prompts
- Token budget management with tiktoken
- Groups results by session, truncates long messages

**`features/semantic_search/utils/settings_parser.py`**
- `parse_semantic_settings()` - parses userSettings into `SemanticSearchSettings`
- Handles tags (comma-separated), date range, session IDs

### Integration Points

**`features/chat/utils/websocket_dispatcher.py`**
- Calls `enhance_prompt_with_semantic_context()` before workflow execution
- Sends `semanticContextAdded` WebSocket event

**`features/chat/services/history/semantic_indexing.py`**
- `queue_semantic_indexing_tasks()` - queues indexing after message persistence
- Non-blocking background task orchestration

### Configuration

**`config/semantic_search/`**
- All `SEMANTIC_*`, `QDRANT_*` environment variables
- `settings` dataclass with typed configuration
- `defaults.py` - Search defaults and thresholds
- `qdrant.py` - Qdrant connection settings
- `embeddings.py` - Embedding model configuration
- `schemas.py` - Configuration dataclasses
- `session_summary.yaml` - Session summary settings
- `session_summary_prompt.txt` - Summarization prompt
- `utils/` - Collection resolution and helper functions

## Utility Scripts

Comprehensive utility scripts are available in `scripts/` for managing and exploring the semantic search index.

**Available scripts:**
- **`backfill_semantic_search.py`** - Index all existing messages (one-time setup)
- **`semantic_search_explorer.py`** - Interactive search tool (most useful for daily use)
- **`semantic_inspect_index.py`** - Inspect index contents, verify indexing
- **`semantic_manage_messages.py`** - Add/update/delete individual messages
- **`python_script_example.py`** - API usage examples for building custom tools

**Quick start:**
```bash
# 1. Backfill existing messages
python scripts/backfill_semantic_search.py

# 2. Verify indexing
python scripts/semantic_inspect_index.py --customer-id 1 --stats

# 3. Try interactive search
python scripts/semantic_search_explorer.py --customer-id 1 --interactive
```

**📖 For complete script documentation and usage examples, see `scripts/README_SEMANTIC_SEARCH.md`**

## Multi-Environment Isolation

When deploying semantic search across multiple environments (production, staging, development), proper isolation is critical to prevent data mixing and corrupted embeddings.

### The Problem

If two environments point to the **same Qdrant instance** with the **same collection name**, they will:
- ✗ Share indexed messages (data leak between environments)
- ✗ Have embedding dimension mismatches if using different embedding models
- ✗ Pollute each other's search results
- ✗ Make non-prod testing unreliable
- ✗ Risk accidental deletion of production data during non-prod cleanup

### Solution: Environment-Specific Collection Names

Use **different `QDRANT_COLLECTION_NAME` values per environment** to isolate data completely.

**Configuration example:**

```bash
# Production .env
QDRANT_URL=https://prod-cluster.cloud.qdrant.io
QDRANT_API_KEY=prod-api-key
QDRANT_COLLECTION_NAME=chat_messages_prod
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-large
SEMANTIC_EMBEDDING_DIMENSIONS=1536

# Non-production .env.sherlock
QDRANT_URL=https://prod-cluster.cloud.qdrant.io    # Same Qdrant instance (optional)
QDRANT_API_KEY=prod-api-key                          # Same credentials (optional)
QDRANT_COLLECTION_NAME=chat_messages_nonprod         # Different collection!
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small
SEMANTIC_EMBEDDING_DIMENSIONS=384

# Local development .env.local
SEMANTIC_SEARCH_ENABLED=false                   # Or use separate Qdrant instance
SEMANTIC_INDEXING_ENABLED=false
QDRANT_COLLECTION_NAME=chat_messages_local      # If enabled locally
```

### Benefits

- ✅ **Complete data separation** - Production and non-prod have independent vector spaces
- ✅ **Safe backfills** - Non-prod backfilling won't affect production data
- ✅ **Dimension safety** - Different embedding models/dimensions don't conflict
- ✅ **Independent testing** - Can fully test Qdrant operations in non-prod
- ✅ **Clear visibility** - Collection names in Qdrant UI clearly show which environment they belong to
- ✅ **Cost control** - Can independently monitor/manage costs per environment
- ✅ **Easy rollback** - Can delete entire non-prod collection without touching production

### Validation Checklist

Before enabling semantic search in multiple environments:

- [ ] **Production collection name:** `chat_messages_prod` (or similar with `_prod` suffix)
- [ ] **Non-prod collection name:** `chat_messages_nonprod` (or similar with `_nonprod` suffix)
- [ ] **Verify in Qdrant UI:** Both collections exist and don't contain cross-environment data
- [ ] **Test backfill:** Run `backfill_semantic_search.py` in non-prod, verify only non-prod collection is updated
- [ ] **Test search:** Verify searches in one environment don't return results from the other

### Disabling in Non-Production

**Alternative approach:** If you want to avoid managing multiple collections, simply disable semantic search in non-prod:

```bash
# .env.sherlock or .env.local
SEMANTIC_SEARCH_ENABLED=false
SEMANTIC_INDEXING_ENABLED=false

# Optional: Remove credentials to prevent accidental usage
# QDRANT_URL=
# QDRANT_API_KEY=
```

This prevents any data from being indexed or searched in non-prod environments.

## Disabling Semantic Search

### Production Environment (Keep Infrastructure, Disable Features)

If you want to keep Qdrant configured but disable search/indexing:

```bash
# In .env
SEMANTIC_SEARCH_ENABLED=false      # Disable search
SEMANTIC_INDEXING_ENABLED=false    # Disable indexing

# Keep Qdrant credentials (for future re-enabling)
QDRANT_URL=https://...
QDRANT_API_KEY=...
```

**Result:**
- ✅ No search queries executed
- ✅ No embeddings generated
- ✅ No data sent to OpenAI/Qdrant
- ✅ Zero cost incurred
- ✅ Can re-enable instantly by toggling flags

### Non-Production Environments (Complete Disable)

For development/staging where you don't want semantic search at all:

**Option 1: Environment variables (recommended)**
```bash
# In .env.sherlock or .env.local
SEMANTIC_SEARCH_ENABLED=false
SEMANTIC_INDEXING_ENABLED=false

# Optional: Remove credentials to prevent accidental usage
# QDRANT_URL=
# QDRANT_API_KEY=
```

**⚠️ Important:** If you enable semantic search in multiple environments pointing to the same Qdrant instance, see **Multi-Environment Isolation** section above to prevent data mixing.

**Option 2: Frontend setting**
```typescript
// In frontend userSettings
{
  "semantic": {
    "enabled": false  // User-level disable
  }
}
```

### Behavior When Disabled

**When `SEMANTIC_SEARCH_ENABLED=false`:**
- `enhance_prompt_with_semantic_context()` returns original prompt immediately
- No embedding generation
- No Qdrant queries
- No WebSocket events sent

**When `SEMANTIC_INDEXING_ENABLED=false`:**
- `index_message_async()` returns immediately without indexing
- No embeddings generated for new messages
- No data sent to Qdrant
- Messages still saved to MySQL database normally

**Both flags checked in code:**
```python
# In prompt_enhancement.py
if not settings.semantic_search_enabled:
    return SemanticEnhancementResult(...)  # No-op

# In indexing.py
if not settings.semantic_indexing_enabled:
    return  # Skip indexing
```

## Testing

### Manual Testing

**Test semantic search provider:**
```bash
python tests/manual/test_semantic_provider.py
```

**Test feature module:**
```bash
python scripts/test_m2_feature_module.py
```

**Test filtering:**
```bash
python scripts/test_m6_filtering.py
```

### Unit Tests

**Test WebSocket integration:**
```bash
pytest tests/unit/features/chat/utils/test_websocket_dispatcher_semantic.py -v
```

**Test provider layer:**
```bash
pytest tests/unit/core/providers/semantic/ -v
```

### Integration Testing

**End-to-end workflow:**
1. Enable semantic search: `SEMANTIC_SEARCH_ENABLED=true`
2. Send WebSocket request with `userSettings.semantic.enabled: true`
3. Check backend logs for:
   - "Semantic search found X results"
   - "Added semantic context (Y tokens)"
4. Verify frontend receives `semanticContextAdded` event

## Performance & Costs

### Performance Metrics

**Embedding generation:**
- OpenAI `text-embedding-3-small`: ~100-200ms per message
- BM25 sparse vector: <1ms (CPU-based tokenization)
- Batch processing: ~50-100 messages/second during backfill

**Hybrid search latency:**
- Typical query: 200-500ms (embedding generation + hybrid search)
- Breakdown: ~150ms embedding + ~100-300ms Qdrant query_points with RRF
- P95: <1 second
- Timeout: 15 seconds (configurable via `SEMANTIC_TOTAL_TIMEOUT`)

**Indexing:**
- Non-blocking: Returns immediately
- Background task: ~200-300ms per message (dense + sparse vectors)
- No impact on WebSocket response time

### Cost Estimates

**OpenAI embeddings:**
- Model: `text-embedding-3-small` @ 384 dimensions
- Cost: $0.02 per 1 million tokens
- Average: ~100 tokens per message
- **10,000 messages ≈ 1M tokens ≈ $0.02**

**Qdrant Cloud:**
- Free tier: 1GB storage
- ~384 bytes per vector + metadata
- **1GB ≈ 2.6 million messages (free)**

**Example calculation (10K messages):**
- Embedding cost: $0.02
- Storage cost: $0.00 (within free tier)
- **Total: ~$0.02 one-time + $0.00/month**

### Rate Limiting

**Default limits:**
- 60 requests per minute per customer
- Configurable via `SEMANTIC_RATE_LIMIT_REQUESTS`, `SEMANTIC_RATE_LIMIT_WINDOW`

**When rate limited:**
- Search returns empty results (graceful degradation)
- `rate_limited: true` in metadata
- Frontend can display "Search temporarily unavailable"

## Troubleshooting

### No search results returned

**Possible causes:**
1. Filters too restrictive (tags, date range, session IDs)
2. Messages not indexed (or indexed without sparse vectors for older data)
3. Semantic search disabled globally or per-request
4. Customer ID mismatch

**Solutions:**
```bash
# Check if enabled
grep SEMANTIC_SEARCH_ENABLED .env

# Check if messages are indexed
python scripts/semantic_inspect_index.py --customer-id 1 --stats

# Remove filters and try again with just limit
# In userSettings: { "semantic": { "enabled": true, "limit": 10 } }
```

> **Note:** With hybrid search using RRF fusion, the `score_threshold` setting is NOT applied. RRF produces rank-based scores (0.5, 0.33, 0.25...) that don't represent similarity. Use `limit` to control result count.

### Messages not being indexed

**Check indexing flag:**
```bash
grep SEMANTIC_INDEXING_ENABLED .env
```

**Verify Qdrant connection:**
```bash
python scripts/semantic_inspect_index.py --stats
```

**Check backend logs:**
```bash
docker logs backend | grep -i semantic
```

**Re-index specific messages:**
```bash
python scripts/semantic_manage_messages.py index --message-ids 100 200 300
```

### High latency / timeouts

**Check timeout settings:**
```bash
# In .env
SEMANTIC_SEARCH_TIMEOUT=10.0      # Qdrant search timeout
SEMANTIC_TOTAL_TIMEOUT=15.0       # Total operation timeout
SEMANTIC_EMBEDDING_TIMEOUT=5.0    # OpenAI embedding timeout
```

**Monitor backend logs:**
```bash
docker logs -f backend | grep -i "semantic\|timeout"
```

**Reduce context size:**
```bash
# In .env
SEMANTIC_SEARCH_CONTEXT_MAX_TOKENS=2000  # Default: 4000
```

### Circuit breaker tripping

**Symptoms:**
- "Circuit breaker open" in logs
- No search results for a period

**Causes:**
- Multiple consecutive failures (Qdrant/OpenAI down)
- Network issues

**Solutions:**
- Wait for auto-recovery (default: 60 seconds)
- Check Qdrant/OpenAI status
- Verify credentials in `.env`
- Check backend logs for root cause

### Cost concerns

**Monitor usage:**
```bash
# Check total messages indexed
python scripts/semantic_inspect_index.py --customer-id 1 --stats

# Estimate cost: messages_count * 100 tokens / 1M * $0.02
```

**Reduce costs:**
- Use smaller embedding dimensions (384 vs 1536)
- Disable for non-prod: `SEMANTIC_SEARCH_ENABLED=false`
- Filter by date range to search recent messages only

## Best Practices

### 1. Environment-Specific Configuration

**Production:**
```bash
SEMANTIC_SEARCH_ENABLED=true
SEMANTIC_INDEXING_ENABLED=true
QDRANT_URL=https://prod-cluster.cloud.qdrant.io
QDRANT_API_KEY=prod-api-key
```

**Non-production:**
```bash
SEMANTIC_SEARCH_ENABLED=false      # Disable to save costs
SEMANTIC_INDEXING_ENABLED=false
# QDRANT_URL=                      # Optional: remove credentials
# QDRANT_API_KEY=
```

### 2. Frontend Integration

**Always provide toggle:**
```typescript
// Let users enable/disable semantic search
const userSettings = {
  semantic: {
    enabled: userPreferences.semanticSearchEnabled
  }
}
```

**Show context usage:**
```typescript
// Listen for semanticContextAdded event
socket.on('message', (event) => {
  if (event.type === 'customEvent' &&
      event.content.type === 'semanticContextAdded') {
    showNotification(`Using context from ${event.content.resultCount} messages`)
  }
})
```

### 3. Tagging Strategy

**Be consistent with tags:**
```typescript
// Good: Consistent categorization
tags: ["work", "project-alpha", "architecture"]

// Avoid: Random, one-off tags
tags: ["misc", "stuff", "random thoughts"]
```

**Recommended categories:**
- **Topics:** work, personal, research, ideas
- **Projects:** project-alpha, project-beta
- **Types:** decision, question, action-item

### 4. Monitoring

**Key metrics to track:**
- Search hit rate (results found / searches)
- Average latency (time to return results)
- Context token usage (average tokens per search)
- Indexing backlog (messages pending indexing)

**Log analysis:**
```bash
# Search for semantic events
docker logs backend | grep "Semantic search"

# Check for failures
docker logs backend | grep -i "semantic.*error\|failed"

# Monitor context usage
docker logs backend | grep "Added semantic context"
```

### 5. Backfilling

**Initial backfill (one-time):**
```bash
# Test with small batch first
python scripts/backfill_semantic_search.py --limit 100 --dry-run

# Full backfill
python scripts/backfill_semantic_search.py

# Monitor progress
python scripts/semantic_inspect_index.py --customer-id 1 --stats
```

**Incremental re-indexing:**
```bash
# Re-index recent messages (last 1000)
python scripts/semantic_manage_messages.py index --range -1000-0

# Re-index specific customer
python scripts/backfill_semantic_search.py --customer-id 123
```

## Advanced Topics

### Hybrid Search Technical Details

The hybrid search implementation uses Qdrant's `query_points` API with prefetch and RRF fusion:

```python
# Simplified implementation (from qdrant.py)
hits = await self.client.query_points(
    collection_name=self.collection_name,
    prefetch=[
        # Sparse vector search (BM25 keywords)
        models.Prefetch(
            query=models.SparseVector(indices=..., values=...),
            using="sparse",
            limit=request.limit * 2,  # Oversample for fusion
            filter=qdrant_filter,
        ),
        # Dense vector search (semantic similarity)
        models.Prefetch(
            query=dense_embedding,
            using="dense",
            limit=request.limit * 2,  # Oversample for fusion
            filter=qdrant_filter,
        ),
    ],
    # RRF fusion combines results
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=request.limit,
    with_payload=True,
)
```

**Key design decisions:**
- **Prefetch limit = 2x requested limit**: Ensures enough candidates for effective fusion
- **Filters applied at prefetch level**: Reduces candidate set before fusion
- **No score_threshold**: RRF scores are rank-based, not similarity-based
- **Default RRF k=2**: Qdrant's default (original paper uses k=40)

**BM25 Sparse Vector Generation:**
```python
# From bm25.py - hash-based token IDs for consistency
def get_token_id(self, token: str) -> int:
    return abs(hash(token)) % HASH_SPACE  # 2^31 - 1

# BM25 score calculation (simplified, Qdrant adds IDF)
score = (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * (doc_len / avgdl)))
```

### Custom Search Workflows

**Building custom tools:**

```python
# Example: Direct search with raw results
import asyncio
from features.semantic_search.service import get_semantic_search_service

async def search_with_scores(query: str, customer_id: int):
    service = get_semantic_search_service()

    # Use search() for raw results with RRF scores
    results = await service.search(
        query=query,
        customer_id=customer_id,
        limit=20,
        tags=["work"],
    )

    for r in results:
        print(f"[{r.score:.3f}] {r.content[:100]}...")
```

See `scripts/python_script_example.py` for complete examples.

### Extending the Provider

**Adding a new vector database:**

1. Implement `BaseSemanticProvider` in `core/providers/semantic/`
2. Register in `core/providers/semantic/__init__.py`
3. Update `factory.py` to initialize your provider
4. Add configuration to `core/config.py`

**Adding alternative fusion methods:**
Qdrant 1.11+ supports DBSF (Distribution-Based Score Fusion) as an alternative to RRF:
```python
query=models.FusionQuery(fusion=models.Fusion.DBSF)
```

### Multi-Tenancy

**Built-in support:**
- All searches automatically filtered by `customer_id`
- Qdrant metadata includes `customer_id` field
- No cross-customer data leakage

**Verification:**
```bash
# Check customer isolation
python scripts/semantic_inspect_index.py --customer-id 1 --metadata-stats
python scripts/semantic_inspect_index.py --customer-id 2 --metadata-stats
```

### Collection Schema

**Qdrant collection structure:**
```
Collection: chat_messages (configurable via QDRANT_COLLECTION_NAME)

Vectors (named):
├── "dense": 384 dimensions (OpenAI text-embedding-3-small)
└── "sparse": BM25 token indices + values

Payload fields:
├── content (text)
├── customer_id (int) - indexed
├── session_id (int)
├── message_id (int)
├── message_type (keyword) - indexed: "user" | "assistant"
├── session_name (text)
├── tags (keyword array) - indexed
├── timestamp (datetime) - indexed
└── content_length (int)
```

## See Also

**Documentation:**
- **Settings Guide:** `DocumentationApp/semantic-search-settings-guide.md` - Complete user settings reference
- **Scripts Guide:** `scripts/README_SEMANTIC_SEARCH.md` - Utility scripts documentation
- **Developer Handbook:** `DocumentationApp/storage-backend-ng-developer-handbook.md` - Overall backend architecture
- **WebSocket Events:** `DocumentationApp/websocket-events-handbook.md` - Event contract documentation

---

**Questions or issues?** Check backend logs (`docker logs backend`) or try the utility scripts in `scripts/` for debugging.

## Session-Level Search

### Overview

The semantic search system now supports **session-level search** alongside existing message-level modes. Instead of indexing individual messages, session search indexes LLM-generated summaries that capture the entire conversation.

Why add session summaries?

- Message-level search is great for finding specific facts or quotes.
- Session-level search excels at finding whole conversations by topic.
- Example: “business ideas we discussed” should return entire brainstorming sessions, not just one message.

### Architecture

The system now maintains two parallel indexes:

| Tier | Collection | Granularity | Use Cases |
|------|------------|-------------|-----------|
| Message-Level | `chat_messages_prod_hybrid` | Individual messages | Fact retrieval, quotes, documentation |
| Session-Level | `chat_sessions_summary_prod` | Conversation summaries | Topic discovery, conversation retrieval |

### Workflow

1. **Summarization** – `SessionSummaryService` gathers all session messages and calls the configured model (parameter: `summarization.model` in `config/semantic/session_summary.yaml`, default: gpt-4o-mini) to create a structured summary with topics and entities.
2. **Storage** – summaries are stored in MySQL `session_summaries` with metadata (message count, timestamps, config_version).
3. **Indexing** – `SessionIndexingService` generates dense embeddings + sparse vectors and upserts points into Qdrant (`chat_sessions_summary_prod`).
4. **Search** – `SessionSearchService` executes dense/hybrid/sparse searches over summaries.
5. **Updates** – `SummaryUpdateService` compares `ChatSessionsNG.last_update` vs `session_summaries.last_updated` to detect stale data.

### Search Modes

Message-level modes (existing):

- `semantic` – Dense vector search over messages.
- `hybrid` – Dense + sparse fusion (default).
- `keyword` – Sparse BM25 search.

Session-level modes (new):

- `session_semantic` – Dense search over summaries.
- `session_hybrid` – Dense + sparse fusion over summaries (recommended).

Multi-tier mode (new):

- `multi_tier` – Search session summaries first, then drill into top sessions’ messages.

### Frontend Usage

```javascript
// Session-level search
userSettings.semantic.search_mode = "session_hybrid"

// Multi-tier search with custom config
userSettings.semantic.search_mode = "multi_tier"
userSettings.semantic.top_sessions = 3
userSettings.semantic.messages_per_session = 5
```

### Configuration Reference

`config/semantic_search/session_summary.yaml`

```yaml
summarization:
  model: "gpt-4o-mini"
  max_tokens: 800
  temperature: 0.3
  prompt_file: "config/semantic_search/session_summary_prompt.txt"
backfill:
  min_messages: 3
  batch_size: 10
versioning:
  config_version: 1
```

Increasing `config_version` forces all summaries to be regenerated (useful when changing prompts or models).

## Multi-Tier Search

### Strategy

Multi-tier search combines both tiers for high-quality topical discovery:

1. Run session search (dense or hybrid) to find relevant conversations.
2. For the top N sessions, run message-level searches scoped to each session ID.
3. Merge results into a hierarchical response: session metadata + matched messages.

### Example Output

```markdown
## Relevant Conversations

### 1. Session 123 (Relevance: 0.89)
**Summary:** Discussed 5 business ideas including SaaS platform and AI tooling.
**Topics:** saas, business-ideas, mvp-planning
**Entities:** ProjectX, TechStartup Inc

**Key Messages:**
1. **You** (score: 0.85): Idea 1: SaaS platform for small businesses...
2. **AI** (score: 0.82): That market is underserved...

---
```

### Configuration

```javascript
userSettings.semantic.search_mode = "multi_tier"
userSettings.semantic.top_sessions = 5
userSettings.semantic.messages_per_session = 5
```

`top_sessions` controls how many session summaries are returned; `messages_per_session` controls how many messages per session the tier-2 search retrieves.

### Performance

- Session search: ~80–120ms
- Message search per session: ~50–100ms
- Multi-tier (3 sessions × 5 messages) ~ 250–350ms total

You can tune `top_sessions` and `messages_per_session` to balance quality vs. latency.

## Maintenance and Monitoring

### Automatic Regeneration

`SummaryUpdateService` powers incremental refresh:

1. Detect stale summaries (session last_update > summary last_updated or config_version mismatch).
2. Regenerate summary via `SessionSummaryService`.
3. Reindex summary via `SessionIndexingService`.

Front-end endpoint:

```
POST /api/v1/admin/summaries/regenerate
```

- `session_id` query parameter → regenerate one session.
- Without `session_id` → batch regenerate all stale sessions (under cron control).
- Optional filters: `customer_id`, `limit`, `batch_size`.

### Cron Job

`scripts/cron_regenerate_summaries.sh` provides a simple shell wrapper. Recommended crontab entry:

```
0 2 * * * /path/to/scripts/cron_regenerate_summaries.sh
```

It logs responses (success/fail counts) to `/var/log/semantic_search/cron_regenerate.log` by default.

### Monitoring Endpoints

- `GET /api/v1/admin/summaries/stale` – Inspect stale session IDs.
- `GET /api/v1/admin/summaries/health` – Summary stats:
  - `total_summaries`
  - `coverage_percent` (summaries / sessions)
  - `stale_summaries` and `stale_percent`

Use these metrics for dashboards or alerting. Example thresholds:

- Coverage < 80% → run backfill.
- Stale > 10% → investigate cron job.

## Cost Analysis

### Initial Backfill (per 1000 sessions)

- Summaries: ~5M tokens → ~$0.75 (GPT-4o-mini).
- Embeddings: 1000 embeddings → ~$0.10.
- Total ≈ $0.85.

### Ongoing (100 stale sessions/day)

- Summaries: ~$0.0075/day.
- Embeddings: ~$0.01/day.
- Total ≈ $0.60/month.

Multi-tier search uses both session + message searches per query. Expect ~10–20% higher compute vs. pure message-level search, but still dominated by OpenAI embedding cost.
