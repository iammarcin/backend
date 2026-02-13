---
description: Execute a specific milestone from the implementation plan. Delegates to appropriate agent based on milestone type.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task
model: claude-sonnet-4-5-20250929
---

# Implement Milestone

## Context
- Request ID: $1
- Milestone ID: $2

## Load Plan
Read the implementation plan:
@DocumentationApp/automation/plans/request-$1-plan.md

## Implementation Process

### Step 1: Parse Milestone
Extract the milestone details from the plan document:
- Title and description
- Type (database, config, core, feature, api, test, docs)
- Assigned agent
- Dependencies (verify they're completed)
- Expected files to create/modify
- Acceptance criteria

### Step 2: Verify Dependencies
Before proceeding, ensure all dependent milestones are complete.
If dependencies are not met, report this and do not proceed.

### Step 3: Select Implementation Approach

Based on milestone type, choose the approach:

| Type | Agent | Primary Tools | Focus |
|------|-------|---------------|-------|
| database | endpoint-builder | Write, Edit, Bash | SQLAlchemy models, migrations |
| config | endpoint-builder | Write, Edit | Configuration files in config/ |
| core | endpoint-builder | Write, Edit | Core infrastructure in core/ |
| feature | endpoint-builder | Write, Edit, Bash | Feature modules in features/ |
| api | endpoint-builder | Write, Edit | Routes, schemas, dependencies |
| test | test-writer | Write, Edit, Bash(pytest) | Test files in tests/ |
| docs | documentation-agent | Write, Edit | Documentation, CLAUDE.md |

### Step 4: Execute Implementation

**For code milestones (database, config, core, feature, api):**
1. Check existing patterns in similar files
2. Create/modify files following project conventions
3. Ensure imports are correct
4. Follow 200-250 line file limit
5. Run syntax check after each file

**For test milestones:**
1. Create test file matching the tested module
2. Use existing fixtures from conftest.py
3. Cover success and failure paths
4. Include edge cases
5. Verify tests pass: `docker exec backend pytest tests/path/to/test.py -v`

**For documentation milestones:**
1. Update relevant CLAUDE.md files
2. Add handbook entries if needed
3. Update feature documentation

### Step 5: Verify Completion

After implementation:

1. **Syntax check**: Ensure no Python errors
   ```bash
   docker exec backend python -m py_compile <file>
   ```

2. **Lint check**: Run ruff on modified files
   ```bash
   docker exec backend ruff check <files>
   ```

3. **Type check** (if applicable):
   ```bash
   docker exec backend mypy <files> --ignore-missing-imports
   ```

4. **Run related tests**:
   ```bash
   docker exec backend pytest tests/ -k "<relevant_tests>" -v
   ```

5. **Verify acceptance criteria** from the milestone

### Step 6: Update Status

```bash
python3 .claude/scripts/update_request_status.py $1 \
  --status implementing \
  --phase $2
```

If milestone completes successfully, report:
- Files created/modified
- Tests added/updated
- Any deviations from plan

If milestone fails, report:
- What failed and why
- Suggested remediation
- Whether to retry or escalate

## Rollback on Failure

If implementation fails catastrophically:
1. Capture error details
2. Reset changed files: `git checkout -- <files>`
3. Report failure with context
4. Do NOT leave partial implementations
