# Batch API Handbook

## Overview

The Batch API enables cost-efficient, asynchronous processing of large volumes of text generation requests. Batch mode offers:

- **50% cost reduction** on all usage (input + output tokens)
- **Separate rate limits** from real-time API
- **Support for OpenAI, Anthropic, and Gemini** providers
- **24-hour turnaround** for most batches (often faster)

## When to Use Batch Mode

Batch mode is ideal for:

1. **Semantic Search Preparation**: Bulk summarization of chat sessions for vector indexing
2. **Content Generation**: Large-scale documentation, product descriptions, article summaries
3. **Data Processing**: Batch analysis, classification, or transformation of datasets
4. **Evaluation**: Processing test suites or evaluation datasets
5. **Background Jobs**: Any non-urgent text generation workload

**Do NOT use batch mode for:**
- Real-time chat responses
- Interactive applications requiring immediate feedback
- Single or few requests (no cost benefit)

## Supported Providers and Models

### OpenAI
- **Models**: gpt-4o, gpt-4o-mini, o1, o3, gpt-3.5-turbo, and all reasoning models
- **Limits**: 50,000 requests per batch, 200 MB max file size
- **Turnaround**: Target 24 hours

### Anthropic
- **Models**: claude-sonnet-4-5, claude-opus-4, claude-haiku-3-5, and all Claude models
- **Limits**: 100,000 requests per batch, 256 MB max file size
- **Turnaround**: Most batches finish in <1 hour
- **Result Retention**: 29 days

### Google Gemini
- **Models**: gemini-2.5-flash, gemini-2.5-pro, and all Gemini models
- **Limits**: 50,000 requests per batch, 2 GB max file size
- **Turnaround**: Target 24 hours

## API Reference

### Submit Batch Job

**Endpoint**: `POST /api/v1/batch/`

**Request Body**:
```json
{
  "requests": [
    {
      "custom_id": "unique-id-1",
      "prompt": "Your prompt here",
      "model": "gpt-4o",
      "temperature": 0.7,
      "max_tokens": 1000,
      "system_prompt": "You are a helpful assistant",
      "messages": []
    }
  ],
  "model": "gpt-4o",
  "description": "Optional batch description"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "job_id": "batch_20240115_120000_123",
    "provider": "openai",
    "model": "gpt-4o",
    "status": "completed",
    "request_count": 100,
    "succeeded_count": 98,
    "failed_count": 2,
    "created_at": "2024-01-15T12:00:00Z",
    "completed_at": "2024-01-15T12:30:00Z"
  }
}
```

### Get Batch Status

**Endpoint**: `GET /api/v1/batch/{job_id}`

**Response**:
```json
{
  "success": true,
  "data": {
    "job_id": "batch_20240115_120000_123",
    "status": "completed",
    "request_count": 100,
    "succeeded_count": 98,
    "failed_count": 2,
    "expired_count": 0,
    "cancelled_count": 0,
    "created_at": "2024-01-15T12:00:00Z",
    "completed_at": "2024-01-15T12:30:00Z",
    "expires_at": "2024-02-13T12:00:00Z"
  }
}
```

### Get Batch Results

**Endpoint**: `GET /api/v1/batch/{job_id}/results`

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "text": "Generated response text",
      "model": "gpt-4o",
      "provider": "openai",
      "metadata": {
        "custom_id": "unique-id-1",
        "finish_reason": "stop",
        "usage": {
          "total_tokens": 150
        }
      }
    }
  ]
}
```

### List Batch Jobs

**Endpoint**: `GET /api/v1/batch/?limit=20&offset=0&status=completed`

**Query Parameters**:
- `limit` (int): Maximum results (default: 20)
- `offset` (int): Pagination offset (default: 0)
- `status` (string): Filter by status (optional)

### Cancel Batch Job

**Endpoint**: `POST /api/v1/batch/{job_id}/cancel`

## Usage Examples

### Example 1: Summarize Chat Sessions for Semantic Search

```python
import httpx

requests = []
for session_id, session_text in chat_sessions.items():
    requests.append({
        "custom_id": f"session-{session_id}",
        "prompt": f"Summarize this chat session in 2-3 sentences: {session_text}",
        "temperature": 0.3,
        "max_tokens": 200
    })

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/v1/batch/",
        json={
            "requests": requests,
            "model": "gpt-4o-mini",
            "description": "Chat session summaries for semantic indexing"
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    job_id = response.json()["data"]["job_id"]

    results_response = await client.get(
        f"http://localhost:8000/api/v1/batch/{job_id}/results",
        headers={"Authorization": f"Bearer {token}"},
    )

summaries = results_response.json()["data"]
```

### Example 2: Bulk Documentation Generation

```python
documentation_requests = []
for endpoint in api_endpoints:
    documentation_requests.append({
        "custom_id": f"docs-{endpoint['name']}",
        "prompt": f"Generate API documentation for: {endpoint['code']}",
        "model": "claude-sonnet-4-5",
        "system_prompt": "You are a technical documentation expert.",
        "temperature": 0.2,
        "max_tokens": 1000
    })

await client.post(
    "http://localhost:8000/api/v1/batch/",
    json={
        "requests": documentation_requests,
        "model": "claude-sonnet-4-5",
        "description": "API documentation generation"
    },
    headers={"Authorization": f"Bearer {token}"},
)
```

### Example 3: Mixed Model Batch

```python
requests = [
    {
        "custom_id": "analysis-1",
        "prompt": "Analyze this code for security issues...",
        "model": "o3",
        "temperature": 1.0
    },
    {
        "custom_id": "summary-1",
        "prompt": "Summarize this article...",
        "model": "gpt-4o-mini",
        "temperature": 0.5
    }
]

await client.post(
    "http://localhost:8000/api/v1/batch/",
    json={
        "requests": requests,
        "model": "gpt-4o",
        "description": "Mixed workload batch"
    },
    headers={"Authorization": f"Bearer {token}"},
)
```

## Error Handling

### Request-Level Errors

Individual requests can fail without affecting other requests in the batch:

```json
{
  "text": "",
  "model": "gpt-4o",
  "provider": "openai",
  "metadata": {
    "custom_id": "req-123",
    "error": "Rate limit exceeded",
    "error_type": "rate_limit_error"
  }
}
```

Check `metadata.error` to identify failed requests.

### Batch-Level Errors

- **400 Bad Request**: Invalid model, batch size exceeded, unsupported provider
- **404 Not Found**: Batch job doesn't exist
- **500 Internal Server Error**: Provider API failure

## Cost Calculation

All batch requests receive a **50% discount** on standard pricing.

**Example** (OpenAI gpt-4o):
- Standard: $3.00/MTok input, $15.00/MTok output
- Batch: $1.50/MTok input, $7.50/MTok output

**For 1M input tokens + 500K output tokens**:
- Standard cost: (1M × $3) + (500K × $15) = $10,500
- Batch cost: (1M × $1.50) + (500K × $7.50) = $5,250
- **Savings: $5,250 (50%)**

## Best Practices

1. **Use Custom IDs Wisely**: Make them meaningful for result mapping
2. **Batch Size**: Aim for 100-10,000 requests per batch for optimal processing
3. **Model Selection**: Use cheaper models when appropriate
4. **Error Handling**: Always check `metadata.error` to handle partial failures
5. **Result Expiry**: Download results within 29 days (Anthropic limit)
6. **Temperature**: Use lower temperatures (0.1-0.3) for deterministic results

## Limitations

- **No Streaming**: Batch mode doesn't support streaming responses
- **No Real-Time Feedback**: Results available after batch completes
- **No Guarantees**: Some requests may expire under high load
- **Per-Provider Limits**: Each provider has different max requests and file sizes
- **Result Storage**: Results stored in `batch_jobs.metadata` (JSON)

## Architecture Notes

- **Synchronous Processing**: Current implementation polls provider APIs synchronously
- **Future Enhancement**: Async background workers with webhook notifications
- **Database Storage**: Batch results stored in `batch_jobs` table
- **Provider Fallback**: Providers without batch support fall back to sequential processing

## Troubleshooting

### "Model does not support batch API"
- Check model is OpenAI, Anthropic, or Gemini
- Verify model name via `/api/v1/admin/models/text`

### "Batch size exceeds limit"
- OpenAI: 50,000 max
- Anthropic: 100,000 max
- Gemini: 50,000 max

### "Results have expired"
- Results available for 29 days after creation
- Download results promptly after completion

### Partial Failures
- Check each result's `metadata.error` field
- Retry failed requests individually or in new batch

## Related Documentation

- **Text Providers Config Handbook**: Provider configuration details
- **Storage Backend Developer Handbook**: Overall architecture
- **API Reference**: Complete endpoint documentation
