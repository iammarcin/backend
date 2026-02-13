---
description: Deep research task for investigating bugs, exploring implementation options, or understanding codebase patterns.
allowed-tools: Read, Glob, Grep, Task, WebSearch, WebFetch
model: claude-sonnet-4-5-20250929
---

# Research Task

## Context
- Request ID: $1
- Research topic: $2

## Research Process

### Step 1: Understand the Research Question

Parse what needs to be researched:
- Is this a bug investigation?
- Is this exploring implementation options?
- Is this understanding existing patterns?
- Is this external technology research?

### Step 2: Codebase Exploration

Use the Explore agent for thorough codebase analysis:

**For Bug Investigation:**
```
Use Task tool with subagent_type=Explore:
- Thoroughness: very thorough
- Focus on: error traces, related code paths, recent changes
```

**For Implementation Research:**
```
Use Task tool with subagent_type=Explore:
- Thoroughness: medium to very thorough
- Focus on: similar features, patterns, dependencies
```

### Step 3: External Research (if needed)

For technology questions or best practices:
- Search official documentation
- Look for recent articles and guides
- Check GitHub for reference implementations

### Step 4: Synthesize Findings

Create a research document with:

```markdown
# Research: [Topic]

## Summary
[2-3 sentence overview of findings]

## Research Questions
1. [Question 1]
2. [Question 2]

## Findings

### [Finding Category 1]
**Location**: `file/path.py:line`
**Details**: [explanation]
**Relevance**: [how this relates to the question]

### [Finding Category 2]
...

## Code References
- `path/to/file.py:123` - [description]
- `path/to/other.py:456` - [description]

## External References
- [Resource Name](url) - [why it's relevant]

## Recommendations
1. [Recommendation 1 with rationale]
2. [Recommendation 2 with rationale]

## Next Steps
- [ ] [Action item 1]
- [ ] [Action item 2]

## Open Questions
- [Any unresolved questions]
```

### Step 5: Save Research Document

Save to: `DocumentationApp/automation/research/request-$1-research.md`

### Step 6: Update Request

```bash
python3 .claude/scripts/update_request_status.py $1 \
  --status completed \
  --plan DocumentationApp/automation/research/request-$1-research.md
```

## Research Quality Standards

Good research should:
- Cite specific file:line references
- Include relevant code snippets
- Cross-reference with existing documentation
- Consider implications across architecture layers
- Provide actionable recommendations
- Note any assumptions made

## Output

When complete, provide:
1. Executive summary (2-3 sentences)
2. Key findings (bullet points)
3. Recommendations
4. Link to full research document
