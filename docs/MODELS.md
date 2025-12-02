# Context Bridge Data Models

This document describes the Pydantic data models used in the Context Bridge API. All models are type-safe and provide validation, serialization, and documentation.

## Overview

Context Bridge uses Pydantic models to ensure type safety and provide structured data. These models are used as:
- **Return types** from API methods
- **Input validation** for API parameters
- **Serialization** for JSON responses

## Module Organization

| Module | Description |
|--------|-------------|
| `context_bridge.database.models.group_models` | Group and processing-related models |
| `context_bridge.database.models.tag_models` | Tag system models |
| `context_bridge.service.doc_manager` | Document management result models |
| `context_bridge.service.search_service` | Search result models |

---

## Group Models

### GroupInfo

Basic information about a group, used in list operations.

**Import:**
```python
from context_bridge.database.models.group_models import GroupInfo
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | UUID of the group (as string) |
| `document_id` | `int` | Associated document ID |
| `name` | `Optional[str]` | Human-readable group name |
| `description` | `Optional[str]` | Group description |
| `context_enabled` | `bool` | Whether context generation is enabled |
| `context_model` | `Optional[str]` | Model used for context generation |
| `total_pages` | `int` | Number of pages in the group |
| `total_chunks` | `int` | Number of chunks in the group |
| `processing_status` | `str` | Current status (pending, processing, completed, failed, reprocessing) |
| `created_at` | `str` | Creation timestamp (ISO format) |
| `processed_at` | `Optional[str]` | Processing completion timestamp (ISO format) |

**Usage:**
```python
groups = await bridge.list_groups(document_id=123)
for group in groups:
    print(f"{group.name}: {group.processing_status}")
    print(f"  Pages: {group.total_pages}, Chunks: {group.total_chunks}")
```

**Conversion:**
```python
# Convert from Group model
group_info = GroupInfo.from_group(group)
```

---

### GroupStats

Detailed statistics for a specific group.

**Import:**
```python
from context_bridge.database.models.group_models import GroupStats
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `group_id` | `str` | UUID of the group (as string) |
| `document_id` | `int` | Associated document ID |
| `name` | `Optional[str]` | Group name |
| `description` | `Optional[str]` | Group description |
| `status` | `str` | Processing status |
| `context_enabled` | `bool` | Whether context generation is enabled |
| `context_model` | `Optional[str]` | Model used for context |
| `total_pages` | `int` | Number of pages |
| `total_chunks` | `int` | Number of chunks |
| `chunks_by_status` | `Dict[str, int]` | Breakdown of chunk counts by status |
| `total_content_size` | `int` | Total characters in all chunks |
| `created_at` | `str` | Creation timestamp (ISO format) |
| `processed_at` | `Optional[str]` | Processing completion timestamp |

**Usage:**
```python
from uuid import UUID

stats = await bridge.get_group_stats(UUID("550e8400-e29b-41d4-a716-446655440000"))
print(f"Group: {stats.name}")
print(f"Status: {stats.status}")
print(f"Content size: {stats.total_content_size:,} characters")
print(f"Chunks by status: {stats.chunks_by_status}")
```

---

### GroupCreationResult

Result returned when creating a new group (reserved for future use).

**Import:**
```python
from context_bridge.database.models.group_models import GroupCreationResult
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `group_id` | `str` | UUID of the created group |
| `document_id` | `int` | Associated document ID |
| `status` | `str` | Initial status (typically "processing") |
| `pages_selected` | `int` | Number of pages in the group |
| `estimated_chunks` | `int` | Estimated number of chunks |
| `context_enabled` | `bool` | Whether context generation is enabled |
| `context_model` | `Optional[str]` | Model for context generation |

---

### ReprocessingResult

Result returned when re-processing a group.

**Import:**
```python
from context_bridge.database.models.group_models import ReprocessingResult
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `status` | `str` | Result status: "success", "failed", or "partial" |
| `group_id` | `str` | UUID of the re-processed group |
| `chunks_deleted` | `int` | Number of chunks deleted before re-processing |
| `chunks_created` | `int` | Number of new chunks created |
| `contexts_generated` | `int` | Number of contexts generated (0 if disabled) |
| `context_enabled` | `bool` | Whether context generation was enabled |
| `context_model` | `Optional[str]` | Model used for context generation |
| `errors` | `int` | Number of errors during processing |

**Usage:**
```python
from uuid import UUID

result = await bridge.reprocess_group(
    group_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    context_enabled=True,
    context_model="anthropic:claude-3-5-sonnet-20241022"
)

if result.status == "success":
    print(f"✅ Created {result.chunks_created} chunks")
    print(f"   Generated {result.contexts_generated} contexts")
else:
    print(f"⚠️  {result.errors} errors occurred")
```

---

## Processing Models

### ChunkProcessingResult

Result returned when initiating chunk processing via `create_group()`.

**Import:**
```python
from context_bridge.service.doc_manager import ChunkProcessingResult
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `document_id` | `int` | Document being processed |
| `pages_processed` | `int` | Number of pages selected for processing |

**Usage:**
```python
result = await bridge.create_group(
    document_id=123,
    page_ids=[1, 2, 3, 4, 5]
)
print(f"Started processing {result.pages_processed} pages")
```

**Note:** Since processing runs asynchronously, this result only indicates that processing has been queued. Use `list_groups()` to monitor progress.

---

### CrawlAndStoreResult

Result returned when crawling documentation.

**Import:**
```python
from context_bridge.service.doc_manager import CrawlAndStoreResult
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `document_id` | `int` | ID of the created/updated document |
| `library_name` | `str` | Name of the library |
| `version` | `str` | Version string |
| `pages_crawled` | `int` | Number of pages crawled |
| `pages_stored` | `int` | Number of pages successfully stored |
| `errors` | `List[str]` | List of error messages |

**Usage:**
```python
result = await bridge.crawl_documentation(
    library_name="requests",
    version="2.31.0",
    base_url="https://docs.python-requests.org/en/v2.31.0/"
)
print(f"Crawled {result.pages_crawled} pages, stored {result.pages_stored}")
if result.errors:
    print(f"Errors: {result.errors}")
```

---

### PageInfo

Simplified page information for listing operations.

**Import:**
```python
from context_bridge.service.doc_manager import PageInfo
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Page ID |
| `url` | `str` | Original URL |
| `content_length` | `int` | Length of content in characters |
| `status` | `str` | Processing status |
| `crawled_at` | `datetime` | When the page was crawled |

**Usage:**
```python
pages = await bridge.list_pages(document_id=123)
for page in pages:
    print(f"Page {page.id}: {page.url}")
    print(f"  Status: {page.status}, Size: {page.content_length:,} chars")
```

---

## Search Models

### ContentSearchResult

Result returned from search operations.

**Import:**
```python
from context_bridge.service.search_service import ContentSearchResult
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `chunk_id` | `int` | ID of the matching chunk |
| `content` | `str` | Chunk content (may include context prefix) |
| `score` | `float` | Relevance score (0-1, higher is better) |
| `document_id` | `int` | Associated document ID |
| `page_id` | `Optional[int]` | Associated page ID |
| `group_id` | `Optional[UUID]` | Associated group ID |
| `metadata` | `Dict[str, Any]` | Additional metadata |

**Usage:**
```python
results = await bridge.search(
    query="authentication",
    document_id=123,
    limit=10
)
for result in results:
    print(f"Score: {result.score:.3f}")
    print(f"Content: {result.content[:200]}...")
```

---

## Tag Models

### Tag

Represents a tag that can be applied to documents.

**Import:**
```python
from context_bridge.database.models.tag_models import Tag
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Tag ID |
| `name` | `str` | Tag name |
| `category` | `TagCategory` | Category (language, framework, etc.) |
| `description` | `Optional[str]` | Tag description |
| `is_predefined` | `bool` | Whether this is a system-defined tag |
| `created_at` | `datetime` | Creation timestamp |

---

### TagCategory

Enum for tag categories.

**Import:**
```python
from context_bridge.database.models.tag_models import TagCategory
```

**Values:**
- `TagCategory.LANGUAGE` - Programming languages (Python, JavaScript, etc.)
- `TagCategory.FRAMEWORK` - Frameworks (Django, React, etc.)
- `TagCategory.TOPIC` - Topics (database, authentication, etc.)
- `TagCategory.CUSTOM` - User-defined tags

---

### TagCreate

Model for creating a new tag.

**Import:**
```python
from context_bridge.database.models.tag_models import TagCreate
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Tag name |
| `category` | `TagCategory` | Tag category |
| `description` | `Optional[str]` | Optional description |

**Usage:**
```python
from context_bridge.database.models.tag_models import TagCreate, TagCategory

new_tag = await bridge.create_tag(
    TagCreate(
        name="async-programming",
        category=TagCategory.TOPIC,
        description="Asynchronous programming patterns"
    )
)
```

---

### TagUpdate

Model for updating an existing tag.

**Import:**
```python
from context_bridge.database.models.tag_models import TagUpdate
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `Optional[str]` | New tag name |
| `description` | `Optional[str]` | New description |

---

### TagStatistics

Statistics about tag usage.

**Import:**
```python
from context_bridge.database.models.tag_models import TagStatistics
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `tag_id` | `int` | Tag ID |
| `name` | `str` | Tag name |
| `category` | `TagCategory` | Tag category |
| `document_count` | `int` | Number of documents with this tag |

---

## Document Models

### Document

Represents a documentation source.

**Import:**
```python
from context_bridge.database.repositories.document_repository import Document
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Document ID |
| `library_name` | `str` | Name of the library |
| `version` | `str` | Version string |
| `base_url` | `str` | Base URL of the documentation |
| `created_at` | `datetime` | When the document was created |
| `updated_at` | `Optional[datetime]` | Last update timestamp |

---

## Best Practices

### Type Hints

Always use proper type hints when working with Context Bridge models:

```python
from typing import List
from context_bridge.database.models.group_models import GroupInfo

async def process_groups(groups: List[GroupInfo]) -> None:
    for group in groups:
        if group.processing_status == "completed":
            print(f"Ready: {group.name}")
```

### Model Serialization

All models support JSON serialization via Pydantic:

```python
# Convert to dictionary
group_dict = group_info.model_dump()

# Convert to JSON string
group_json = group_info.model_dump_json()

# Create from dictionary
group_info = GroupInfo.model_validate(data_dict)
```

### Error Handling

Models provide validation errors with clear messages:

```python
try:
    result = ReprocessingResult(
        status="invalid_status",  # Will raise validation error
        group_id="not-a-uuid",
        # ... other fields
    )
except ValidationError as e:
    print(f"Validation failed: {e}")
```

---

## See Also

- [API Reference](API.md) - Complete API documentation
- [Architecture](ARCHITECTURE.md) - System architecture overview
