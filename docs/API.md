# Context Bridge API Reference

This document provides a comprehensive reference for the `ContextBridge` class, the main entry point for the Context Bridge library.

> **See also:** [Data Models Reference](MODELS.md) for detailed documentation of Pydantic models used in this API.

## Table of Contents

- [Initialization](#initialization)
- [Configuration](#configuration)
- [Document Operations](#document-operations)
- [Page Operations](#page-operations)
- [Group Management](#group-management)
- [Search Operations](#search-operations)
- [Tag Operations](#tag-operations)
- [Data Models](#data-models)

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

**Raises:**
- `RuntimeError`: If ContextBridge is already initialized
- `ConnectionError`: If database connection fails or database is unreachable
- `Exception`: If service initialization fails (embedding service, etc.)

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

## Configuration

### `Config`

Configuration class for Context Bridge. Supports three initialization patterns.

```python
from context_bridge import Config

config = Config(
    postgres_host="localhost",
    postgres_password="secure_password",
    embedding_model="nomic-embed-text:latest"
)
```

#### PostgreSQL Settings

| Parameter | Type | Default | Env Variable | Description |
|-----------|------|---------|--------------|-------------|
| `postgres_host` | `str` | `"localhost"` | `POSTGRES_HOST` | Database hostname |
| `postgres_port` | `int` | `5432` | `POSTGRES_PORT` | Database port |
| `postgres_user` | `str` | `"postgres"` | `POSTGRES_USER` | Database username |
| `postgres_password` | `str` | `""` | `POSTGRES_PASSWORD` | Database password (min 8 chars in production) |
| `postgres_db` | `str` | `"context_bridge"` | `POSTGRES_DB` | Database name |
| `postgres_max_pool_size` | `int` | `10` | `DB_POOL_MAX` | Connection pool size |

#### Embedding Settings

| Parameter | Type | Default | Env Variable | Description |
|-----------|------|---------|--------------|-------------|
| `ollama_base_url` | `str` | `"http://localhost:11434"` | `OLLAMA_BASE_URL` | Ollama API base URL |
| `embedding_model` | `str` | `"nomic-embed-text:latest"` | `EMBEDDING_MODEL` | Embedding model name |
| `vector_dimension` | `int` | `768` | `VECTOR_DIMENSION` | Embedding vector dimension |

#### Search Settings

| Parameter | Type | Default | Env Variable | Description |
|-----------|------|---------|--------------|-------------|
| `similarity_threshold` | `float` | `0.7` | `SIMILARITY_THRESHOLD` | Default similarity threshold (0-1) |
| `bm25_weight` | `float` | `0.3` | `BM25_WEIGHT` | BM25 weight in hybrid search (0-1) |
| `vector_weight` | `float` | `0.7` | `VECTOR_WEIGHT` | Vector weight in hybrid search (0-1) |

#### Chunking Settings

| Parameter | Type | Default | Env Variable | Description |
|-----------|------|---------|--------------|-------------|
| `chunk_size` | `int` | `2000` | `CHUNK_SIZE` | Default chunk size (characters) |
| `min_combined_content_size` | `int` | `100` | `MIN_COMBINED_CONTENT_SIZE` | Minimum content size for processing |
| `max_combined_content_size` | `int` | `3500000` | `MAX_COMBINED_CONTENT_SIZE` | Maximum content size for processing |

#### Crawling Settings

| Parameter | Type | Default | Env Variable | Description |
|-----------|------|---------|--------------|-------------|
| `crawl_max_depth` | `int` | `3` | `CRAWL_MAX_DEPTH` | Maximum crawl depth (1-10) |
| `crawl_max_concurrent` | `int` | `10` | `CRAWL_MAX_CONCURRENT` | Max concurrent crawl operations |

#### AI Context Generation Settings

| Parameter | Type | Default | Env Variable | Description |
|-----------|------|---------|--------------|-------------|
| `context_agent_model` | `str` | `"anthropic:claude-3-5-sonnet-20241022"` | `CONTEXT_AGENT_MODEL` | Model for context generation |
| `context_agent_temperature` | `float` | `0.3` | `CONTEXT_AGENT_TEMPERATURE` | Temperature for generation (0-1) |
| `context_agent_max_tokens` | `int` | `500` | `CONTEXT_AGENT_MAX_TOKENS` | Max tokens for context response |
| `context_batch_size` | `int` | `10` | `CONTEXT_BATCH_SIZE` | Parallel chunk processing batch size |

#### API Keys

| Parameter | Type | Default | Env Variable | Description |
|-----------|------|---------|--------------|-------------|
| `anthropic_api_key` | `Optional[str]` | `None` | `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `openai_api_key` | `Optional[str]` | `None` | `OPENAI_API_KEY` | OpenAI API key for GPT |
| `google_api_key` | `Optional[str]` | `None` | `GOOGLE_API_KEY` | Google API key for Gemini |
| `grok_api_key` | `Optional[str]` | `None` | `GROK_API_KEY` | Grok API key |

#### Configuration Patterns

**Pattern 1: Direct Python (Recommended for library usage)**
```python
from context_bridge import ContextBridge, Config

config = Config(
    postgres_host="localhost",
    postgres_password="secure_password",
    embedding_model="nomic-embed-text:latest"
)

async with ContextBridge(config=config) as bridge:
    result = await bridge.crawl_documentation(...)
```

**Pattern 2: Environment Variables (Recommended for Docker/Kubernetes)**
```bash
export POSTGRES_HOST=postgres
export POSTGRES_PASSWORD=secure_pass
export EMBEDDING_MODEL=nomic-embed-text:latest
```
```python
from context_bridge import ContextBridge

async with ContextBridge() as bridge:
    result = await bridge.crawl_documentation(...)
```

**Pattern 3: .env File (Convenient for local development)**
```bash
# .env (git-ignored)
POSTGRES_HOST=localhost
POSTGRES_PASSWORD=devpass
EMBEDDING_MODEL=nomic-embed-text:latest
```
```python
# Automatically loaded if python-dotenv is available
from context_bridge import ContextBridge

async with ContextBridge() as bridge:
    result = await bridge.crawl_documentation(...)
```

**Raises:**
- `ValidationError`: If `postgres_password` is provided but less than 8 characters

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

**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If `source_url` is invalid or `max_depth` is outside 1-10 range
- `ConnectionError`: If target URL is unreachable or crawling fails

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

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

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

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

### `delete_document`

Delete a document and all related data (pages, chunks).

```python
async def delete_document(document_id: int) -> bool
```

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

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

**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If `status` is not one of 'pending', 'chunked', 'deleted'

### `delete_page`

Soft delete a page.

```python
async def delete_page(page_id: int) -> bool
```

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

---

## Group Management

### `list_groups`

List groups for a document or all groups.

```python
async def list_groups(
    document_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[GroupInfo]
```

**Arguments:**
- `document_id`: Optional document ID filter. If not provided, lists all groups across all documents
- `limit`: Maximum number of results to return (default: 100)
- `offset`: Pagination offset (default: 0)

**Returns:**
- List of `GroupInfo` objects containing group metadata

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

### `create_group`

**NEW in v0.2** - Process pages for chunking and embedding, optionally with AI context generation.

```python
async def create_group(
    document_id: int,
    page_ids: List[int],
    chunk_size: Optional[int] = None,
    context_enabled: bool = False,
    context_model: Optional[str] = None
) -> ChunkProcessingResult
```

**Arguments:**
- `document_id`: Document ID
- `page_ids`: List of page IDs to process
- `chunk_size`: Optional chunk size override
- `context_enabled`: Enable AI context generation for chunks (not yet forwarded - use `reprocess_group`)
- `context_model`: Model to use for context generation (not yet forwarded - use `reprocess_group`)

**Returns:**
- `ChunkProcessingResult` with processing initiation details

**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If pages are from different documents, page IDs are invalid, or content size exceeds limits
- `EmbeddingConnectionError`: If embedding service (Ollama) is unreachable

### `get_group_stats`

**NEW in v0.2** - Get detailed statistics for a specific group.

```python
async def get_group_stats(group_id: UUID) -> GroupStats
```

**Arguments:**
- `group_id`: UUID of the group

**Returns:**
- `GroupStats` object with comprehensive group information including chunk statistics

**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If group not found

### `list_reprocessable_groups`

**NEW in v0.2** - List groups eligible for re-processing with new context settings.

```python
async def list_reprocessable_groups(
    document_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[GroupInfo]
```

**Use Case:** Identifies groups processed without context generation that are eligible for re-processing.

**Returns:**
- List of `GroupInfo` objects for reprocessable groups

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

### `reprocess_group`

**NEW in v0.2** - Re-process a completed group with new settings.

```python
async def reprocess_group(
    group_id: UUID,
    context_enabled: bool = True,
    context_model: Optional[str] = None
) -> ReprocessingResult
```

**Arguments:**
- `group_id`: UUID of the group to re-process
- `context_enabled`: Enable context generation
- `context_model`: Model to use for context generation

**Returns:**
- `ReprocessingResult` with re-processing operation results

**Raises:**
- `RuntimeError`: If ContextBridge not initialized, or if reprocessing fails critically
- `ValueError`: If group not found or cannot be reprocessed (wrong status)
- `EmbeddingConnectionError`: If embedding service (Ollama) is unreachable

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

**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `EmbeddingConnectionError`: If embedding service is unreachable (for query embedding)

---

## Tag Operations

### `list_tags`

List all available tags, optionally filtered by category.

```python
async def list_tags(category: Optional[TagCategory] = None) -> List[Tag]
```

**Arguments:**
- `category`: Optional TagCategory to filter by (e.g., `TagCategory.technology`)

**Returns:**
- List of `Tag` objects

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

**Example:**
```python
# List all tags
all_tags = await bridge.list_tags()

# List only technology tags
tech_tags = await bridge.list_tags(category=TagCategory.technology)
```

---

### `get_document_tags`

Get all tags for a document.

```python
async def get_document_tags(document_id: int) -> List[Tag]
```

**Arguments:**
- `document_id`: Document ID

**Returns:**
- List of `Tag` objects associated with the document

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

**Example:**
```python
tags = await bridge.get_document_tags(document_id=42)
print(f"Document has {len(tags)} tags: {', '.join([t.name for t in tags])}")
```

---

### `add_tag_to_document`

Add a single tag to a document.

```python
async def add_tag_to_document(document_id: int, tag_id: int) -> bool
```

**Arguments:**
- `document_id`: Document ID
- `tag_id`: Tag ID to add

**Returns:**
- `True` if tag was added, `False` if the relationship already exists (idempotent)

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

**Example:**
```python
# Add tag with ID 5 to document 42
added = await bridge.add_tag_to_document(document_id=42, tag_id=5)
if added:
    print("✅ Tag added")
else:
    print("Tag was already assigned")
```

---

### `add_tags_to_document`

Add multiple tags to a document.

```python
async def add_tags_to_document(document_id: int, tag_ids: List[int]) -> int
```

**Arguments:**
- `document_id`: Document ID
- `tag_ids`: List of tag IDs to add

**Returns:**
- Number of tags successfully added

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

**Example:**
```python
# Add multiple tags after crawling
count = await bridge.add_tags_to_document(
    document_id=42, 
    tag_ids=[1, 5, 12, 15]
)
print(f"✅ Added {count} tags to document")
```

---

### `remove_tag_from_document`

Remove a single tag from a document.

```python
async def remove_tag_from_document(document_id: int, tag_id: int) -> bool
```

**Arguments:**
- `document_id`: Document ID
- `tag_id`: Tag ID to remove

**Returns:**
- `True` if tag was removed, `False` if it wasn't assigned

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

**Example:**
```python
# Remove tag from document
removed = await bridge.remove_tag_from_document(document_id=42, tag_id=5)
if removed:
    print("✅ Tag removed")
else:
    print("Tag was not assigned")
```

---

### `remove_all_tags_from_document`

Remove all tags from a document.

```python
async def remove_all_tags_from_document(document_id: int) -> int
```

**Arguments:**
- `document_id`: Document ID

**Returns:**
- Number of tags removed

**Raises:**
- `RuntimeError`: If ContextBridge not initialized

**Example:**
```python
# Clear all tags from a document
count = await bridge.remove_all_tags_from_document(document_id=42)
print(f"Removed {count} tags")
```

---

### `create_tag`

Create a new custom tag.

```python
async def create_tag(
    name: str,
    category: TagCategory,
    description: Optional[str] = None
) -> Tag
```

**Arguments:**
- `name`: Tag name (must be unique)
- `category`: TagCategory enum value
- `description`: Optional tag description

**Returns:**
- Created `Tag` object

**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If tag name already exists

**Example:**
```python
from context_bridge import TagCategory

# Create a custom tag
new_tag = await bridge.create_tag(
    name="async-io",
    category=TagCategory.technology,
    description="Async I/O and concurrency concepts"
)
print(f"✅ Created tag: {new_tag.name} (ID: {new_tag.id})")

# Use the new tag
await bridge.add_tag_to_document(document_id=42, tag_id=new_tag.id)
```

---

### Complete Tag Workflow Example

```python
from context_bridge import ContextBridge, TagCategory

async def organize_documentation():
    async with ContextBridge() as bridge:
        # Step 1: Crawl documentation
        result = await bridge.crawl_documentation(
            name="my-library",
            version="1.0.0",
            source_url="https://docs.example.com"
        )
        doc_id = result.document_id
        
        # Step 2: Create custom tags for domain-specific organization
        perf_tag = await bridge.create_tag(
            name="performance",
            category=TagCategory.custom,
            description="Performance optimization guides"
        )
        
        # Step 3: Assign both custom and predefined tags
        tags = await bridge.list_tags(category=TagCategory.technology)
        tech_tag_ids = [t.id for t in tags[:3]]
        
        await bridge.add_tags_to_document(
            document_id=doc_id,
            tag_ids=tech_tag_ids + [perf_tag.id]
        )
        
        # Step 4: Verify tags
        assigned_tags = await bridge.get_document_tags(doc_id)
        print(f"✅ Tagged document with: {', '.join([t.name for t in assigned_tags])}")
        
        # Step 5: Continue with chunking and search
        pages = await bridge.list_pages(doc_id)
        group = await bridge.create_group(doc_id, [p.id for p in pages[:50]])
        
        # Documents are now organized and ready for search!
```

---

## Data Models

Context Bridge uses Pydantic models for type-safe data handling. All return types are properly typed.

### Key Models

| Model | Module | Description |
|-------|--------|-------------|
| `GroupInfo` | `context_bridge.database.models.group_models` | Basic group information for lists |
| `GroupStats` | `context_bridge.database.models.group_models` | Detailed group statistics |
| `ReprocessingResult` | `context_bridge.database.models.group_models` | Re-processing operation result |
| `ChunkProcessingResult` | `context_bridge.service.doc_manager` | Chunk processing initiation result |
| `CrawlAndStoreResult` | `context_bridge.service.doc_manager` | Crawling operation result |
| `PageInfo` | `context_bridge.service.doc_manager` | Page information for lists |
| `ContentSearchResult` | `context_bridge.service.search_service` | Search result item |
| `Tag` | `context_bridge.database.models.tag_models` | Tag information |
| `TagCreate` | `context_bridge.database.models.tag_models` | Tag creation input |

### Import Examples

```python
# Group models
from context_bridge.database.models.group_models import (
    GroupInfo,
    GroupStats,
    ReprocessingResult,
)

# Document management models
from context_bridge.service.doc_manager import (
    CrawlAndStoreResult,
    ChunkProcessingResult,
    PageInfo,
)

# Search models
from context_bridge.service.search_service import ContentSearchResult

# Tag models
from context_bridge.database.models.tag_models import (
    Tag,
    TagCreate,
    TagUpdate,
    TagCategory,
)
```

> **📖 Full Documentation:** See [Data Models Reference](MODELS.md) for complete attribute documentation and usage examples.

