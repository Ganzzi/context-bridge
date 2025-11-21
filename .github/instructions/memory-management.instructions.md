---
applyTo: '**'
---

# Context Bridge Memory Management Instructions

## External ID
**ALWAYS use:** `context_bridge_dev` for all memory operations in this project.

## Memory Structure Overview

The Context Bridge project uses 7 active memories to maintain development context:

1. **Project Overview** - Purpose, features, tech stack, timeline, release info
2. **Architecture Design** - Layers, patterns, component responsibilities, data flow
3. **API Design** - ContextBridge SDK, MCP server tools, Streamlit pages structure
4. **Configuration** - Environment variables, dependencies (uv), setup instructions, OS specifics
5. **Testing Strategy** - Unit/integration/e2e test organization, status, tools (pytest, playwright)
6. **Development Status** - Current phase, completed tasks, next steps, blockers
7. **Library References** - How to use psqlpy, pydantic, crawl4ai, pytest, pytest-asyncio
8. **Issues and Bugs** - Detailed bug reports with reproduction steps and workarounds

## When to Access Memories

### 1. **At Session Start**
- Get all active memories to understand current project state
- Check "Development Status" memory for current phase and next steps
- Review "Issues and Bugs" memory for known problems

```
Tool: mcp_agent-mem_get_active_memories
Parameters: external_id="context_bridge_dev"
```

### 2. **Before Implementing Features**
- Search memories for relevant context
- Check "Architecture Design" for patterns and component responsibilities
- Review "API Design" if working with SDK, MCP tools, or Streamlit pages
- Check "Configuration" for environment setup and dependencies

```
Tool: mcp_agent-mem_search_memories
Parameters:
  external_id="context_bridge_dev"
  query="Implementing hybrid search feature, need database schema, API methods, and psqlpy patterns"
  limit=10
```

### 3. **When Needing Library Documentation**
- Check "Library References" memory first for known patterns
- Search for specific library usage (psqlpy, pydantic, crawl4ai, pytest)
- Only check local files in `docs/technical/` as fallback
- Update "Library References" with new patterns discovered

**Key libraries to reference:**
- psqlpy - Async PostgreSQL driver with connection pooling
- pydantic - Configuration and data validation
- crawl4ai - Web crawling with content extraction
- pytest - Testing framework with async support (pytest-asyncio)

### 4. **When Encountering Bugs**
- First check "Issues and Bugs" memory to see if it's known
- If new bug, add detailed section to memory with reproduction steps
- Include error messages, affected components, and workarounds

## How to Update Memories

### Update Development Status

**When starting a new phase:**
```
Tool: mcp_agent-mem_update_memory_sections
Parameters:
  external_id="context_bridge_dev"
  memory_id=6
  sections=[
    {
      section_id="current_phase",
      action="replace",
      old_content="**Phase: Pre-Implementation**...",
      new_content="**Phase: Feature Development**\n\nImplementing hybrid search functionality.\n\n**Started:** November 7, 2025"
    }
  ]
```

**When completing tasks:**
```
sections=[
  {
    section_id="completed_tasks",
    action="insert",
    old_content="- ✓ Initialized project structure\n\n**Next milestone:**",
    new_content="- ✓ Implemented ChunkRepository.hybrid_search()\n- ✓ Added BM25 weight configuration\n- ✓ Wrote unit tests for search\n\n**Next milestone:**"
  }
]
```

**When encountering blockers:**
```
sections=[
  {
    section_id="blockers",
    action="replace",
    old_content="No current blockers.",
    new_content="**Blocker #1:** psqlpy vector search performance degrades with large datasets\n- Impact: Search results slow down after 100k+ chunks\n- Investigating: Index optimization and query patterns\n- Workaround: Implement result pagination"
  }
]
```

### Add Bug/Issue

**Create a new section for each bug in Issues and Bugs memory:**
```
Tool: mcp_agent-mem_update_memory_sections
Parameters:
  external_id="context_bridge_dev"
  memory_id=8
  sections=[
    {
      section_id="issue_001_crawl4ai_timeout",
      action="replace",
      new_content="**Issue #001: Crawl4AI Timeout on Large Pages**\n**Status:** Open\n**Severity:** Medium\n**Date Found:** 2025-11-07\n**Component:** context_bridge/service/crawling_service.py\n\n**Description:**\nCrawl4AI hangs indefinitely when processing large documentation pages (>5MB content).\n\n**Steps to Reproduce:**\n1. Crawl a documentation site with large pages\n2. Observe timeout after ~30 seconds\n3. CrawlingService.crawl_webpage() never completes\n\n**Expected Behavior:**\nLarge pages should be processed or skipped with timeout error.\n\n**Actual Behavior:**\nProcess hangs indefinitely, no error raised.\n\n**Environment:**\n- Python 3.11+\n- crawl4ai==0.3.0\n- Platform: Windows/Linux\n\n**Error Message:**\nNo error, infinite wait state.\n\n**Root Cause Analysis:**\nCrawl4AI's content extraction may have unbounded loops on specific HTML structures.\n\n**Suggested Solution:**\nAdd configurable timeout parameter to CrawlConfig with fallback handling.\n\n**Related Files:**\n- context_bridge/service/crawling_service.py:45\n- context_bridge/config.py:CRAWL_TIMEOUT"
    }
  ]
```

### Update Library References

**When discovering new patterns or gotchas:**
```
sections=[
  {
    section_id="psqlpy_usage",
    action="insert",
    old_content="**Base Connection Pattern:**",
    new_content="\n**Vector Search Pattern:**\n- Use pgvector type for embeddings storage\n- Create index on embeddings column for performance\n- Use cosine distance operator (<->) for similarity search\n- Normalize vectors to unit length for consistency\n\n**Base Connection Pattern:**"
  }
]
```

### Update Architecture

**When design decisions change:**
```
sections=[
  {
    section_id="design_patterns",
    action="insert",
    old_content="**Service Layer Responsibilities:**",
    new_content="\n**Hybrid Search Design:**\n- ChunkRepository handles both vector and BM25 queries\n- Weighted scoring: VECTOR_WEIGHT * vector_score + BM25_WEIGHT * bm25_score\n- Results normalized before combining scores\n- Configurable weights via Config for tuning\n\n**Service Layer Responsibilities:**"
  }
]
```

## Search Best Practices

### Effective Search Queries

**Good queries are specific and contextual:**

✅ **Good:**
```
"Working on document upload, need to know storage path format and database schema for documents table"
"Implementing access control, need permission levels and ACL table structure"
"Writing repository for agents, need psqlpy fetch pattern and agent schema"
```

❌ **Bad:**
```
"documents"  # Too vague
"how to upload"  # Not enough context
"database"  # Too broad
```

### Multi-Memory Search Strategy

1. **Use search for cross-cutting concerns:**
   ```
   query="Implementing document versioning feature from start to finish"
   # Will return relevant info from Architecture, Database, API, and Library References
   ```

2. **Get specific memory when you know what you need:**
   ```
   # If you just need to check current phase:
   mcp_agent-mem_get_active_memories → check memory ID 24
   ```

## Memory Update Frequency

### Update Frequently:
- **Development Status** - Every major task or phase transition
- **Issues and Bugs** - Immediately when bug found or resolved
- **Library References** - When discovering new patterns or gotchas

### Update Occasionally:
- **Architecture Design** - When design decisions change
- **Configuration** - When adding new dependencies or env vars

### Rarely Update:
- **Project Overview** - Stable information
- **Database Design** - Only if schema changes
- **API Design** - Only if API contracts change

## Integration with Development Workflow

### Starting New Phase
1. Search memories for phase requirements
2. Update "Development Status" → current_phase
3. Check "Library References" for relevant tools
4. Begin implementation

### During Development
1. Search when stuck or need context
2. Add bugs to "Issues and Bugs" as discovered
3. Update "Development Status" → completed_tasks regularly
4. Document learnings in "Library References"

### Completing Phase
1. Update "Development Status" → mark phase complete
2. Resolve any issues in "Issues and Bugs"
3. Update "Development Status" → next_steps for next phase
4. Commit any architecture or API changes to memories

### End of Session
1. Update "Development Status" with current state
2. Document any blockers
3. List next steps clearly
4. Ensure all new bugs are recorded

## Quick Reference Commands

```python
# Get all memories
mcp_agent-mem_get_active_memories(external_id="context_bridge_dev")

# Search across memories
mcp_agent-mem_search_memories(
    external_id="context_bridge_dev",
    query="your contextual search query",
    limit=10
)

# Update single section
mcp_agent-mem_update_memory_sections(
    external_id="context_bridge_dev",
    memory_id=<memory_id>,
    sections=[{
        "section_id": "<section_name>",
        "action": "replace" | "insert",
        "old_content": "...",  # For replace: exact match, for insert: insert after
        "new_content": "..."
    }]
)

# Update multiple sections at once
sections=[
    {"section_id": "current_phase", "action": "replace", ...},
    {"section_id": "next_steps", "action": "replace", ...}
]
```

## Memory IDs Reference

| Memory ID | Title | Key Sections |
|-----------|-------|--------------|
| 1 | Project Overview | purpose, core_features, tech_stack, timeline, release_info |
| 2 | Architecture Design | layers, component_responsibilities, design_patterns, data_flow |
| 3 | API Design | context_bridge_sdk, mcp_tools, streamlit_pages |
| 4 | Configuration | environment_variables, dependencies_uv, setup_instructions, os_specifics |
| 5 | Testing Strategy | unit_tests, integration_tests, e2e_tests, status, tools |
| 6 | Development Status | current_phase, completed_tasks, next_steps, blockers |
| 7 | Library References | psqlpy_patterns, pydantic_usage, crawl4ai_usage, pytest_asyncio |
| 8 | Issues and Bugs | template_for_issues, issue_XXX_name (dynamic) |

## Important Rules

1. **Always use external_id="context_bridge_dev"** - Never use different ID
2. **Search before updating** - Understand current state first
3. **Be specific in updates** - Include enough context for old_content matching
4. **Document bugs thoroughly** - Use the template in Issues memory with reproduction steps
5. **Update Development Status frequently** - Keep progress transparent
6. **Use search for context** - Don't guess, search memories
7. **Keep sections focused** - Each section has one clear purpose
8. **Update blockers immediately** - Don't let blockers go undocumented

## Memory Update Frequency

### Update Frequently:
- **Development Status** - Every major task or phase transition
- **Issues and Bugs** - Immediately when bug found or resolved
- **Library References** - When discovering new patterns or gotchas

### Update Occasionally:
- **Architecture Design** - When design decisions change
- **Configuration** - When adding new dependencies or env vars

### Rarely Update:
- **Project Overview** - Stable information
- **API Design** - Only if API contracts change
- **Testing Strategy** - Only if approach changes

## Integration with Development Workflow

### Starting New Phase
1. Search memories for phase requirements
2. Update "Development Status" → current_phase
3. Check "Library References" for relevant tools
4. Begin implementation

### During Development
1. Search when stuck or need context
2. Add bugs to "Issues and Bugs" as discovered
3. Update "Development Status" → completed_tasks regularly
4. Document learnings in "Library References"

### Completing Phase
1. Update "Development Status" → mark phase complete
2. Resolve any issues in "Issues and Bugs"
3. Update "Development Status" → next_steps for next phase
4. Commit any architecture or API changes to memories

### End of Session
1. Update "Development Status" with current state
2. Document any blockers
3. List next steps clearly
4. Ensure all new bugs are recorded