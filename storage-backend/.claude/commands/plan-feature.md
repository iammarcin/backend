---
description: Transform a feature request into structured implementation milestones. Analyzes codebase and creates actionable plan.
allowed-tools: Read, Glob, Grep, Task, WebSearch
model: claude-sonnet-4-5-20250929
---

# Plan Feature Implementation

## Context
- Request ID: $1

## Request Details
```bash
python3 .claude/scripts/fetch_request.py $1
```

## Planning Process

### Step 1: Understand the Request
Parse the feature request and identify:
- Core functionality required
- Expected API endpoints (if any)
- Database changes needed (new tables, columns)
- External integrations
- Testing requirements
- Documentation updates

### Step 2: Codebase Analysis
Before planning, explore the relevant parts of the codebase:

1. **Find similar features** - Use the Explore agent or Grep to find similar implementations
2. **Understand patterns** - Check existing features in `features/` for patterns to follow
3. **Identify dependencies** - What existing code will this feature interact with?
4. **Check configuration** - What config changes might be needed in `config/`?

### Step 3: Architecture Decision
Determine the implementation approach:

| Question | Options |
|----------|---------|
| Which layers affected? | config/, core/, features/, infrastructure/ |
| New feature module? | Yes (create features/newfeature/) or No (extend existing) |
| Database required? | New tables, modify existing, or none |
| New provider? | Add to core/providers/ or use existing |
| API endpoints? | REST, WebSocket, or both |

### Step 4: Create Milestones
Break down into atomic, independently testable milestones.

Each milestone must have:
- **ID**: M1, M2, M3...
- **Title**: Clear, actionable description
- **Type**: database | config | core | feature | api | test | docs
- **Agent**: endpoint-builder | test-writer | documentation-agent
- **Dependencies**: Which milestones must complete first (e.g., ["M1", "M2"])
- **Files**: List of files to create or modify
- **Acceptance**: How to verify this milestone is complete

### Step 5: Generate Plan Document
Create the plan at: `DocumentationApp/automation/plans/request-$1-plan.md`

Use this template:

```markdown
# Implementation Plan: [Feature Title]

## Overview
[1-2 paragraph summary of what will be built]

## Request Reference
- ID: $1
- Type: feature
- Priority: [from request]

## Affected Components
- [ ] config/
- [ ] core/
- [ ] features/
- [ ] infrastructure/
- [ ] tests/

## Milestones

### M1: [Title]
- **Type**: [type]
- **Agent**: [agent]
- **Dependencies**: None
- **Files**:
  - [file paths]
- **Acceptance**: [criteria]

### M2: [Title]
...

## Risk Assessment
- [Potential issues and mitigations]

## Testing Strategy
- Unit tests for: [components]
- Integration tests for: [flows]
- Manual testing: [scenarios]

## Estimated Complexity
[Simple | Medium | Complex]
```

### Step 6: Update Request
Save the milestones to the database:

```bash
python3 .claude/scripts/update_request_status.py $1 \
  --status planning \
  --plan DocumentationApp/automation/plans/request-$1-plan.md
```

## Output
When complete, summarize:
1. Number of milestones created
2. Key technical decisions made
3. Any questions or clarifications needed
4. Recommended execution order
