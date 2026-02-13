# Batch API Reference

## Endpoints

### POST /api/v1/batch/
Submit a new batch job.

- **Authentication**: Required (JWT token)
- **Request body**:
  - `requests` (array, required): List of batch request items
    - `custom_id` (string, required)
    - `prompt` (string, required unless `messages` provided)
    - `model` (string, optional)
    - `temperature` (float, optional, 0.0-2.0)
    - `max_tokens` (int, optional)
    - `system_prompt` (string, optional)
    - `messages` (array, optional) – chat history payload
  - `model` (string, required): Default model for the batch
  - `description` (string, optional): Human-readable description
- **Response**: `BatchJobResponse`
- **Errors**:
  - 400: Invalid model, unsupported provider, batch size exceeded
  - 500: Provider API failure

---

### GET /api/v1/batch/{job_id}
Retrieve batch job status.

- **Authentication**: Required
- **Path parameters**:
  - `job_id` (string)
- **Response**: `BatchJobResponse`
- **Errors**: 404 when job not found or belongs to another customer

---

### GET /api/v1/batch/{job_id}/results
Fetch results for a completed batch job.

- **Authentication**: Required
- **Path parameters**:
  - `job_id` (string)
- **Response**: Array of `ProviderResponse`
- **Errors**:
  - 404: Job not found
  - 400: Job not completed or results expired

---

### GET /api/v1/batch/
List batch jobs for the authenticated customer.

- **Authentication**: Required
- **Query parameters**:
  - `limit` (int, optional, default=20)
  - `offset` (int, optional, default=0)
  - `status` (string, optional)
- **Response**: `BatchJobListResponse`

---

### POST /api/v1/batch/{job_id}/cancel
Cancel a batch job that is still processing.

- **Authentication**: Required
- **Path parameters**: `job_id` (string)
- **Response**: `BatchJobResponse`
- **Errors**:
  - 404: Job not found
  - 400: Job already completed/failed/cancelled

## Schemas

### BatchJobResponse
```json
{
  "job_id": "string",
  "provider": "string",
  "model": "string",
  "status": "queued|processing|completed|failed|cancelled|expired",
  "request_count": 0,
  "succeeded_count": 0,
  "failed_count": 0,
  "cancelled_count": 0,
  "expired_count": 0,
  "created_at": "datetime",
  "started_at": "datetime",
  "completed_at": "datetime",
  "expires_at": "datetime",
  "results_url": "string",
  "error_message": "string",
  "metadata": {}
}
```

### BatchJobListResponse
```json
{
  "jobs": [BatchJobResponse],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

### ProviderResponse
```json
{
  "text": "string",
  "model": "string",
  "provider": "string",
  "reasoning": "string",
  "metadata": {
    "custom_id": "string",
    "finish_reason": "string",
    "usage": {
      "input_tokens": 0,
      "output_tokens": 0
    },
    "error": "string",
    "error_type": "string"
  },
  "tool_calls": [],
  "requires_tool_action": false
}
```
