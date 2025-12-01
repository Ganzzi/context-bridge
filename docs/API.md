# Context Bridge API Reference

This document provides a comprehensive reference for the `ContextBridge` class, the main entry point for the Context Bridge library.

## Table of Contents

- [Initialization](#initialization)
- [Document Operations](#document-operations)
- [Page Operations](#page-operations)
- [Group Management](#group-management)
- [Search Operations](#search-operations)
- [Tag Operations](#tag-operations)

---

## Initialization

### `ContextBridge`

The main class for interacting with the Context Bridge system.

```python
class ContextBridge(config: Optional[Config] = None)
```

**Arguments:**
- `config` (Optional[Config]): Configuration object. If not provided, loads from environment variables and `.env` file.

**Example:**
```python
from context_bridge import ContextBridge

async with ContextBridge() as bridge:
    # Use bridge methods
    pass
```

### `initialize`

Initialize database connections and services. Must be called before using other methods if not using the context manager.

```python
async def initialize() -> None
```

### `close`

Close all connections and cleanup resources.

```python
async def close() -> None
```

### `is_initialized`

Check if the bridge is initialized.

```python
def is_initialized() -> bool
```

### `get_config`

Get the current configuration.

```python
def get_config() -> Config
```

### `health_check`

Perform a health check of all services.

```python
async def health_check() -> Dict[str, Any]
```

**Returns:**
- Dictionary with health status of `database`, `embedding_service`, and other services.

---

## Document Operations

### `crawl_documentation`

Crawl and store documentation from a URL.

```python
async def crawl_documentation(
    name: str,
    version: str,
    source_url: str,
    description: Optional[str] = None,
    max_depth: Optional[int] = None,
    additional_urls: Optional[List[str]] = None
) -> CrawlAndStoreResult
```

**Arguments:**
- `name`: Document name (e.g., "Python Docs")
- `version`: Document version (e.g., "3.11")
- `source_url`: Primary URL to crawl
- `description`: Optional description
- `max_depth`: Optional crawl depth override (1-10)
- `additional_urls`: Optional list of additional URLs to crawl

**Returns:**
- `CrawlAndStoreResult` object containing summary of the operation.

### `find_documents`

Find documents by query or filters.

```python
async def find_documents(
    query: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    name: Optional[str] = None,
    version: Optional[str] = None,
    id: Optional[int] = None,
    tags: Optional[List[int]] = None,
    tag_match_all: bool = False
) -> List[Document]
```

**Arguments:**
- `query`: Search query string (searches name, description, metadata)
- `limit`: Max results (default: 10)
- `offset`: Pagination offset
- `name`: Exact name filter
- `version`: Exact version filter
- `id`: Exact ID filter
- `tags`: List of tag IDs to filter by
- `tag_match_all`: If True, requires ALL tags; if False, requires ANY tag.

**Returns:**
- List of `Document` objects.

### `list_documents`

List all documents with pagination.

```python
async def list_documents(limit: int = 100, offset: int = 0) -> List[Document]
```

### `get_document`

Get a specific document by name and version.

```python
async def get_document(name: str, version: str) -> Optional[Document]
```

### `delete_document`

Delete a document and all related data (pages, chunks).

```python
async def delete_document(document_id: int) -> bool
```

---

## Page Operations

### `list_pages`

List pages for a document.

```python
async def list_pages(
    document_id: int,
    status: Optional[str] = None,
    offset: int = 0,
    limit: int = 100
) -> List[PageInfo]
```

**Arguments:**
- `document_id`: Document ID
- `status`: Filter by status ('pending', 'chunked', 'deleted')
- `offset`: Pagination offset
- `limit`: Max results

### `delete_page`

Soft delete a page.

```python
async def delete_page(page_id: int) -> bool
```

---

## Group Management

### `list_groups`

List groups for a document or all groups.

```python
async def list_groups(
    document_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]
```

**Arguments:**
- `document_id`: Optional document ID filter. If not provided, lists all groups across all documents
- `limit`: Maximum number of results to return (default: 100)
- `offset`: Pagination offset (default: 0)

**Returns:**
- List of dictionaries containing group metadata

### `create_group`

**NEW in v0.2** - Process pages for chunking and embedding, optionally with AI context generation.

```python
async def create_group(
    document_id: int,
    page_ids: List[int],
    name: Optional[str] = None,
    chunk_size: Optional[int] = None,
    context_enabled: bool = False,
    context_model: Optional[str] = None
) -> Dict[str, Any]
```

**Arguments:**
- `document_id`: Document ID
- `page_ids`: List of page IDs to process
- `name`: Optional human-readable name for the group
- `chunk_size`: Optional chunk size override
- `context_enabled`: Enable AI context generation for chunks
- `context_model`: Model to use for context generation

**Returns:**
- Dictionary with processing result

### `get_group_stats`

**NEW in v0.2** - Get detailed statistics for a specific group.

```python
async def get_group_stats(group_id: UUID) -> Dict[str, Any]
```

**Arguments:**
- `group_id`: UUID of the group

**Returns:**
- Dictionary with comprehensive group information

### `list_reprocessable_groups`

**NEW in v0.2** - List groups eligible for re-processing with new context settings.

```python
async def list_reprocessable_groups(
    document_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]
```

**Use Case:** Identifies groups processed without context generation that are eligible for re-processing.

### `reprocess_group`

**NEW in v0.2** - Re-process a completed group with new settings.

```python
async def reprocess_group(
    group_id: UUID,
    context_enabled: bool = True,
    context_model: Optional[str] = None
) -> Dict[str, Any]
```

**Arguments:**
- `group_id`: UUID of the group to re-process
- `context_enabled`: Enable context generation
- `context_model`: Model to use for context generation

**Returns:**
- Dictionary with re-processing result

---

## Search Operations

### `search`

Search within document content using hybrid search (Vector + BM25).

```python
async def search(
    query: str,
    document_id: int,
    limit: int = 10,
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None
) -> List[ContentSearchResult]
```

**Arguments:**
- `query`: Search query
- `document_id`: Document ID
- `limit`: Max results
- `vector_weight`: Weight for vector search (0-1)
- `bm25_weight`: Weight for BM25 search (0-1)

---

## Tag Operations

### `list_tags`

List all available tags.

```python
async def list_tags(category: Optional[TagCategory] = None) -> List[Tag]
```

### `get_document_tags`

Get all tags for a document.

```python
async def get_document_tags(document_id: int) -> List[Tag]
```
