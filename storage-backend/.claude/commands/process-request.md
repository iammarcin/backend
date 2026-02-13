---
description: Main entry point for processing automation requests. Orchestrates the full workflow from request to deployment.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task, WebFetch, WebSearch
model: claude-sonnet-4-5-20250929
---

# Process Automation Request

## Context
- Request ID: $1
- Working directory: !`pwd`
- Git status: !`git status --short`
- Recent commits: !`git log --oneline -5`

## Request Details
Fetch the automation request from the database:

```bash
python3 .claude/scripts/fetch_request.py $1
```

## Workflow

You are the main orchestrator for processing automation requests. Follow these steps based on the request type:

### Phase 1: Request Analysis
1. Parse the request description and attachments
2. Identify request type (feature/bug/research/refactor)
3. Classify complexity (simple/medium/complex)
4. If bug report, analyze any attached logs or screenshots

### Phase 2: Route to Appropriate Workflow

**For Feature Requests:**
1. Update status: `python3 .claude/scripts/update_request_status.py $1 --status planning`
2. Run `/project:plan-feature $1` to create implementation plan
3. Review generated milestones for feasibility
4. For each milestone:
   - Update phase: `python3 .claude/scripts/update_request_status.py $1 --status implementing --phase M{n}`
   - Run `/project:implement $1 M{n}`
5. Run `/project:test $1` for comprehensive testing
6. If tests pass, consider running `/project:deploy $1 staging`

**For Bug Reports:**
1. Update status: `python3 .claude/scripts/update_request_status.py $1 --status planning --phase investigation`
2. Use the research-agent to investigate:
   - Analyze logs and symptoms
   - Trace code execution path
   - Identify root cause
3. Create a targeted fix plan
4. Implement the fix
5. Write regression test
6. Run test suite to verify

**For Research Tasks:**
1. Update status: `python3 .claude/scripts/update_request_status.py $1 --status implementing --phase research`
2. Use the research-agent with thoroughness=very_thorough
3. Generate comprehensive research document
4. Save findings to DocumentationApp/automation/research/
5. Update request with findings

**For Refactor Requests:**
1. Update status to planning
2. Analyze scope and impact
3. Create incremental refactoring milestones
4. Implement with tests at each step
5. Verify no regressions

### Phase 3: Completion
1. Verify all tests pass
2. Create summary of changes made
3. Update request status:
   - On success: `python3 .claude/scripts/update_request_status.py $1 --status completed`
   - On failure: `python3 .claude/scripts/update_request_status.py $1 --status failed --error "reason"`

## Error Handling
- If any phase fails, update status to 'blocked' with error details
- Do not proceed to next phase until current phase succeeds
- Maximum 2 retries per phase before escalating

## Quality Gates
- All code changes must pass ruff formatting and linting
- Test coverage must remain above 90%
- No security vulnerabilities (checked by PreToolUse hook)
