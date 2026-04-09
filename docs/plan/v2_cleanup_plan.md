# Context Bridge v2 Cleanup Plan

**Document Version:** 1.0  
**Created:** November 21, 2025  
**Purpose:** Simplify v2 implementation by removing unnecessary features from Core API and MCP Server  
**Status:** Planning Phase

---

## Table of Contents

1. [Overview](#overview)
2. [Scope of Changes](#scope-of-changes)
3. [Phase 1: MCP Server Cleanup](#phase-1-mcp-server-cleanup)
4. [Phase 2: Core API Cleanup - Tags](#phase-2-core-api-cleanup---tags)
5. [Phase 3: Core API Cleanup - Groups](#phase-3-core-api-cleanup---groups)
6. [Phase 4: Context Agent Refactoring](#phase-4-context-agent-refactoring)
7. [Phase 5: Reprocessing Service Decision](#phase-5-reprocessing-service-decision)
8. [Phase 6: Testing & Validation](#phase-6-testing--validation)
9. [Success Criteria](#success-criteria)

---

## Overview

This plan addresses the over-engineering in the v2 implementation by:
- Simplifying the MCP server to essential tools only
- Removing programmatic tag/group management from Core API (keep UI-focused)
- Reorganizing context generation code
- Ensuring type safety with Pydantic models

### Design Philosophy

- **MCP Server**: Minimal read-only interface for AI agents (find, search)
- **Core API**: Support for Streamlit UI management features
- **Streamlit UI**: Full management interface for tags, groups, documents

---

## Scope of Changes

### What's Being Removed

1. **MCP Server Tools** (7 tools → 2 tools):
   - ❌ `list_tags`
   - ❌ `add_document_tags`
   - ❌ `remove_tag_from_document`
   - ❌ `list_groups`
   - ❌ `get_group_status`
   - ❌ `generate_context_for_group`
   - ❌ `list_non_context_groups`
   - ❌ `reprocess_group`
   - ❌ `reprocess_multiple_groups`
   - ✅ Keep: `find_documents` (with tags in response)
   - ✅ Keep: `search_content`

2. **Core API Methods** (5 methods removed):
   - ❌ `add_tags_to_document()` - Use Streamlit UI
   - ❌ `remove_tag_from_document()` - Use Streamlit UI
   - ❌ `remove_all_tags_from_document()` - Use Streamlit UI
   - ❌ `get_documents_by_tag()` - Use `find_documents(tags=[...])`
   - ❌ `get_group_info()` - Use Streamlit UI
   - ❌ `generate_context_for_group()` - Use Streamlit UI
   - ❌ `list_non_context_groups()` - Use Streamlit UI
   - ❌ `reprocess_group_with_context()` - Use Streamlit UI
   - ❌ `reprocess_multiple_groups_with_context()` - Use Streamlit UI

3. **Core API Methods** (Keep for Streamlit):
   - ✅ `list_tags()` - Needed for UI tag selector
   - ✅ `get_document_tags()` - Needed for displaying doc tags
   - ✅ `list_groups()` - Needed for groups page

### What's Being Reorganized

1. **Context Agent**:
   - Move from: `context_bridge/service/context_agent.py`
   - Move to: `context_bridge/agents/context_generator.py`
   - Fix: Use `result.output.context` instead of `result.data.context`
   - Fix: Use `output_type` instead of `result_type` in Agent init
   - Ensure: All types are Pydantic models, no `dict` or `Any`

2. **Reprocessing Service**:
   - Evaluate if still needed after Core API cleanup
   - If needed: Move from `context_bridge/services/` to `context_bridge/service/`
   - If not needed: Delete entirely

---

## Phase 1: MCP Server Cleanup

**Duration:** 1-2 hours  
**Dependencies:** None  
**Priority:** High  
**Goal:** Restore MCP server to minimal essential tools

### 1.1 Revert MCP Server Files

**Files to revert/cleanup:**
- `context_bridge_mcp/server.py` - Remove new tools, keep only 2 tools
- `context_bridge_mcp/schemas.py` - Remove schemas for removed tools
- `context_bridge_mcp/__main__.py` - No changes needed
- `context_bridge_mcp/run.py` - No changes needed

### 1.2 Keep Only Essential Tools

**Tool 1: find_documents**
```python
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="find_documents",
            description=(
                "Find documentation by name, version, or query. "
                "Returns documents with their tags for categorization. "
                "Supports filtering by name, version, tags, and semantic query."
            ),
            inputSchema=FIND_DOCUMENTS_INPUT_SCHEMA,
        ),
        types.Tool(
            name="search_content",
            description=(
                "Search documentation content with hybrid vector + BM25 search. "
                "Requires a document_id to limit search scope. "
                "Returns relevant chunks with context and relevance scores."
            ),
            inputSchema=SEARCH_CONTENT_INPUT_SCHEMA,
        ),
    ]
```

**Handler 1: _handle_find_documents**
- Keep existing implementation
- Ensure tags are included in response (already done)
- Format: Return documents with `tags` field containing list of tag objects

**Handler 2: _handle_search_content**
- Keep existing implementation
- No changes needed

### 1.3 Remove Unused Schemas

**File:** `context_bridge_mcp/schemas.py`

Remove schemas:
- `LIST_TAGS_INPUT_SCHEMA`
- `ADD_DOCUMENT_TAGS_INPUT_SCHEMA`
- `REMOVE_TAG_INPUT_SCHEMA`
- `LIST_GROUPS_INPUT_SCHEMA`
- `GET_GROUP_STATUS_INPUT_SCHEMA`
- `GENERATE_CONTEXT_FOR_GROUP_INPUT_SCHEMA`
- `LIST_NON_CONTEXT_GROUPS_INPUT_SCHEMA`
- `REPROCESS_GROUP_INPUT_SCHEMA`
- `REPROCESS_MULTIPLE_GROUPS_INPUT_SCHEMA`

Keep schemas:
- `FIND_DOCUMENTS_INPUT_SCHEMA`
- `SEARCH_CONTENT_INPUT_SCHEMA`
- `UPDATE_FIND_DOCUMENTS_INPUT_SCHEMA` (if it exists and is used)

### 1.4 Checklist - Phase 1

- [ ] **Update server.py** (Estimated: 30 min)
  - [ ] Remove tool definitions for: list_tags, add_document_tags, remove_tag_from_document
  - [ ] Remove tool definitions for: list_groups, get_group_status, generate_context_for_group
  - [ ] Remove tool definitions for: list_non_context_groups, reprocess_group, reprocess_multiple_groups
  - [ ] Remove handler functions: `_handle_list_tags`, `_handle_add_document_tags`, `_handle_remove_tag`
  - [ ] Remove handler functions: `_handle_list_groups`, `_handle_get_group_status`, `_handle_generate_context_for_group`
  - [ ] Remove handler functions: `_handle_list_non_context_groups`, `_handle_reprocess_group`, `_handle_reprocess_multiple_groups`
  - [ ] Keep only: `_handle_find_documents` and `_handle_search_content`
  - [ ] Update `handle_call_tool()` to route only 2 tools
  - **Result:** MCP server with 2 tools (down from 11 tools)

- [ ] **Update schemas.py** (Estimated: 10 min)
  - [ ] Remove all unused input schemas (9 schemas)
  - [ ] Keep only: `FIND_DOCUMENTS_INPUT_SCHEMA`, `SEARCH_CONTENT_INPUT_SCHEMA`
  - **Result:** Clean schema file with only essential definitions

- [ ] **Verify find_documents returns tags** (Estimated: 10 min)
  - [ ] Check that `_handle_find_documents` includes tags in response
  - [ ] Ensure tags are formatted correctly: `[{id, name, category, description}, ...]`
  - **Result:** Tags available to AI agents via find_documents

- [ ] **Test MCP server** (Estimated: 10 min)
  - [ ] Start MCP server: `python -m context_bridge_mcp`
  - [ ] Verify only 2 tools listed
  - [ ] Test find_documents returns tags
  - [ ] Test search_content works
  - **Result:** Functional minimal MCP server

**Phase 1 Total Estimated Time:** 1 hour

---

## Phase 2: Core API Cleanup - Tags

**Duration:** 1-2 hours  
**Dependencies:** Phase 1  
**Priority:** High  
**Goal:** Remove programmatic tag management from Core API, keep UI-focused methods

### 2.1 Remove Core API Methods

**File:** `context_bridge/core.py`

Remove methods:
```python
# Remove these 4 methods
async def add_tags_to_document(...)      # Line ~694-709
async def remove_tag_from_document(...)  # Line ~712-726
async def remove_all_tags_from_document(...)  # Line ~745-758
async def get_documents_by_tag(...)      # Line ~763-792
```

Keep methods:
```python
# Keep these for Streamlit UI
async def list_tags(...)           # Needed for tag selector
async def get_document_tags(...)   # Needed for displaying doc tags
```

**Rationale:**
- Tag management should happen in Streamlit UI
- `find_documents(tags=[...])` already supports tag filtering
- Streamlit can call repository directly for tag operations
- Simpler Core API = easier to maintain

### 2.2 Update find_documents to Return Tags

**File:** `context_bridge/core.py`

Ensure `find_documents()` returns documents with tags:
```python
async def find_documents(
    self,
    query: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    name: Optional[str] = None,
    version: Optional[str] = None,
    id: Optional[int] = None,
    tags: Optional[List[int]] = None,
    tag_match_all: bool = False,
) -> List[Document]:
    """
    Find documents with optional tag filtering.
    
    Returns:
        List of Document objects with tags populated
    """
    # Implementation already exists, verify tags are returned
```

### 2.3 Update Streamlit UI for Direct Repository Access

**Files:**
- `streamlit_app/pages/crawl.py` - Tag adding during crawl
- `streamlit_app/pages/documents.py` - Tag management UI

Update to call repository directly:
```python
# In Streamlit pages - call repository directly
async with bridge._db_manager.connection() as conn:
    tag_repo = TagRepository(conn)
    await tag_repo.add_tags_to_document(doc_id, tag_ids)
```

**Rationale:**
- Streamlit already has access to bridge instance
- Direct repository calls are fine for UI layer
- Reduces complexity in Core API

### 2.4 Checklist - Phase 2

- [ ] **Remove Core API methods** (Estimated: 20 min)
  - [ ] Remove `add_tags_to_document()` from `context_bridge/core.py` (~15 lines)
  - [ ] Remove `remove_tag_from_document()` from `context_bridge/core.py` (~14 lines)
  - [ ] Remove `remove_all_tags_from_document()` from `context_bridge/core.py` (~13 lines)
  - [ ] Remove `get_documents_by_tag()` from `context_bridge/core.py` (~29 lines)
  - **Result:** 4 methods removed (~71 lines cleaned)

- [ ] **Verify kept methods** (Estimated: 10 min)
  - [ ] Verify `list_tags()` works correctly
  - [ ] Verify `get_document_tags()` works correctly
  - [ ] Verify `find_documents(tags=[...])` filters correctly
  - **Result:** Essential tag methods functional

- [ ] **Update Streamlit UI** (Estimated: 30 min)
  - [ ] Update `streamlit_app/pages/crawl.py` to use `TagRepository` directly
  - [ ] Update `streamlit_app/pages/documents.py` to use `TagRepository` directly
  - [ ] Verify tag adding/removing works in UI
  - [ ] Test tag filtering in document search
  - **Result:** Streamlit UI uses repositories directly

- [ ] **Update documentation** (Estimated: 15 min)
  - [ ] Update `README.md` to remove removed methods from examples
  - [ ] Update `docs/guides/tags_system_guide.md` to clarify Streamlit-only management
  - **Result:** Documentation reflects simplified API

- [ ] **Run tag tests** (Estimated: 15 min)
  - [ ] Run `pytest tests/unit/test_core_tags_api.py`
  - [ ] Update/remove tests for removed methods
  - [ ] Verify remaining tag tests pass
  - **Result:** All tag tests passing

**Phase 2 Total Estimated Time:** 1.5 hours

---

## Phase 3: Core API Cleanup - Groups

**Duration:** 1-2 hours  
**Dependencies:** Phase 2  
**Priority:** High  
**Goal:** Remove advanced group management from Core API, keep simple listing

### 3.1 Remove Core API Methods

**File:** `context_bridge/core.py`

Remove methods:
```python
# Remove these 5 methods
async def get_group_info(...)                        # Line ~857-916
async def generate_context_for_group(...)            # Line ~923-972
async def list_non_context_groups(...)               # Line ~978-1008
async def reprocess_group_with_context(...)          # Line ~1015-1099
async def reprocess_multiple_groups_with_context(...)  # Line ~1179-1296
```

Keep methods:
```python
# Keep for Streamlit UI
async def list_groups(...)         # Needed for groups page basic listing
```

**Rationale:**
- Group details and reprocessing should be in Streamlit UI
- Streamlit groups page can call repositories/services directly
- Simplifies Core API surface area
- Advanced features remain available, just not in public API

### 3.2 Update Streamlit Groups Page

**File:** `streamlit_app/pages/groups.py`

Update to use services directly:
```python
# For group info - call repository directly
async with bridge._db_manager.connection() as conn:
    group_repo = GroupRepository(conn)
    group = await group_repo.get_group_by_id(group_id)
    pages = await page_repo.get_pages_for_group(group_id)
    
# For reprocessing - call ReprocessingService directly
reprocessing_service = ReprocessingService(
    bridge._db_manager,
    chunking_service,
    embedding_service,
    bridge.config
)
result = await reprocessing_service.reprocess_group(group_id, context_enabled=True)
```

### 3.3 Checklist - Phase 3

- [ ] **Remove Core API methods** (Estimated: 20 min)
  - [ ] Remove `get_group_info()` from `context_bridge/core.py` (~60 lines)
  - [ ] Remove `generate_context_for_group()` from `context_bridge/core.py` (~50 lines)
  - [ ] Remove `list_non_context_groups()` from `context_bridge/core.py` (~30 lines)
  - [ ] Remove `reprocess_group_with_context()` from `context_bridge/core.py` (~85 lines)
  - [ ] Remove `reprocess_multiple_groups_with_context()` from `context_bridge/core.py` (~118 lines)
  - **Result:** 5 methods removed (~343 lines cleaned)

- [ ] **Verify list_groups() works** (Estimated: 10 min)
  - [ ] Test `list_groups(document_id=...)` returns basic group info
  - [ ] Verify response includes: id, name, status, pages, chunks, created_at
  - **Result:** Basic group listing functional

- [ ] **Update Streamlit groups page** (Estimated: 40 min)
  - [ ] Import `GroupRepository`, `PageRepository`, `ChunkRepository`
  - [ ] Update group details section to call `GroupRepository.get_group_by_id()`
  - [ ] Update reprocess button to call `ReprocessingService.reprocess_group()`
  - [ ] Test all group page features work
  - **Result:** Streamlit groups page uses services directly

- [ ] **Update documentation** (Estimated: 15 min)
  - [ ] Update `README.md` to remove removed methods
  - [ ] Update `docs/guides/groups_system_guide.md` to clarify Streamlit-only management
  - **Result:** Documentation reflects simplified API

- [ ] **Run group tests** (Estimated: 15 min)
  - [ ] Run `pytest tests/unit/test_core_groups_api.py`
  - [ ] Update/remove tests for removed methods
  - [ ] Verify remaining group tests pass
  - **Result:** All group tests passing

**Phase 3 Total Estimated Time:** 1.5 hours

---

## Phase 4: Context Agent Refactoring

**Duration:** 1-2 hours  
**Dependencies:** Phase 3  
**Priority:** High  
**Goal:** Move context agent to proper location, fix Pydantic AI issues, ensure type safety

### 4.1 Move Context Agent

**From:** `context_bridge/service/context_agent.py`  
**To:** `context_bridge/agents/context_generator.py`

**Steps:**
1. Create `context_bridge/agents/` directory if not exists
2. Create `context_bridge/agents/__init__.py`
3. Move `context_agent.py` → `context_generator.py`
4. Rename class if needed (optional: `ContextGenerationAgent` → `ContextGenerator`)

### 4.2 Fix Pydantic AI Usage

**Issue 1: Use `output_type` instead of `result_type`**

Current (incorrect):
```python
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    result_type=ChunkContext,  # ❌ Wrong parameter name
    model_settings={...},
)
```

Fixed:
```python
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    output_type=ChunkContext,  # ✅ Correct parameter name
    model_settings={...},
)
```

**Issue 2: Use `result.output.context` instead of `result.data.context`**

Current (incorrect):
```python
result = await self._agent.run(user_prompt)
context = result.data.context  # ❌ Wrong attribute
```

Fixed:
```python
result = await self._agent.run(user_prompt)
context = result.output.context  # ✅ Correct attribute
```

### 4.3 Ensure Type Safety

**Rule:** Never use `dict`, `Dict[str, Any]`, or `Any` types in context generation

**Current models:**
```python
class ChunkContext(BaseModel):
    """Output model for chunk context generation."""
    context: str = Field(description="Succinct context")
```

**Verify all method signatures use Pydantic models:**
```python
class ContextGenerator:
    async def generate_context(
        self,
        chunk_content: str,        # ✅ Primitive types OK
        document_content: str,     # ✅ Primitive types OK
    ) -> str:                      # ✅ Returns primitive, not dict
        """Generate context for a chunk."""
        result = await self._agent.run(...)
        return result.output.context  # ✅ Type-safe access
        
    async def generate_contexts_batch(
        self,
        chunks: List[str],         # ✅ Typed list
        document_content: str,
    ) -> List[str]:                # ✅ Typed return
        """Generate contexts for multiple chunks."""
```

### 4.4 Update All Imports

**Files to update:**
- `context_bridge/service/doc_manager.py` - Import ContextGenerator
- `context_bridge/services/reprocessing_service.py` - Import ContextGenerator
- Any other files importing `context_agent.py`

Update import:
```python
# Old
from context_bridge.service.context_agent import ContextGenerationAgent

# New
from context_bridge.agents.context_generator import ContextGenerator
```

### 4.5 Checklist - Phase 4

- [ ] **Create agents directory** (Estimated: 5 min)
  - [ ] Create `context_bridge/agents/` directory
  - [ ] Create `context_bridge/agents/__init__.py`
  - [ ] Export `ContextGenerator` in `__init__.py`
  - **Result:** Proper module structure

- [ ] **Move and rename file** (Estimated: 10 min)
  - [ ] Move `context_bridge/service/context_agent.py` → `context_bridge/agents/context_generator.py`
  - [ ] Optionally rename class: `ContextGenerationAgent` → `ContextGenerator`
  - [ ] Delete old file
  - **Result:** Context agent in correct location

- [ ] **Fix Pydantic AI usage** (Estimated: 20 min)
  - [ ] Change `result_type=ChunkContext` → `output_type=ChunkContext`
  - [ ] Change `result.data.context` → `result.output.context`
  - [ ] Test context generation works
  - **Result:** Correct Pydantic AI API usage

- [ ] **Verify type safety** (Estimated: 15 min)
  - [ ] Search for `Any` type usage in context_generator.py
  - [ ] Search for `dict` or `Dict` type usage in context_generator.py
  - [ ] Ensure all method signatures use Pydantic models or primitives
  - [ ] Run mypy/pyright on the file
  - **Result:** Type-safe context generation

- [ ] **Update imports** (Estimated: 20 min)
  - [ ] Update `context_bridge/service/doc_manager.py`
  - [ ] Update `context_bridge/services/reprocessing_service.py`
  - [ ] Search codebase for `context_agent` import
  - [ ] Update all imports to use new path
  - **Result:** All imports resolved

- [ ] **Test context generation** (Estimated: 20 min)
  - [ ] Run unit tests for context generation
  - [ ] Test with sample document and chunks
  - [ ] Verify contexts are generated correctly
  - **Result:** Context generation functional

**Phase 4 Total Estimated Time:** 1.5 hours

---

## Phase 5: Reprocessing Service Decision

**Duration:** 30 min - 1 hour  
**Dependencies:** Phases 1-4  
**Priority:** Medium  
**Goal:** Decide fate of ReprocessingService and clean up services directory

### 5.1 Analyze ReprocessingService Usage

**File:** `context_bridge/services/reprocessing_service.py`

**Methods provided:**
1. `reprocess_group()` - Re-process single group with context
2. `reprocess_multiple_groups()` - Batch re-process multiple groups

**Current usage:**
- ❌ Was called by `ContextBridge.reprocess_group_with_context()` (being removed)
- ❌ Was called by `ContextBridge.reprocess_multiple_groups_with_context()` (being removed)
- ✅ Still needed by Streamlit groups page for reprocessing UI

### 5.2 Decision: Keep and Move

**Rationale:**
- Reprocessing logic is complex and should be in a service
- Streamlit groups page needs this functionality
- Moving to `context_bridge/service/` aligns with other services
- Keeps Core API clean while maintaining functionality

**Action:** Move from `context_bridge/services/` → `context_bridge/service/`

### 5.3 Clean Up services/ Directory

**Current state:**
- `context_bridge/services/reprocessing_service.py` - Singular file in plural directory

**Action:** 
- Move file to `context_bridge/service/reprocessing_service.py`
- Delete empty `context_bridge/services/` directory
- Update all imports

### 5.4 Checklist - Phase 5

- [ ] **Analyze ReprocessingService dependencies** (Estimated: 10 min)
  - [ ] Check what methods are called by Core API (being removed)
  - [ ] Check what methods are called by Streamlit UI (still needed)
  - [ ] Check what repositories/services it uses
  - **Result:** Clear understanding of dependencies

- [ ] **Move ReprocessingService** (Estimated: 10 min)
  - [ ] Move `context_bridge/services/reprocessing_service.py` → `context_bridge/service/reprocessing_service.py`
  - [ ] Delete empty `context_bridge/services/` directory
  - **Result:** Service in correct location

- [ ] **Update imports** (Estimated: 15 min)
  - [ ] Update `streamlit_app/pages/groups.py`
  - [ ] Search codebase for `context_bridge.services.reprocessing_service`
  - [ ] Update all imports to `context_bridge.service.reprocessing_service`
  - **Result:** All imports resolved

- [ ] **Update ReprocessingService imports** (Estimated: 10 min)
  - [ ] Update import in ReprocessingService: `context_bridge.service.context_agent` → `context_bridge.agents.context_generator`
  - [ ] Update class name if renamed in Phase 4
  - [ ] Test service initializes correctly
  - **Result:** Service imports correct context generator

- [ ] **Test reprocessing** (Estimated: 15 min)
  - [ ] Test ReprocessingService.reprocess_group() works
  - [ ] Test from Streamlit groups page
  - [ ] Verify chunks are regenerated with context
  - **Result:** Reprocessing functional

**Phase 5 Total Estimated Time:** 1 hour

---

## Phase 6: Testing & Validation

**Duration:** 2-3 hours  
**Dependencies:** Phases 1-5  
**Priority:** Critical  
**Goal:** Ensure all changes work correctly and tests pass

### 6.1 Unit Tests

**Tests to update/remove:**
- `tests/unit/test_core_tags_api.py` - Remove tests for removed methods
- `tests/unit/test_core_groups_api.py` - Remove tests for removed methods
- `tests/unit/test_mcp_tag_handlers.py` - Remove tests for removed tools
- `tests/unit/test_mcp_group_handlers.py` - Remove tests for removed tools
- `tests/unit/test_context_agent.py` - Update imports and test location
- `tests/unit/test_reprocessing_service.py` - Update imports

**Tests to keep:**
- Repository tests (no changes)
- Service tests (update imports only)
- Integration tests (update imports only)

### 6.2 Integration Tests

**Test scenarios:**
1. **MCP Server:**
   - Start MCP server
   - Verify only 2 tools listed
   - Call `find_documents` and verify tags in response
   - Call `search_content` and verify results
   
2. **Tags in Streamlit:**
   - Crawl document with tags
   - View document tags
   - Add/remove tags via UI
   - Filter documents by tags

3. **Groups in Streamlit:**
   - View groups list
   - View group details
   - Reprocess group with context
   - Verify chunks regenerated

4. **Context Generation:**
   - Import ContextGenerator from new location
   - Generate context for test chunk
   - Verify output is string with 2-3 sentences

### 6.3 Manual Testing Checklist

**MCP Server:**
- [ ] Start server: `python -m context_bridge_mcp`
- [ ] Check logs show only 2 tools
- [ ] Test with MCP client if available

**Streamlit UI:**
- [ ] Start UI: `streamlit run streamlit_app/app.py`
- [ ] Navigate to Documents page
- [ ] Test tag filtering
- [ ] Navigate to Groups page
- [ ] Test group details view
- [ ] Test group reprocessing

**Python API:**
- [ ] Import `ContextBridge`
- [ ] Call `find_documents(tags=[...])`
- [ ] Call `list_tags()`
- [ ] Call `list_groups()`
- [ ] Verify removed methods are not accessible

### 6.4 Checklist - Phase 6

- [ ] **Update unit tests** (Estimated: 45 min)
  - [ ] Remove tests for `add_tags_to_document()`, `remove_tag_from_document()`, etc.
  - [ ] Remove tests for `get_group_info()`, `reprocess_group_with_context()`, etc.
  - [ ] Remove MCP tests for removed tools
  - [ ] Update context agent test imports
  - [ ] Update reprocessing service test imports
  - **Result:** Tests updated for new structure

- [ ] **Run all unit tests** (Estimated: 15 min)
  - [ ] Run `pytest tests/unit/ -v`
  - [ ] Fix any failing tests
  - [ ] Verify all pass
  - **Result:** All unit tests passing

- [ ] **Run integration tests** (Estimated: 15 min)
  - [ ] Run `pytest tests/integration/ -v`
  - [ ] Fix any failing tests
  - [ ] Verify all pass
  - **Result:** All integration tests passing

- [ ] **Manual MCP server testing** (Estimated: 20 min)
  - [ ] Start MCP server
  - [ ] Verify 2 tools in logs
  - [ ] Test find_documents with tags
  - [ ] Test search_content
  - **Result:** MCP server functional

- [ ] **Manual Streamlit UI testing** (Estimated: 30 min)
  - [ ] Start Streamlit app
  - [ ] Test Documents page - tag filtering
  - [ ] Test Crawl page - tag adding
  - [ ] Test Groups page - view details
  - [ ] Test Groups page - reprocess with context
  - **Result:** Streamlit UI fully functional

- [ ] **Type checking** (Estimated: 15 min)
  - [ ] Run `mypy context_bridge/` (if configured)
  - [ ] Run `pyright context_bridge/` (if configured)
  - [ ] Fix any type errors
  - **Result:** Type-safe codebase

**Phase 6 Total Estimated Time:** 2.5 hours

---

## Success Criteria

### ✅ MCP Server
- [ ] Only 2 tools: `find_documents` and `search_content`
- [ ] `find_documents` returns tags in response
- [ ] Server starts without errors
- [ ] Tools respond correctly

### ✅ Core API - Tags
- [ ] Removed: `add_tags_to_document()`, `remove_tag_from_document()`, `remove_all_tags_from_document()`, `get_documents_by_tag()`
- [ ] Kept: `list_tags()`, `get_document_tags()`
- [ ] `find_documents(tags=[...])` filters correctly

### ✅ Core API - Groups
- [ ] Removed: `get_group_info()`, `generate_context_for_group()`, `list_non_context_groups()`, `reprocess_group_with_context()`, `reprocess_multiple_groups_with_context()`
- [ ] Kept: `list_groups()`
- [ ] Basic group listing works

### ✅ Context Agent
- [ ] Located at: `context_bridge/agents/context_generator.py`
- [ ] Uses `output_type=ChunkContext` (not `result_type`)
- [ ] Uses `result.output.context` (not `result.data.context`)
- [ ] No `dict`, `Dict[str, Any]`, or `Any` types in signatures
- [ ] All imports updated

### ✅ Reprocessing Service
- [ ] Located at: `context_bridge/service/reprocessing_service.py`
- [ ] Imports updated to use new context generator path
- [ ] Works correctly from Streamlit UI

### ✅ Streamlit UI
- [ ] Tags management works (add/remove via UI)
- [ ] Documents filtering by tags works
- [ ] Groups page displays correctly
- [ ] Group reprocessing works

### ✅ Tests
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] No tests for removed methods
- [ ] Type checking passes (if configured)

---

## Timeline Summary

| Phase | Duration | Description |
|-------|----------|-------------|
| Phase 1 | 1 hour | MCP Server Cleanup |
| Phase 2 | 1.5 hours | Core API Cleanup - Tags |
| Phase 3 | 1.5 hours | Core API Cleanup - Groups |
| Phase 4 | 1.5 hours | Context Agent Refactoring |
| Phase 5 | 1 hour | Reprocessing Service Decision |
| Phase 6 | 2.5 hours | Testing & Validation |
| **Total** | **9 hours** | **Complete Cleanup** |

---

## Implementation Notes

### Type Safety Rules

1. **Never use `Any` in public methods:**
   ```python
   # ❌ Bad
   async def process(data: Any) -> Dict[str, Any]:
       pass
   
   # ✅ Good
   async def process(data: ProcessInput) -> ProcessOutput:
       pass
   ```

2. **Always use Pydantic models for structured data:**
   ```python
   # ❌ Bad
   return {"status": "ok", "count": 5}
   
   # ✅ Good
   class ProcessResult(BaseModel):
       status: str
       count: int
   return ProcessResult(status="ok", count=5)
   ```

3. **Use type hints consistently:**
   ```python
   # ✅ Good
   from typing import List, Optional
   
   async def get_items(
       limit: int = 10,
       offset: int = 0,
       filter_tags: Optional[List[int]] = None
   ) -> List[Item]:
       pass
   ```

### Pydantic AI Correct Usage

```python
from pydantic import BaseModel, Field
from pydantic_ai import Agent

class OutputModel(BaseModel):
    result: str = Field(description="The result")

# ✅ Correct initialization
agent = Agent(
    model="claude-3-5-sonnet-20241022",
    system_prompt="You are a helpful assistant",
    output_type=OutputModel,  # NOT result_type
)

# ✅ Correct result access
result = await agent.run("Hello")
output = result.output.result  # NOT result.data.result
```

### Directory Structure After Cleanup

```
context_bridge/
├── agents/
│   ├── __init__.py
│   └── context_generator.py  # ✅ Moved here
├── database/
│   ├── repositories/
│   │   ├── tag_repository.py
│   │   └── group_repository.py
│   └── models/
│       ├── tag_models.py
│       └── group_models.py
├── service/
│   ├── doc_manager.py
│   ├── search_service.py
│   ├── chunking_service.py
│   ├── embedding.py
│   └── reprocessing_service.py  # ✅ Moved here
└── core.py  # ✅ Simplified API

context_bridge_mcp/
├── server.py  # ✅ Only 2 tools
└── schemas.py  # ✅ Only 2 schemas
```

---

## Risk Mitigation

### Risk 1: Breaking Existing Code
- **Mitigation:** Comprehensive testing in Phase 6
- **Fallback:** Git revert if critical issues found

### Risk 2: Streamlit UI Issues
- **Mitigation:** Manual testing of all UI features
- **Fallback:** Keep old methods temporarily with deprecation warnings

### Risk 3: Test Failures
- **Mitigation:** Update tests incrementally with each phase
- **Fallback:** Skip optional tests if needed, focus on critical paths

### Risk 4: Import Errors
- **Mitigation:** Search entire codebase for imports before moving files
- **Fallback:** Use `grep` or IDE find to locate all import statements

---

## Post-Cleanup Actions

1. **Update Documentation:**
   - [ ] Update `README.md` with simplified API examples
   - [ ] Update `docs/guides/tags_system_guide.md`
   - [ ] Update `docs/guides/groups_system_guide.md`
   - [ ] Update API reference if exists

2. **Update CHANGELOG:**
   - [ ] Document removed methods
   - [ ] Document moved modules
   - [ ] Document breaking changes
   - [ ] Add migration guide for users

3. **Code Review:**
   - [ ] Review all changes for consistency
   - [ ] Verify no debug code left
   - [ ] Check for TODO comments
   - [ ] Ensure logging is appropriate

4. **Performance Check:**
   - [ ] Run benchmarks if available
   - [ ] Check for performance regressions
   - [ ] Verify database query efficiency

---

## Conclusion

This cleanup plan simplifies the v2 implementation by:
- Reducing MCP server from 11 tools to 2 tools (82% reduction)
- Removing 9 unnecessary methods from Core API
- Properly organizing context generation code
- Maintaining full functionality through Streamlit UI
- Ensuring type safety throughout

**Expected Outcome:** A cleaner, more maintainable codebase with clear separation of concerns between MCP server (minimal read-only), Core API (essential operations), and Streamlit UI (full management interface).
