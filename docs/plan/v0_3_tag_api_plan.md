# Version 0.3 - Tag API Enhancement Plan

**Status:** In Development
**Start Date:** December 2, 2025
**Target Release:** December 9, 2025
**Version:** 0.3.0

---

## 📋 Executive Summary

Version 0.3 completes the **Tag API implementation** by exposing public methods in the `ContextBridge` class for tag management. Currently, tag assignment is only available in the Streamlit UI through private repository access. This plan adds symmetric tag management capabilities to the Python SDK.

### Key Deliverables

- ✅ 5 new public methods in ContextBridge
- ✅ Comprehensive unit tests (15+ test cases)
- ✅ Updated API documentation with examples
- ✅ Example workflow script
- ✅ No breaking changes (additive only)

---

## 🎯 Problem Statement

### Current State
- ContextBridge exposes only 2 tag methods: `list_tags()` and `get_document_tags()`
- TagRepository has 15+ methods but they're private (not exposed in public API)
- Users cannot assign tags when using the Python SDK directly
- Tag management only works in Streamlit UI
- Gap in document lifecycle: Crawl → ✓ Organize → ✗ **Tag** → Chunk → Search

### Use Case
```python
# Users want to do this:
async with ContextBridge() as bridge:
    result = await bridge.crawl_documentation(...)
    
    # MISSING: Assign tags after crawling
    # bridge.add_tags_to_document(result.document_id, [1, 2, 3])
    
    # MISSING: Create custom tags
    # new_tag = await bridge.create_tag("custom", TagCategory.custom)
```

---

## 📐 Solution Design

### New Public Methods

All methods will follow existing ContextBridge patterns:
- Initialization checks via `_check_initialized()`
- Async/await support
- Proper error handling and logging
- Type hints and comprehensive docstrings
- Pydantic models for type safety

#### Method 1: `add_tag_to_document`
```python
async def add_tag_to_document(self, document_id: int, tag_id: int) -> bool:
    """
    Add a tag to a document.
    
    Args:
        document_id: Document ID
        tag_id: Tag ID to add
        
    Returns:
        True if tag was added, False if already exists
        
    Raises:
        RuntimeError: If ContextBridge not initialized
        ValueError: If document or tag doesn't exist
    """
```

**Use Case:** Single tag assignment
```python
added = await bridge.add_tag_to_document(doc_id=42, tag_id=5)
```

---

#### Method 2: `add_tags_to_document`
```python
async def add_tags_to_document(self, document_id: int, tag_ids: List[int]) -> int:
    """
    Add multiple tags to a document.
    
    Args:
        document_id: Document ID
        tag_ids: List of tag IDs to add
        
    Returns:
        Number of tags successfully added
        
    Raises:
        RuntimeError: If ContextBridge not initialized
    """
```

**Use Case:** Bulk tag assignment after crawling
```python
# Assign 3 tags after crawling
count = await bridge.add_tags_to_document(doc_id=42, tag_ids=[1, 5, 12])
print(f"✅ Added {count} tags")
```

---

#### Method 3: `remove_tag_from_document`
```python
async def remove_tag_from_document(self, document_id: int, tag_id: int) -> bool:
    """
    Remove a tag from a document.
    
    Args:
        document_id: Document ID
        tag_id: Tag ID to remove
        
    Returns:
        True if tag was removed, False if it wasn't assigned
        
    Raises:
        RuntimeError: If ContextBridge not initialized
    """
```

**Use Case:** Unassign a tag
```python
removed = await bridge.remove_tag_from_document(doc_id=42, tag_id=5)
```

---

#### Method 4: `remove_all_tags_from_document`
```python
async def remove_all_tags_from_document(self, document_id: int) -> int:
    """
    Remove all tags from a document.
    
    Args:
        document_id: Document ID
        
    Returns:
        Number of tags removed
        
    Raises:
        RuntimeError: If ContextBridge not initialized
    """
```

**Use Case:** Reset document tags
```python
removed = await bridge.remove_all_tags_from_document(doc_id=42)
print(f"Removed {removed} tags")
```

---

#### Method 5: `create_tag`
```python
async def create_tag(
    self, 
    name: str, 
    category: TagCategory, 
    description: Optional[str] = None
) -> Tag:
    """
    Create a new custom tag.
    
    Args:
        name: Tag name (must be unique)
        category: TagCategory enum value
        description: Optional tag description
        
    Returns:
        Created Tag object
        
    Raises:
        RuntimeError: If ContextBridge not initialized
        ValueError: If tag name already exists
    """
```

**Use Case:** Create custom tags for domain-specific categorization
```python
from context_bridge.database.models.tag_models import TagCategory

new_tag = await bridge.create_tag(
    name="async-io",
    category=TagCategory.technology,
    description="Async I/O and concurrency concepts"
)
print(f"✅ Created tag: {new_tag.name} (ID: {new_tag.id})")
```

---

### Updated Exports

Update `context_bridge/__init__.py` to export tag models:

```python
from .config import Config, get_config, set_config
from .core import ContextBridge
from .database.models.tag_models import Tag, TagCategory, TagCreate, TagUpdate

__all__ = [
    "Config", 
    "get_config", 
    "set_config", 
    "ContextBridge",
    "Tag",
    "TagCategory",
    "TagCreate",
    "TagUpdate",
]
```

---

## 📝 Implementation Roadmap

### Phase 1: Core Implementation (1-2 hours)

**File: `context_bridge/core.py`**

1. Add 5 new methods after `get_document_tags()` (around line 970)
2. Keep all existing documentation
3. Follow existing code patterns:
   - Use `self._check_initialized()`
   - Delegate to `self._tag_repository`
   - Add proper error handling
   - Include comprehensive docstrings

**Implementation Details:**
- Location: Add new "Tag Management" section after existing "Tag Operations"
- Inherit error handling from TagRepository
- No database schema changes required
- No configuration changes required

### Phase 2: Export Updates (5 minutes)

**File: `context_bridge/__init__.py`**

1. Import Tag models
2. Add to `__all__` export list
3. Keep version and other exports unchanged

### Phase 3: Testing (2-3 hours)

**File: `tests/unit/test_core_tag_methods.py` (NEW)**

Create comprehensive unit tests:
- `test_add_tag_to_document_success` - Tag added
- `test_add_tag_to_document_already_exists` - Idempotent
- `test_add_tags_to_document_multiple` - Bulk add
- `test_add_tags_to_document_empty_list` - Handle empty list
- `test_remove_tag_from_document_success` - Tag removed
- `test_remove_tag_from_document_not_found` - Not assigned
- `test_remove_all_tags_from_document` - Clear all tags
- `test_create_tag_success` - Custom tag creation
- `test_create_tag_duplicate_name` - Reject duplicates
- `test_add_tag_uninitialized` - Check initialization
- `test_get_document_tags_after_add` - Verify assignment

**Test Patterns:**
- Mock `_tag_repository` for unit isolation
- Use `AsyncMock` for async methods
- Test success and error cases
- Verify initialization checks

### Phase 4: Documentation (1 hour)

**File: `docs/API.md`**

Add new section in Tag Operations:

```markdown
### Tag Management

#### `add_tag_to_document`
```python
async def add_tag_to_document(document_id: int, tag_id: int) -> bool
```

#### `add_tags_to_document`
#### `remove_tag_from_document`
#### `remove_all_tags_from_document`
#### `create_tag`
```

Include:
- Method signatures
- Parameter descriptions
- Return values
- Error cases
- Usage examples

### Phase 5: Examples (30 minutes)

**File: `examples/04_tags_workflow.py` (NEW)**

Complete workflow example:
```python
"""
Example: Complete Document Lifecycle with Tag Management

Demonstrates:
1. Crawling documentation
2. Creating custom tags
3. Assigning tags to documents
4. Using tags for organization
5. Searching with tag context
"""

import asyncio
from context_bridge import ContextBridge, TagCategory

async def main():
    async with ContextBridge() as bridge:
        # Step 1: Crawl documentation
        result = await bridge.crawl_documentation(...)
        
        # Step 2: Create custom tags if needed
        performance_tag = await bridge.create_tag(
            name="performance-optimization",
            category=TagCategory.technology,
            description="Content about performance tuning and optimization"
        )
        
        # Step 3: Assign tags
        await bridge.add_tags_to_document(
            result.document_id,
            [performance_tag.id, 1, 5, 12]  # Mix of custom and predefined
        )
        
        # Step 4: Verify tags
        tags = await bridge.get_document_tags(result.document_id)
        print(f"Document tagged with: {', '.join([t.name for t in tags])}")
        
        # Step 5: Create and process group
        pages = await bridge.list_pages(result.document_id)
        group = await bridge.create_group(result.document_id, [p.id for p in pages])
        
        # Step 6: Search (results benefit from tag metadata)
        results = await bridge.search(...)

if __name__ == "__main__":
    asyncio.run(main())
```

### Phase 6: Validation (1 hour)

**Testing Steps:**
1. Run existing unit tests: `pytest tests/unit/test_core.py -v`
2. Run new tag tests: `pytest tests/unit/test_core_tag_methods.py -v`
3. Run all tests: `pytest tests/unit/ -v`
4. Check coverage: `pytest --cov=context_bridge tests/unit/`
5. Verify no regressions in integration tests

---

## 🔍 Quality Assurance

### Code Review Checklist

- [ ] All 5 methods implement `_check_initialized()`
- [ ] All methods have comprehensive docstrings
- [ ] All methods delegate to `_tag_repository`
- [ ] Error handling is consistent with existing code
- [ ] Type hints are correct (List[int], Optional, etc.)
- [ ] No breaking changes to existing API
- [ ] Logging is appropriate

### Testing Checklist

- [ ] All 15+ new tests pass
- [ ] No regressions in existing tests
- [ ] 100% code coverage for new methods
- [ ] Mock patterns match existing tests
- [ ] Async handling is correct

### Documentation Checklist

- [ ] API.md updated with all 5 methods
- [ ] Examples provided for each method
- [ ] Docstrings are clear and complete
- [ ] Example script runs without errors

---

## 📊 Impact Analysis

### Non-Breaking Changes

- ✅ Additive only (no modifications to existing methods)
- ✅ No database schema changes
- ✅ No configuration changes
- ✅ No breaking changes to existing API
- ✅ No performance impact

### Benefits

1. **Complete Document Lifecycle:** Crawl → Tag → Organize → Chunk → Search
2. **API Symmetry:** SDK now matches Streamlit UI capabilities
3. **Type Safety:** All tag operations use Pydantic models
4. **User Flexibility:** Programmatic tag management and custom tags
5. **Better Organization:** Users can categorize docs at scale

---

## 🚀 Release Plan

### v0.3.0 Release Contents

```markdown
## v0.3.0 - Tag Management API

**Release Date:** December 9, 2025

### New Features
- 5 new public tag management methods in ContextBridge
  - `add_tag_to_document()` - Assign single tag
  - `add_tags_to_document()` - Bulk tag assignment
  - `remove_tag_from_document()` - Unassign tag
  - `remove_all_tags_from_document()` - Clear tags
  - `create_tag()` - Create custom tags
- Updated exports for Tag models
- Comprehensive example workflow

### Improvements
- Complete document lifecycle: Crawl → Tag → Organize → Chunk → Search
- Full API symmetry between SDK and Streamlit UI
- Better type safety with Pydantic models

### Documentation
- Updated API reference with tag operations
- New example: Complete tag workflow
- Docstrings for all new methods

### Breaking Changes
- None

### Test Coverage
- 15+ new unit tests (100% coverage)
- All existing tests passing (349/369)
```

---

## 📅 Timeline

| Phase | Task | Duration | Target Date |
|-------|------|----------|-------------|
| 1 | Core Implementation | 1-2h | Dec 2 |
| 2 | Export Updates | 5min | Dec 2 |
| 3 | Unit Tests | 2-3h | Dec 3 |
| 4 | Documentation | 1h | Dec 3 |
| 5 | Examples | 30min | Dec 4 |
| 6 | Validation & QA | 1h | Dec 4 |
| 7 | Release Prep | 30min | Dec 5 |
| **Total** | | **6-8h** | **Dec 9** |

---

## 📚 Reference: Related Issues & Discussions

### Why This Matters

From GitHub Issues and User Feedback:
- Users want to programmatically assign tags when crawling
- Tag assignment currently requires UI or private API access
- Missing capability creates incomplete workflow
- Tag-based filtering would improve document management

### Related Components

- **Core API:** `context_bridge/core.py` (main file)
- **Data Layer:** `context_bridge/database/repositories/tag_repository.py` (17 methods)
- **Models:** `context_bridge/database/models/tag_models.py` (5 models)
- **UI:** `streamlit_app/pages/tags.py` (for reference)
- **Tests:** `tests/unit/test_tag_repository.py` (existing tests)

---

## ✅ Success Criteria

All of the following must be true for v0.3.0 release:

- [ ] All 5 new methods implemented in ContextBridge
- [ ] All 15+ new unit tests pass (100% success)
- [ ] No regressions in existing tests (349+ tests still pass)
- [ ] API documentation updated with examples
- [ ] Example workflow script created and working
- [ ] Tag models exported in `__init__.py`
- [ ] Code follows existing patterns and style
- [ ] No breaking changes to public API
- [ ] Memory updated with completion status

---

## 🎓 Appendix: Method Signatures

### Complete Method Signatures

```python
# Method 1: Add single tag
async def add_tag_to_document(self, document_id: int, tag_id: int) -> bool

# Method 2: Add multiple tags
async def add_tags_to_document(self, document_id: int, tag_ids: List[int]) -> int

# Method 3: Remove single tag
async def remove_tag_from_document(self, document_id: int, tag_id: int) -> bool

# Method 4: Remove all tags
async def remove_all_tags_from_document(self, document_id: int) -> int

# Method 5: Create custom tag
async def create_tag(
    self, 
    name: str, 
    category: TagCategory, 
    description: Optional[str] = None
) -> Tag
```

---

**Document Version:** 1.0  
**Last Updated:** December 2, 2025  
**Status:** In Development
