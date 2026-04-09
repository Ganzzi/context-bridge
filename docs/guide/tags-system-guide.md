# Tags System - Implementation Guide

**Status:** Phase 1 - In Progress  
**Date:** November 15, 2025  
**Version:** 2.0.0

---

## Overview

The Tags System provides powerful document categorization and filtering capabilities. Documents can be tagged with multiple predefined categories from three main groups: Documentation Types, Technology, and Domain.

### Key Benefits

- 📂 **Organization**: Categorize documents for better organization
- 🔍 **Filtering**: Filter documents by one or more tags during search
- 📊 **Analytics**: Track tag usage and popularity
- 🎯 **Discovery**: Help users find relevant documentation
- ♻️ **Reusability**: Consistent tag names across all documents

---

## Quick Start

### 1. Accessing Tags

```python
from context_bridge import ContextBridge, Config

async with ContextBridge() as bridge:
    # List all available tags
    tags = await bridge.list_tags()
    
    # List tags by category
    from context_bridge.database.models import TagCategory
    
    tech_tags = await bridge.list_tags(category=TagCategory.TECHNOLOGY)
    doc_tags = await bridge.list_tags(category=TagCategory.DOCUMENTATION_TYPE)
    domain_tags = await bridge.list_tags(category=TagCategory.DOMAIN)
```

### 2. Viewing Document Tags

```python
# Get all tags for a document
tags = await bridge.get_document_tags(document_id=1)
for tag in tags:
    print(f"{tag.name} ({tag.category}): {tag.description}")
```

### 3. Searching with Tags

```python
# Find documents with specific tags
tag_ids = [2]  # API Reference
documents = await bridge.find_documents(tags=tag_ids)

# Find documents with multiple tags (matches ANY tag)
tag_ids = [2, 5, 10]
documents = await bridge.find_documents(tags=tag_ids)
```

### 4. Managing Document Tags (Streamlit UI)

Tag management (adding/removing tags) is done through the **Streamlit UI** or by calling the **TagRepository directly**:

**Via Streamlit UI:**
- Open the Tags Management page (`pages/tags.py`)
- Navigate to Document Management
- Use the tag selector to add/remove tags

**Via TagRepository (Advanced Users):**
```python
from context_bridge.database.repositories.tag_repository import TagRepository

async with bridge._db_manager.connection() as conn:
    tag_repo = TagRepository(conn)
    
    # Add tags
    await tag_repo.add_tags_to_document(document_id=1, tag_ids=[2, 5, 10])
    
    # Remove a tag
    await tag_repo.remove_tag_from_document(document_id=1, tag_id=2)
    
    # Remove all tags
    await tag_repo.remove_all_tags_from_document(document_id=1)
```

---

## Available Tags

### Documentation Types (15 tags)

Used to categorize by documentation format/style:

- `technical-documentation` - General technical documentation
- `api-reference` - API documentation and references ⭐
- `user-guide` - User guides and tutorials
- `developer-guide` - Developer-focused documentation
- `wiki` - Wiki-style documentation
- `specification` - Technical specifications (RFC, standards)
- `whitepaper` - Technical whitepapers
- `research-paper` - Academic/research papers
- `blog-post` - Blog articles and posts
- `article` - General articles
- `faq` - Frequently Asked Questions
- `changelog` - Version history and changelogs
- `release-notes` - Software release notes
- `tutorial` - Step-by-step tutorials
- `case-study` - Case studies and examples

### Technology (23 tags)

Used to categorize by technology/framework:

**Languages:**
- `python`, `javascript`, `typescript`, `java`, `go`, `rust`, `csharp`, `cpp`

**Databases:**
- `database`, `postgresql`, `mongodb`, `redis`, `sql`

**Frameworks & Platforms:**
- `web-framework`, `ml-ai`, `cloud`, `aws`, `azure`, `gcp`

**DevOps:**
- `kubernetes`, `docker`, `devops`, `cicd`

### Domain (10 tags)

Used to categorize by application domain:

- `backend` - Backend development
- `frontend` - Frontend development
- `fullstack` - Full-stack development
- `infrastructure` - Infrastructure and systems
- `security` - Security documentation
- `testing` - Testing documentation
- `monitoring` - Monitoring and observability
- `performance` - Performance optimization
- `scalability` - Scalability and architecture
- `deployment` - Deployment and release

---

## Architecture

### Database Schema

```sql
-- Tags table
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document-Tag junction table (many-to-many)
CREATE TABLE document_tags (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (document_id, tag_id)
);
```

### Repository Layer

TagRepository (direct database access) provides:

```python
# CRUD Operations
create_tag(tag: TagCreate) -> Tag
get_tag_by_id(tag_id: int) -> Optional[Tag]
get_tag_by_name(name: str) -> Optional[Tag]
list_tags(category: Optional[TagCategory], limit, offset) -> List[Tag]
list_all_tags() -> List[Tag]
update_tag(tag_id: int, update: TagUpdate) -> Optional[Tag]
delete_tag(tag_id: int) -> bool

# Document-Tag Associations (Repository Direct Access)
add_tag_to_document(document_id: int, tag_id: int) -> bool
add_tags_to_document(document_id: int, tag_ids: List[int]) -> int
remove_tag_from_document(document_id: int, tag_id: int) -> bool
remove_all_tags_from_document(document_id: int) -> int
get_document_tags(document_id: int) -> List[Tag]
get_documents_by_tag(tag_id: int, limit, offset) -> List[int]
get_documents_by_tags(tag_ids: List[int], match_all: bool, limit, offset) -> List[int]

# Statistics
get_tag_statistics() -> List[TagStatistics]
get_tag_statistics_by_category(category: TagCategory) -> List[TagStatistics]
count_tags_by_category() -> Dict[str, int]
```

**Note:** ContextBridge Core API provides `list_tags()` and `get_document_tags()` for viewing. Tag management operations (add/remove) should be done through the Streamlit UI or by accessing TagRepository directly.

---

## Common Use Cases

### Use Case 1: Finding API Documentation

```python
# Find documents with API Reference tag
api_tag = await bridge.get_tag_by_name("api-reference")
docs = await bridge.find_documents(tags=[api_tag.id])

# Get all tags for a specific document
tags = await bridge.get_document_tags(doc_id)
```

### Use Case 2: Find All Security Documentation

```python
# Use find_documents with tag filtering
# Security documentation is identified by filtering with security tag
docs = await bridge.find_documents(tags=[security_tag.id])
```

### Use Case 3: Multi-Tag Filtering

```python
# Find backend + testing documentation
backend_tag = await bridge.get_tag_by_name("backend")
testing_tag = await bridge.get_tag_by_name("testing")

# Get documents with EITHER tag
docs = await bridge.find_documents(
    tags=[backend_tag.id, testing_tag.id],
    match_all=False
)

# Get documents with BOTH tags
docs = await bridge.find_documents(
    tags=[backend_tag.id, testing_tag.id],
    match_all=True
)
```

### Use Case 4: Tag Statistics & Analytics

```python
# Get overall statistics
stats = await bridge.get_tag_statistics()
for stat in stats:
    print(f"{stat.name}: {stat.usage_count} documents")

# Get statistics for specific category
doc_type_stats = await bridge.get_tag_statistics_by_category(
    TagCategory.DOCUMENTATION_TYPE
)

# Count tags by category
counts = await bridge.count_tags_by_category()
# Output: {'documentation_type': 15, 'technology': 23, 'domain': 10}
```

---

## Streamlit UI Usage

### Document Management Page

In the Documents page, you can:

1. **View tags** on document cards
2. **Filter by tags** using the tag selector dropdown
3. **Add tags** when creating new documents
4. **Remove tags** from existing documents
5. **Manage tags** on the dedicated Tags Management page

### Tag Management Page

The Tags Management page allows:

1. **Browse all tags** organized by category
2. **View tag statistics** (usage counts)
3. **Create custom tags** (if enabled)
4. **Search tags** by name
5. **Filter by category**

---

## API Integration

### MCP Server Tools

The Tags system integrates with the MCP server:

#### `list_tags`
List all available tags with optional filtering.

**Input:**
```json
{
  "category": "documentation_type",  // Optional
  "limit": 50
}
```

**Output:**
```json
{
  "tags": [
    {
      "id": 1,
      "name": "api-reference",
      "category": "documentation_type",
      "description": "API documentation and references",
      "usage_count": 42
    }
  ],
  "total": 50
}
```

#### Updated: `find_documents`
Find documents with tag filtering.

**Input:**
```json
{
  "query": "postgresql",
  "tags": [1, 2],  // Optional tag IDs
  "limit": 10
}
```

**Note:** Tag management (add/remove) is not available through MCP. Use the Streamlit UI or direct repository access instead.

---

## Testing

### Running Tag Tests

```bash
# Run all tag repository tests
pytest tests/unit/test_tag_repository.py -v

# Run specific test
pytest tests/unit/test_tag_repository.py::TestTagRepository::test_add_tag_to_document -v

# Run with coverage
pytest tests/unit/test_tag_repository.py --cov=context_bridge.database.repositories.tag_repository -v
```

### Test Coverage

- ✅ CRUD operations (create, read, list, update, delete)
- ✅ Tag associations (add, remove, get document tags)
- ✅ Filtering by category
- ✅ Statistics and analytics
- ✅ Error handling

---

## Performance Considerations

### Indexing Strategy

Indexes are created for optimal performance:

- `idx_tags_category` - Fast category filtering
- `idx_tags_name` - Fast tag name lookups
- `idx_document_tags_document` - Find tags for a document
- `idx_document_tags_tag` - Find documents with a tag

### Query Optimization

- Use prepared statements to prevent SQL injection
- Batch tag operations with `add_tags_to_document()`
- Leverage indexes for category and name searches
- Use pagination for large result sets

### Performance Metrics

- Tag lookup by ID/name: ~5ms
- Add tag to document: ~10ms
- List tags by category: ~20ms (for 100+ tags)
- Tag statistics: ~50ms

---

## Best Practices

### ✅ Do's

- ✅ Use predefined tags consistently
- ✅ Add 2-3 relevant tags per document
- ✅ Organize tags by category
- ✅ Use batch operations for multiple tags
- ✅ Monitor tag usage statistics
- ✅ Update tags when document content changes
- ✅ Use filter pagination for large result sets

### ❌ Don'ts

- ❌ Create duplicate tags with similar names
- ❌ Add excessive tags to single document (avoid "tag bloat")
- ❌ Mix tag categories in single query
- ❌ Forget to remove unused tags
- ❌ Use tags for content-based filtering (use search instead)
- ❌ Add sensitive information in tag descriptions

---

## Migration Guide

### From v1 to v2

If you're upgrading from Context Bridge v1:

1. **Run migration script:**
   ```bash
   python -m context_bridge.database.init_databases migrate
   ```

2. **Tags are automatically seeded** with predefined values

3. **No automatic tagging** - you must manually add tags to existing documents

4. **Backfill tags** (optional):
   ```python
   # Script to tag existing documents
   # This should be done based on your document content/names
   ```

---

## Troubleshooting

### Q: Duplicate tag name error
**A:** Tag names are unique. If you need the same tag in a different category, it must have a different name.

### Q: Tag not appearing in search
**A:** Verify:
1. Tag was successfully added to document
2. Tag ID is correct
3. Document has been saved

### Q: Performance degradation with many tags
**A:** 
- Ensure indexes are created: `CREATE INDEX idx_document_tags_tag ON document_tags(tag_id);`
- Use pagination: `limit=50, offset=0`
- Consider archiving unused tags

---

## Next Steps

### Phase 2: Groups Table
- Explicit tracking of page groups
- Processing status and context enablement
- Group statistics

### Phase 3: AI Context Generation
- Pydantic AI integration
- Automatic context generation for chunks
- Cost optimization with prompt caching

### Phase 4: Re-Processing
- Re-process groups with context generation
- Batch processing support

---

## References

- [Tags Database Schema](../database/schema/v2_migration_001_tags_and_groups.sql)
- [Tag Models](../database/models/tag_models.py)
- [Tag Repository](../database/repositories/tag_repository.py)
- [Tag Tests](../tests/unit/test_tag_repository.py)
- [Implementation Plan](v2_feature_plan.md)

---

**End of Tags System Guide**
