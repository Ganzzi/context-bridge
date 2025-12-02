# Context Bridge v0.3.1 Refactor Plan

## Overview

Version 0.3.1 focuses on code quality improvements: removing unused configuration variables, adding comprehensive configuration documentation to the API reference, and documenting exceptions for all public API methods.

**Version:** 0.3.1
**Type:** Refactor / Documentation
**Priority:** Medium
**Status:** ✅ Complete

---

## Table of Contents

1. [Summary of Changes](#summary-of-changes)
2. [Task 1: Remove Unused Config Variable](#task-1-remove-unused-config-variable)
3. [Task 2: Add Configuration Section to API Docs](#task-2-add-configuration-section-to-api-docs)
4. [Task 3: Add Raises Documentation to API Methods](#task-3-add-raises-documentation-to-api-methods)
5. [Implementation Checklist](#implementation-checklist)
6. [Testing Strategy](#testing-strategy)
7. [Migration Notes](#migration-notes)

---

## Summary of Changes

### What's Changing

| Area | Change | Impact |
|------|--------|--------|
| Config | Remove `context_enable_cache` variable | Breaking change for users explicitly setting this |
| API Docs | Add Configuration section | Documentation improvement |
| API Docs | Add Raises sections to all methods | Documentation improvement |

### Files to Modify

1. `context_bridge/config.py` - Remove unused variable
2. `.env.example` - Remove unused env var
3. `docs/API.md` - Add Configuration section + Raises documentation
4. `tests/unit/test_context_agent.py` - Remove unused config setting
5. `tests/integration/test_context_generation_integration.py` - Remove unused config setting

---

## Task 1: Remove Unused Config Variable

### Analysis

The `context_enable_cache` config variable was found to be **defined but never used**:

**Defined in:**
- `context_bridge/config.py` (lines 158-160)
- `.env.example` (line 69)

**Set in tests:**
- `tests/unit/test_context_agent.py` (line 36)
- `tests/integration/test_context_generation_integration.py` (line 32)

**Actually used:** **NOWHERE**

The EmbeddingService has its own `enable_cache` parameter with a default of `True`, but the config variable `context_enable_cache` is never passed to it.

### Decision Options

**Option A: Remove the variable entirely** (Recommended)
- Pros: Clean codebase, no dead code
- Cons: Minor breaking change for users who explicitly set this
- Migration: Document in CHANGELOG, users can safely remove from their .env

**Option B: Wire up the variable to EmbeddingService**
- Pros: Makes the config useful
- Cons: Changes behavior, more complex implementation
- Would require modifying `core.py` to pass `config.context_enable_cache` to EmbeddingService

### Recommendation

**Go with Option A** - Remove the variable. Rationale:
1. The variable has never worked, so no existing functionality depends on it
2. EmbeddingService already defaults to `enable_cache=True`
3. Users who want to disable caching can do so programmatically via the EmbeddingService API
4. Simpler is better - no need to add complexity for a rarely-used feature

### Implementation Steps

#### Step 1.1: Remove from `context_bridge/config.py`

```python
# REMOVE these lines (158-161):
    context_enable_cache: bool = Field(
        default_factory=lambda: os.getenv("CONTEXT_ENABLE_CACHE", "true").lower() == "true",
        description="Enable prompt caching for cost savings",
    )
```

#### Step 1.2: Remove from `.env.example`

```bash
# REMOVE this line:
CONTEXT_ENABLE_CACHE=true
```

#### Step 1.3: Update tests

**`tests/unit/test_context_agent.py`**
```python
# REMOVE this line from the config setup:
        context_enable_cache=True,
```

**`tests/integration/test_context_generation_integration.py`**
```python
# REMOVE this line from the config setup:
        context_enable_cache=True,
```

---

## Task 2: Add Configuration Section to API Docs

### Location

Add a new section to `docs/API.md` after the "Initialization" section, before "Document Operations".

### New Section Content

```markdown
---

## Configuration

### `Config`

Configuration class for Context Bridge. Supports three initialization patterns.

```python
from context_bridge import Config

config = Config(
    postgres_host="localhost",
    postgres_port=5432,
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
```

---

## Task 3: Add Raises Documentation to API Methods

### Exception Categories

Based on code analysis, these are the main exception types:

| Exception | When Raised | Affected Methods |
|-----------|-------------|------------------|
| `RuntimeError` | ContextBridge not initialized | All methods except `__init__`, `initialize`, `is_initialized`, `get_config` |
| `ValueError` | Invalid parameters, validation failures | `crawl_documentation`, `create_group`, `reprocess_group`, `get_group_stats`, `create_tag`, `list_pages` |
| `EmbeddingConnectionError` | Cannot connect to Ollama | `crawl_documentation`, `create_group`, `reprocess_group`, `search` |

### Method-by-Method Raises Documentation

#### Lifecycle Methods

**`initialize()`**
```markdown
**Raises:**
- `RuntimeError`: If database connection fails
- `ConnectionError`: If database is unreachable
```

**`close()`**
No exceptions expected - graceful shutdown.

**`health_check()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

#### Document Operations

**`crawl_documentation()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If `source_url` is invalid or `max_depth` is outside 1-10 range
- `ConnectionError`: If target URL is unreachable
```

**`find_documents()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`list_documents()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`get_document()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`delete_document()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

#### Page Operations

**`list_pages()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If `status` is not one of 'pending', 'chunked', 'deleted'
```

**`delete_page()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

#### Group Operations

**`list_groups()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`create_group()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If pages are from different documents, page IDs are invalid, or content size exceeds limits
- `EmbeddingConnectionError`: If embedding service (Ollama) is unreachable
```

**`get_group_stats()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If group not found
```

**`list_reprocessable_groups()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`reprocess_group()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized, or if reprocessing fails critically
- `ValueError`: If group not found or cannot be reprocessed (wrong status)
- `EmbeddingConnectionError`: If embedding service (Ollama) is unreachable
```

#### Search Operations

**`search()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `EmbeddingConnectionError`: If embedding service is unreachable (for query embedding)
```

#### Tag Operations

**`list_tags()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`get_document_tags()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`add_tag_to_document()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`add_tags_to_document()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`remove_tag_from_document()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`remove_all_tags_from_document()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
```

**`create_tag()`**
```markdown
**Raises:**
- `RuntimeError`: If ContextBridge not initialized
- `ValueError`: If tag name already exists
```

---

## Implementation Checklist

### Task 1: Remove `context_enable_cache`
- [x] Remove from `context_bridge/config.py`
- [x] Remove from `.env.example`
- [x] Update `tests/unit/test_context_agent.py`
- [x] Update `tests/integration/test_context_generation_integration.py`
- [x] Run tests to verify nothing breaks

### Task 2: Add Configuration Section
- [x] Add Configuration section to `docs/API.md` after Initialization
- [x] Include all config parameters in tables
- [x] Add configuration patterns (Python, env vars, .env)
- [x] Review for accuracy against actual `Config` class

### Task 3: Add Raises Documentation
- [x] Update `docs/API.md` - Add Raises to `initialize()`
- [x] Update `docs/API.md` - Add Raises to `close()`
- [x] Update `docs/API.md` - Add Raises to `health_check()`
- [x] Update `docs/API.md` - Add Raises to `crawl_documentation()`
- [x] Update `docs/API.md` - Add Raises to `find_documents()`
- [x] Update `docs/API.md` - Add Raises to `list_documents()`
- [x] Update `docs/API.md` - Add Raises to `get_document()`
- [x] Update `docs/API.md` - Add Raises to `delete_document()`
- [x] Update `docs/API.md` - Add Raises to `list_pages()`
- [x] Update `docs/API.md` - Add Raises to `delete_page()`
- [x] Update `docs/API.md` - Add Raises to `list_groups()`
- [x] Update `docs/API.md` - Add Raises to `create_group()`
- [x] Update `docs/API.md` - Add Raises to `get_group_stats()`
- [x] Update `docs/API.md` - Add Raises to `list_reprocessable_groups()`
- [x] Update `docs/API.md` - Add Raises to `reprocess_group()`
- [x] Update `docs/API.md` - Add Raises to `search()`
- [x] Update `docs/API.md` - Add Raises to Tag Operations (all methods)

### Task 4: Type Safety Improvements (Added)
- [x] Create new Pydantic models in `group_models.py` (GroupInfo, GroupStats, ReprocessingResult)
- [x] Refactor `core.py` to use Pydantic models instead of `Dict[str, Any]`
- [x] Update `__init__.py` exports for new models
- [x] Create `docs/MODELS.md` documentation
- [x] Update `docs/API.md` with model references and Data Models section

### Final Steps
- [x] Update CHANGELOG.md with v0.3.1 changes
- [x] Bump version in `pyproject.toml` to 0.3.1
- [x] Run full test suite (331 passed, some pre-existing failures unrelated to v0.3.1)
- [x] Review documentation for completeness

---

## Testing Strategy

### What to Test

1. **Config removal doesn't break anything:**
   ```bash
   python -m pytest tests/ -v
   ```

2. **Documentation accuracy:**
   - Manual review of Config tables against `config.py`
   - Verify all Raises match actual exceptions in code

3. **No regressions:**
   - Run full integration test suite
   - Verify Streamlit app still works
   - Verify MCP server still works

### Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=context_bridge --cov-report=html

# Check for import errors
python -c "from context_bridge import ContextBridge, Config; print('OK')"
```

---

## Migration Notes

### For Users

**v0.3.1 Breaking Changes:**

1. **Removed `context_enable_cache` config variable**
   - This variable was never functional
   - If you have `CONTEXT_ENABLE_CACHE` in your `.env`, you can safely remove it
   - Embedding caching is always enabled by default through `EmbeddingService`

### For Developers

1. The `EmbeddingService` class has its own `enable_cache` parameter (default: `True`)
2. If cache control is needed in the future, consider:
   - Adding `embedding_enable_cache` to Config
   - Wiring it to `EmbeddingService(config, enable_cache=config.embedding_enable_cache)`

---

## Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| Planning | ✅ Complete | This document |
| Implementation | ~1 hour | Remove config, update API docs |
| Testing | ~30 min | Run test suite, manual verification |
| Release | ~15 min | Update CHANGELOG, bump version |

**Total Estimated Time:** 2 hours

---

## Notes

- `context_batch_size` IS used (in `context_generator.py`) - do NOT remove
- The `EmbeddingConnectionError` is a custom exception defined in `context_bridge/service/embedding.py`
- Consider importing `EmbeddingConnectionError` in `__init__.py` for user convenience in future version
