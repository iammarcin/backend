# Automation Feature

**Tags:** `#backend` `#features` `#automation` `#claude-code` `#orchestration` `#ci-cd` `#workflow`

## System Context

The automation feature enables **Claude Code-native autonomous development workflows**. It provides:
- API endpoints for submitting feature requests, bug reports, and research tasks
- Database storage for request tracking and status updates
- Integration with SQS for triggering Claude Code processing on the development server
- Status tracking throughout the automation lifecycle

**Architectural position:** This feature sits in `features/automation/` and follows standard feature module patterns. It integrates with `infrastructure/aws/queue.py` for SQS messaging.

## Purpose

Enable fully autonomous backend development where:
1. User submits feature request/bug report via API
2. Request is queued for processing
3. Claude Code picks up the request on development server
4. Orchestration commands guide implementation
5. Status updates flow back to the database
6. User can track progress via API

## Directory Structure

```
features/automation/
├── __init__.py           # Router export
├── routes.py             # FastAPI endpoints
├── service.py            # Business logic
├── dependencies.py       # FastAPI dependencies
├── db_models.py          # SQLAlchemy models
├── schemas/
│   ├── __init__.py       # Schema exports
│   ├── request.py        # Request DTOs
│   └── response.py       # Response DTOs
├── repositories/
│   ├── __init__.py
│   └── automation_repository.py
└── CLAUDE.md             # This file
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/automation/requests` | Submit new request |
| GET | `/api/v1/automation/requests/{id}` | Get request details |
| PATCH | `/api/v1/automation/requests/{id}` | Update request |
| PATCH | `/api/v1/automation/requests/{id}/status` | Update status (convenience) |
| GET | `/api/v1/automation/requests` | List requests with filters |
| GET | `/api/v1/automation/pending` | Get pending requests for processing |
| GET | `/api/v1/automation/health` | Health check |

## Request Types

- **feature**: New feature implementation
- **bug**: Bug investigation and fix
- **research**: Deep research task
- **refactor**: Code refactoring

## Request Statuses

| Status | Description |
|--------|-------------|
| pending | Waiting to be picked up |
| planning | Creating implementation plan |
| implementing | Executing milestones |
| testing | Running test suite |
| reviewing | Security review / PR review |
| deploying | Deploying to staging/production |
| completed | Successfully finished |
| failed | Failed with error |
| blocked | Blocked, needs intervention |

## Database Model

`AutomationRequest` table tracks:
- Request metadata (type, priority, title, description)
- Processing state (status, current_phase, session_id)
- Milestones (JSON array of implementation steps)
- Artifacts (plan_document, pr_url, test_results)
- Timestamps (created_at, started_at, completed_at, last_update)
- Error handling (error_message, retry_count)

## Integration with Claude Code

### Custom Commands (`.claude/commands/`)
- `process-request.md` - Main orchestrator
- `plan-feature.md` - Create implementation plan
- `implement.md` - Execute milestone
- `test.md` - Run test suite
- `research.md` - Deep research

### Custom Agents (`.claude/agents/`)
- `research-agent.md` - Investigation specialist
- `endpoint-builder.md` - FastAPI implementation
- `test-writer.md` - Pytest test creation
- `documentation-agent.md` - Documentation updates

### Hook Scripts (`.claude/scripts/`)
- `fetch_request.py` - Load request details
- `update_request_status.py` - Update status via API
- `security_check.py` - PreToolUse security validation
- `verify_completion.py` - Stop hook for quality gates

## Workflow Example

```
1. User POSTs to /api/v1/automation/requests
   └── Creates database record
   └── Queues to SQS (if configured)

2. Dev server polls SQS
   └── Receives message with request_id
   └── Invokes: claude -p "/project:process-request {id}"

3. Claude Code orchestrates
   └── /project:plan-feature creates milestones
   └── /project:implement executes each milestone
   └── /project:test validates changes
   └── Updates status via update_request_status.py

4. User GETs /api/v1/automation/requests/{id}
   └── Sees current status, milestones, artifacts
```

## Configuration

Environment variable:
- `AWS_SQS_AUTOMATION_QUEUE_URL` - SQS queue for request processing

If not configured, requests are stored but not automatically queued.

## Usage Examples

### Submit Feature Request
```bash
curl -X POST http://localhost:8000/api/v1/automation/requests \
  -H "Content-Type: application/json" \
  -d '{
    "type": "feature",
    "title": "Add rate limiting to public endpoints",
    "description": "Implement rate limiting for all /api/v1/public/* endpoints. Limit to 100 requests/minute per IP.",
    "priority": "medium"
  }'
```

### Check Status
```bash
curl http://localhost:8000/api/v1/automation/requests/{id}
```

### List Pending Requests
```bash
curl http://localhost:8000/api/v1/automation/pending
```

## Related Documentation

- `.claude/commands/` - Custom command definitions
- `.claude/agents/` - Custom agent definitions
- `.claude/settings.json` - Hooks configuration
- `DocumentationApp/backend-automation-claude-code-native-proposal.md` - Full architecture proposal
