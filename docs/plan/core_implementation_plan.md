# Context Bridge - Core Implementation Plan

**Version:** 2.0  
**Last Updated:** October 12, 2025  
**Status:** Active Implementation - Phase 3 Completed, Architecture Revision

---

## 📋 Document Overview

This document outlines the complete implementation plan for the **Context Bridge** core package, focusing on the essential functionality needed for crawling, storing, chunking, and searching technical documentation with RAG capabilities.

**Scope:**
- ✅ Core Python package implementation
- ✅ Database schema and initialization
- ✅ Repository layer (data access)
- ✅ Service layer (business logic)
- ✅ Complete crawling workflow
- 🔄 Unified API via ContextBridge class
- ❌ MCP server (separate phase)
- ❌ Streamlit UI (separate phase)

**Architecture Changes (v2.0):**
- **Removed:** Page grouping concept (page_groups, page_group_members tables, GroupRepository)
- **Simplified:** Direct page-to-chunk workflow without intermediate grouping
- **Added:** DocManager service for high-level document operations
- **Added:** ContextBridge class as unified API entry point

---

## 🎯 Project Goals

### Primary Objectives

1. **Enable intelligent documentation crawling** with automatic type detection (webpages, sitemaps, text files)
2. **Store raw crawled content** with deduplication and metadata tracking
3. **Implement smart Markdown chunking** that preserves code blocks and structure with size validation
4. **Generate and store embeddings** with dual vector + BM25 indexing
5. **Enable hybrid search** combining vector similarity and BM25 full-text search
6. **Support document versioning** for multiple versions of the same documentation
7. **Provide simple, unified API** through ContextBridge class for easy integration

### Success Criteria

- [ ] Successfully crawl and store 1000+ pages from technical documentation sites
- [ ] Chunk content with >95% preservation of code block integrity
- [ ] Achieve <500ms average search response time for hybrid queries
- [ ] Support concurrent operations with connection pooling
- [ ] Maintain type safety throughout with Pydantic models
- [ ] Provide comprehensive test coverage (>80%)
- [ ] Simple API with clear documentation for end users

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer Architecture                        │
└─────────────────────────────────────────────────────────────┘

Layer 1: Public API
└── core.py (ContextBridge class - unified entry point)

Layer 2: Configuration
├── config.py (Pydantic models, environment variables)

Layer 3: Database Foundation
├── postgres_manager.py (Connection pooling, context managers)
├── init_databases.py (Schema initialization)
└── schema/extensions.sql (SQL schema definitions)

Layer 4: Repository Layer (Data Access)
├── document_repository.py (CRUD for documents)
├── page_repository.py (CRUD for crawled pages)
└── chunk_repository.py (Chunk storage and hybrid search)

Layer 5: Service Layer (Business Logic)
├── doc_manager.py (High-level document operations)
├── search_service.py (Orchestrate hybrid search)
├── url_service.py (URL parsing and type detection)
├── crawling_service.py (Web crawling workflow)
├── chunking_service.py (Smart Markdown chunking)
└── embedding.py (Generate embeddings via Ollama/Gemini)

Layer 6: External Dependencies
├── PSQLPy (PostgreSQL driver)
├── Crawl4AI (Web crawling)
├── Ollama/Gemini (Embeddings)
└── PostgreSQL Extensions (pgvector, vchord_bm25)
```

**Key Architecture Changes:**
- **Simplified Workflow:** Pages → Chunks (no intermediate grouping)
- **DocManager:** Orchestrates document-level operations (crawl, chunk, manage pages)
- **ContextBridge:** Single entry point for all user-facing operations
- **Direct Chunking:** Users select page IDs, content is combined and validated, then chunked

---

## 📅 Implementation Phases

### Phase 1: Database Foundation ⚡ (Priority: Critical) ✅ **COMPLETED**

**Goal:** Establish reliable database connection and schema

#### 1.1 Database Schema Design

**File:** `context_bridge/schema/extensions.sql`

```sql
-- Extensions (must be created first)
CREATE EXTENSION IF NOT EXISTS vector CASCADE;
CREATE EXTENSION IF NOT EXISTS vchord CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_tokenizer CASCADE;
CREATE EXTENSION IF NOT EXISTS vchord_bm25 CASCADE;

-- Table: documents (versioned documentation)
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    source_url TEXT,
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Table: pages (raw crawled content)
CREATE TABLE IF NOT EXISTS pages (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    url TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_length INTEGER GENERATED ALWAYS AS (length(content)) STORED,
    crawled_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'chunked', 'deleted')),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Table: chunks (embedded content)
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_page_ids INTEGER[] NOT NULL, -- Array of page IDs used to create this chunk
    embedding VECTOR(768), -- Dimension must match config
    bm25_vector bm25vector, -- Auto-generated by trigger
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pages_document ON pages(document_id);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_hash ON pages(content_hash);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_source_pages ON chunks USING GIN(source_page_ids);
CREATE INDEX IF NOT EXISTS idx_chunks_vector ON chunks USING vchord(embedding);
CREATE INDEX IF NOT EXISTS idx_chunks_bm25 ON chunks USING vchord_bm25 (bm25_vector);

-- Trigger: Auto-generate bm25_vector from content
CREATE OR REPLACE FUNCTION generate_bm25_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.bm25_vector := tokenize(NEW.content, 'bert');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER chunks_bm25_trigger
BEFORE INSERT OR UPDATE OF content ON chunks
FOR EACH ROW
EXECUTE FUNCTION generate_bm25_vector();

-- Trigger: Update documents.updated_at
CREATE OR REPLACE FUNCTION update_document_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE documents SET updated_at = NOW() WHERE id = NEW.document_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_doc_on_page_insert
AFTER INSERT ON pages
FOR EACH ROW
EXECUTE FUNCTION update_document_timestamp();

CREATE TRIGGER update_doc_on_chunk_insert
AFTER INSERT ON chunks
FOR EACH ROW
EXECUTE FUNCTION update_document_timestamp();
```

**Schema Changes from v1.0:**
- **Removed:** `page_groups` and `page_group_members` tables
- **Updated:** `pages.status` changed from 'grouped' to 'chunked'
- **Updated:** `chunks` table:
  - Removed `group_id` column
  - Added `source_page_ids` INTEGER[] to track which pages were combined
  - Simplified UNIQUE constraint to (document_id, chunk_index)

**Tasks:**
- [x] Review existing `extensions.sql`
- [ ] Remove page_groups and page_group_members tables
- [ ] Update chunks table schema
- [ ] Update page status constraints
- [ ] Add GIN index for source_page_ids array
- [x] Add triggers for bm25_vector generation
- [x] Add constraints and validation

**Dependencies:** None  
**Testing:** Run initialization and verify schema with `\d` commands

---

#### 1.2 PostgreSQL Manager Enhancement

**File:** `context_bridge/database/postgres_manager.py`

**Current State:** Basic implementation exists  
**Required Enhancements:**

```python
class PostgreSQLManager:
    """
    Enhanced PostgreSQL manager with:
    - Connection pooling
    - Transaction support
    - Connection health checks
    - Graceful shutdown
    """
    
    async def initialize(self) -> None:
        """Initialize connection pool with retry logic."""
        
    async def health_check(self) -> bool:
        """Verify database connectivity."""
        
    async def execute_transaction(self, operations: list) -> None:
        """Execute multiple operations in a transaction."""
        
    async def close(self) -> None:
        """Gracefully close all connections."""
```

**Tasks:**
- [x] Add connection retry logic with exponential backoff
- [x] Implement health check method
- [x] Add transaction support with rollback
- [x] Add connection pool statistics logging
- [x] Add graceful shutdown with connection cleanup

**Dependencies:** Phase 1.1  
**Testing:** Unit tests with mock connections, integration tests with real DB

---

#### 1.3 Database Initialization Script

**File:** `context_bridge/database/init_databases.py`

**Current State:** Basic implementation exists  
**Required Enhancements:**

```python
async def init_postgresql():
    """
    Initialize PostgreSQL with:
    - Extension creation
    - Schema creation
    - Index creation
    - Trigger setup
    - Verification
    """
    
async def verify_schema():
    """Verify all tables, indexes, and extensions exist."""
    
async def reset_database():
    """Drop and recreate all tables (dev only)."""
```

**Tasks:**
- [x] Add schema verification step
- [x] Add idempotent schema creation (IF NOT EXISTS)
- [x] Add migration support for schema changes
- [x] Add dev-only reset function
- [x] Improve error messages and logging

**Dependencies:** Phase 1.1, 1.2  
**Testing:** Run multiple times to verify idempotency

---

### Phase 2: Repository Layer 🗄️ (Priority: Critical) ✅ **COMPLETED**

**Goal:** Create type-safe data access layer with PSQLPy

**Status:** Phase 2 completed with revised architecture (no GroupRepository)

#### 2.1 Document Repository ✅

**File:** `context_bridge/database/repositories/document_repository.py`

**Status:** ✅ **COMPLETED**  
**Dependencies:** Phase 1.1, 1.2  
**Testing:** 15+ unit tests, 5+ integration tests

---

#### 2.2 Page Repository ✅

**File:** `context_bridge/database/repositories/page_repository.py`

**Updates Required:**
- [ ] Update status values from 'grouped' to 'chunked'
- [ ] Add method to get combined content for multiple page IDs
- [ ] Add method to validate total size of selected pages

**New Methods Needed:**

```python
async def get_combined_content(
    self,
    page_ids: List[int],
    separator: str = "\n\n---\n\n"
) -> str:
    """
    Get combined content of multiple pages.
    Pages are ordered by ID and joined with separator.
    """

async def validate_pages_for_chunking(
    self,
    page_ids: List[int],
    min_size: Optional[int] = None,
    max_size: Optional[int] = None
) -> Tuple[bool, Optional[str], int]:
    """
    Validate if pages can be chunked together.
    Checks:
    - All pages exist and belong to same document
    - All pages have status 'pending'
    - Total size is within bounds
    Returns: (is_valid, error_message, total_size)
    """
```

**Status:** ✅ **BASE COMPLETED**, Updates pending  
**Dependencies:** Phase 2.1  
**Testing:** 20+ unit tests, 8+ integration tests

---

#### 2.3 Chunk Repository ✅

**File:** `context_bridge/database/repositories/chunk_repository.py`

**Updates Required:**
- [ ] Remove `group_id` parameter from create methods
- [ ] Add `source_page_ids` parameter to create methods
- [ ] Update search methods to work without groups
- [ ] Remove `list_by_group` method
- [ ] Add `list_by_pages` method to find chunks created from specific pages

**Updated Interface:**

```python
class Chunk(BaseModel):
    """Chunk model."""
    id: int
    document_id: int
    chunk_index: int
    content: str
    source_page_ids: List[int]  # Changed from group_id
    embedding: List[float]
    created_at: datetime

class ChunkRepository:
    """Repository for chunk operations with hybrid search."""
    
    async def create(
        self,
        document_id: int,
        chunk_index: int,
        content: str,
        source_page_ids: List[int],  # New parameter
        embedding: List[float]
    ) -> int:
        """
        Create a chunk with embedding.
        BM25 vector is auto-generated by trigger.
        """
        
    async def create_batch(
        self,
        chunks: List[dict]  # Each dict includes source_page_ids
    ) -> List[int]:
        """Create multiple chunks efficiently. Returns list of IDs."""
        
    async def list_by_pages(
        self,
        page_ids: List[int]
    ) -> List[Chunk]:
        """Get all chunks created from specific pages."""
        
    # ... rest of search methods remain the same
```

**Status:** ✅ **BASE COMPLETED**, Updates pending  
**Dependencies:** Phase 2.2  
**Testing:** 25+ unit tests, 15+ integration tests

---
        """
        BM25 full-text search using vchord_bm25.
        Returns chunks ordered by BM25 relevance.
        """
        
    async def hybrid_search(
        self,
        document_id: int,
        query: str,
        query_embedding: List[float],
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Hybrid search combining vector and BM25 with weighted scores.
        
        Algorithm:
        1. Perform vector search (top 50)
        2. Perform BM25 search (top 50)
        3. Normalize scores to 0-1 range
        4. Combine: final_score = (vector_score * vector_weight) + (bm25_score * bm25_weight)
        5. Return top N by final score
        """
        
    async def delete_by_document(self, document_id: int) -> int:
        """Delete all chunks for a document. Returns count deleted."""
        
    async def delete_by_group(self, group_id: int) -> int:
        """Delete all chunks for a group. Returns count deleted."""
```

**Tasks:**
- [x] Implement vector search with pgvector operators
- [x] Implement BM25 search with vchord_bm25 operators
- [x] Implement hybrid search algorithm
- [x] Add batch operations for efficiency
- [x] Handle PgVector type conversions
- [ ] Write unit tests with mock embeddings
- [ ] Write integration tests with real vectors

**Status:** ✅ **COMPLETED**  
**Dependencies:** Phase 2.3  
**Testing:** 25+ unit tests, 15+ integration tests

**Reference Documentation:** `docs/technical/psqlpy-complete-guide.md` (Section 9: Vector Operations)

---

### Phase 3: Service Layer 🔧 (Priority: High)

**Goal:** Implement business logic and orchestration

#### 3.1 URL Service (Already Exists)

**File:** `context_bridge/service/url_service.py`

**Current State:** Implementation exists  
**Required Validation:**

- [ ] Verify is_txt() method works correctly
- [ ] Verify is_sitemap() method works correctly
- [ ] Verify get_domain() method works correctly
- [ ] Add unit tests if missing
- [ ] Document API

**Dependencies:** None  
**Testing:** 10+ unit tests

---

#### 3.2 Crawling Service Enhancement

**File:** `context_bridge/service/crawling_service.py`

**Current State:** May exist partially  
**Required Implementation:**

```python
from typing import List, Optional
from crawl4ai import AsyncWebCrawler
from pydantic import BaseModel, field_validator

class CrawlConfig(BaseModel):
    """Crawling configuration."""
    max_depth: int = 3
    max_concurrent: int = 10
    memory_threshold: float = 70.0
    
    @field_validator('max_depth')
    def validate_depth(cls, v):
        if not 1 <= v <= 10:
            raise ValueError('max_depth must be between 1 and 10')
        return v

class CrawlResult(BaseModel):
    """Single crawl result."""
    url: str
    markdown: str
    
    @field_validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class CrawlBatchResult(BaseModel):
    """Batch crawl results."""
    results: List[CrawlResult]
    crawl_type: CrawlType
    total_urls_attempted: int
    successful_count: int
    failed_count: int

class CrawlingService:
    """Service for orchestrating web crawling operations."""
    
    def __init__(self, config: CrawlConfig, url_service: UrlService):
        self.config = config
        self.url_service = url_service
        
    async def crawl_webpage(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        depth: Optional[int] = None
    ) -> CrawlBatchResult:
        """Crawl a webpage with automatic type detection and dispatch.
        
        Args:
            crawler: AsyncWebCrawler instance to use for crawling
            url: URL to crawl
            depth: Optional override for max_depth from config (1-10)
        """
```

**Tasks:**
- [x] Review existing crawl_webpage implementation
- [x] Add progress callbacks
- [x] Add error recovery and retry logic
- [x] Improve logging
- [x] Write integration tests with real crawler
- [x] Add optional depth parameter override
- [x] Implement recursive webpage crawling
- [x] Implement sitemap batch processing
- [x] Implement text file crawling
- [x] Create comprehensive unit tests

**Status:** ✅ **COMPLETED**  
**Dependencies:** Phase 2.2, 3.1  
**Testing:** 25 unit tests covering all functionality

**Reference Documentation:** `docs/technical/crawl4ai_complete_guide.md`

---

#### 3.3 Chunking Service

**File:** `context_bridge/service/chunking_service.py`

**Current State:** ✅ **IMPLEMENTED**  
**Required Implementation:**

```python
from typing import List, Optional

class ChunkingService:
    """Service for smart Markdown chunking."""
    
    def __init__(self, default_chunk_size: int = 2000):
        self.default_chunk_size = default_chunk_size
    
    def smart_chunk_markdown(
        self,
        markdown: str,
        chunk_size: Optional[int] = None
    ) -> List[str]:
        """
        Smart chunk Markdown content preserving structure.
        
        Algorithm (from docs/technical/smart_chunk_markdown_algorithm.md):
        1. Try to split at code blocks (```)
        2. Fall back to paragraph breaks (\\n\\n)
        3. Fall back to sentence breaks (. )
        4. Fall back to hard limit
        
        Returns list of chunk strings.
        """
        
    def estimate_chunks(
        self,
        content_length: int,
        chunk_size: Optional[int] = None
    ) -> int:
        """Estimate number of chunks for given content length."""
        
    def validate_chunks(
        self,
        chunks: List[str],
        min_size: int = 100,
        max_size: int = 10000
    ) -> bool:
        """Validate that chunks meet size constraints."""
```

**Tasks:**
- [x] Implement smart_chunk_markdown algorithm
- [x] Add boundary detection (code blocks, paragraphs, sentences)
- [x] Add chunk size validation
- [x] Add comprehensive unit tests with various Markdown patterns
- [x] Test with real documentation samples

**Status:** ✅ **COMPLETED**  
**Dependencies:** None  
**Testing:** 30+ unit tests covering edge cases

**Reference Documentation:** `docs/technical/smart_chunk_markdown_algorithm.md`

---

#### 3.4 Embedding Service Enhancement

**File:** `context_bridge/service/embedding.py`

**Current State:** ✅ **ENHANCED**  
**Required Validation:**

```python
class EmbeddingService:
    """Service for generating embeddings with caching and retry logic."""
    
    # Enhanced methods:
    async def get_embedding(self, text: str, timeout: int = 30) -> List[float]
    async def get_embeddings_batch(self, texts: List[str], ...) -> List[List[float]]
    async def verify_connection(self) -> bool
    async def ensure_model_available(self) -> bool
    def get_cache_stats(self) -> Dict[str, Any]
    def clear_cache(self) -> None
    def validate_configuration(self) -> List[str]
```

**Tasks:**
- [x] Review existing implementation
- [x] Add embedding dimension validation
- [x] Add caching for repeated texts
- [x] Add retry logic with exponential backoff
- [x] Add comprehensive error handling
- [x] Write unit tests with mocked API calls
- [x] Write integration tests with real Ollama

**Status:** ✅ **COMPLETED**  
**Dependencies:** Phase 1 (config)  
**Testing:** 25+ unit tests, 12+ integration tests

**Reference Documentation:** `docs/technical/embedding_service.md`

---

#### 3.5 Search Service (New)

**File:** `context_bridge/service/search_service.py`

**Current State:** ✅ **IMPLEMENTED**  
**Required Implementation:**

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class DocumentSearchResult(BaseModel):
    """Document search result."""
    document: Document
    relevance_score: float
    
class ContentSearchResult(BaseModel):
    """Content search result with context."""
    chunk: Chunk
    document_name: str
    document_version: str
    score: float
    rank: int

class SearchService:
    """Service for orchestrating search operations."""
    
    def __init__(
        self,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        embedding_service: EmbeddingService,
        default_vector_weight: float = 0.7,
        default_bm25_weight: float = 0.3
    ):
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.embedding_service = embedding_service
        self.default_vector_weight = default_vector_weight
        self.default_bm25_weight = default_bm25_weight
    
    async def find_documents(
        self,
        query: str,
        limit: int = 10
    ) -> List[DocumentSearchResult]:
        """
        Find documents by query.
        Searches document name, description, and metadata.
        Returns documents sorted by relevance.
        """
        
    async def search_content(
        self,
        query: str,
        document_id: int,
        version: Optional[str] = None,
        limit: int = 10,
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None
    ) -> List[ContentSearchResult]:
        """
        Search within document content using hybrid search.
        
        Steps:
        1. Generate query embedding
        2. Perform hybrid search in chunks
        3. Enrich results with document metadata
        4. Return ranked results
        """
        
    async def search_across_versions(
        self,
        query: str,
        document_name: str,
        limit_per_version: int = 5
    ) -> dict[str, List[ContentSearchResult]]:
        """
        Search across all versions of a document.
        Returns dict mapping version -> results.
        """
```

**Tasks:**
- [x] Implement document search with text matching
- [x] Implement content search with hybrid algorithm
- [x] Implement cross-version search
- [x] Add result ranking and deduplication
- [x] Add relevance score calculation
- [x] Write comprehensive unit tests
- [x] Write integration tests
- [x] Create database integration test script (`scripts/test_search_service.py`)

**Dependencies:** Phase 2.4, 3.4  
**Testing:** 20+ unit tests, 10+ integration tests

---

### Phase 4: High-Level Services & Public API 🚀 (Priority: High) **NEW**

**Goal:** Create DocManager for document operations and ContextBridge as unified public API

#### 4.1 Document Manager Service (NEW)

**File:** `context_bridge/service/doc_manager.py`

**Purpose:** High-level orchestration for document operations

**Implementation:**

```python
from typing import List, Optional
from pydantic import BaseModel
import logging
import hashlib

logger = logging.getLogger(__name__)

class CrawlAndStoreResult(BaseModel):
    """Result of crawl and store operation."""
    document_id: int
    document_name: str
    document_version: str
    pages_crawled: int
    pages_stored: int
    duplicates_skipped: int
    errors: int

class ChunkProcessingResult(BaseModel):
    """Result of chunking operation."""
    document_id: int
    pages_processed: int
    chunks_created: int
    errors: int

class PageInfo(BaseModel):
    """Simplified page information for listing."""
    id: int
    url: str
    content_length: int
    status: str
    crawled_at: datetime

class DocManager:
    """High-level document management service."""
    
    def __init__(
        self,
        db_manager: PostgreSQLManager,
        crawling_service: CrawlingService,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        config: Config
    ):
        self.db_manager = db_manager
        self.crawling_service = crawling_service
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.config = config
        
    async def crawl_and_store(
        self,
        name: str,
        version: str,
        source_url: str,
        description: Optional[str] = None,
        max_depth: Optional[int] = None
    ) -> CrawlAndStoreResult:
        """
        Crawl documentation and store pages.
        
        Workflow:
        1. Create or get document
        2. Crawl source URL with optional depth override
        3. Store pages (skip duplicates)
        4. Return detailed results
        """
        logger.info(f"Starting crawl_and_store for {name} v{version} from {source_url}")
        
        async with self.db_manager.connection() as conn:
            doc_repo = DocumentRepository(conn)
            page_repo = PageRepository(conn)
            
            # Get or create document
            doc = await doc_repo.get_by_name_version(name, version)
            if not doc:
                doc_id = await doc_repo.create(
                    name=name,
                    version=version,
                    source_url=source_url,
                    description=description
                )
            else:
                doc_id = doc.id
            
            # Crawl with optional depth override
            async with AsyncWebCrawler(verbose=True) as crawler:
                crawl_result = await self.crawling_service.crawl_webpage(
                    crawler,
                    source_url,
                    depth=max_depth
                )
            
            # Store pages
            stored = 0
            duplicates = 0
            errors = 0
            
            for page in crawl_result.results:
                try:
                    content_hash = hashlib.sha256(page.markdown.encode()).hexdigest()
                    existing = await page_repo.get_by_url(page.url)
                    
                    if existing:
                        duplicates += 1
                        continue
                    
                    await page_repo.create(
                        document_id=doc_id,
                        url=page.url,
                        content=page.markdown,
                        content_hash=content_hash
                    )
                    stored += 1
                    
                except Exception as e:
                    logger.error(f"Error storing page {page.url}: {e}")
                    errors += 1
            
            logger.info(
                f"Crawl complete: {stored} stored, "
                f"{duplicates} duplicates, {errors} errors"
            )
            
            return CrawlAndStoreResult(
                document_id=doc_id,
                document_name=name,
                document_version=version,
                pages_crawled=len(crawl_result.results),
                pages_stored=stored,
                duplicates_skipped=duplicates,
                errors=errors
            )
    
    async def list_pages(
        self,
        document_id: int,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[PageInfo]:
        """
        List pages for a document with pagination.
        
        Args:
            document_id: Document ID
            status: Optional status filter ('pending', 'chunked', 'deleted')
            offset: Pagination offset
            limit: Maximum results
        """
        async with self.db_manager.connection() as conn:
            page_repo = PageRepository(conn)
            pages = await page_repo.list_by_document(
                document_id,
                status=status,
                offset=offset,
                limit=limit
            )
            
            return [
                PageInfo(
                    id=p.id,
                    url=p.url,
                    content_length=p.content_length,
                    status=p.status,
                    crawled_at=p.crawled_at
                )
                for p in pages
            ]
    
    async def delete_page(
        self,
        page_id: int
    ) -> bool:
        """
        Delete a page (soft delete - marks as 'deleted').
        
        Args:
            page_id: Page ID to delete
            
        Returns:
            True if successful
        """
        async with self.db_manager.connection() as conn:
            page_repo = PageRepository(conn)
            return await page_repo.delete(page_id)
    
    async def process_chunking(
        self,
        document_id: int,
        page_ids: List[int],
        chunk_size: Optional[int] = None
    ) -> ChunkProcessingResult:
        """
        Process pages for chunking and embedding.
        
        Workflow:
        1. Validate pages (same document, status='pending', size constraints)
        2. Get combined content
        3. Chunk content
        4. Generate embeddings (batch)
        5. Store chunks with source_page_ids
        6. Update page status to 'chunked'
        
        Args:
            document_id: Document ID
            page_ids: List of page IDs to process
            chunk_size: Optional chunk size override
            
        Returns:
            ChunkProcessingResult with counts and errors
        """
        logger.info(f"Starting process_chunking for doc {document_id}, {len(page_ids)} pages")
        
        chunk_size = chunk_size or self.config.chunk_size
        min_size = self.config.min_combined_content_size
        max_size = self.config.max_combined_content_size
        
        async with self.db_manager.connection() as conn:
            page_repo = PageRepository(conn)
            chunk_repo = ChunkRepository(self.db_manager)
            
            # Validate pages
            is_valid, error_msg, total_size = await page_repo.validate_pages_for_chunking(
                page_ids,
                min_size=min_size,
                max_size=max_size
            )
            
            if not is_valid:
                raise ValueError(f"Page validation failed: {error_msg}")
            
            logger.info(f"Validated {len(page_ids)} pages, total size: {total_size} chars")
            
            # Get combined content
            combined_content = await page_repo.get_combined_content(page_ids)
            
            # Chunk
            chunks = self.chunking_service.smart_chunk_markdown(
                combined_content,
                chunk_size=chunk_size
            )
            
            logger.info(f"Created {len(chunks)} chunks from combined content")
            
            # Generate embeddings in batch
            try:
                embeddings = await self.embedding_service.get_embeddings_batch(chunks)
            except Exception as e:
                logger.error(f"Error generating embeddings: {e}")
                raise
            
            # Store chunks
            chunks_created = 0
            errors = 0
            
            chunk_data = []
            for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_data.append({
                    'document_id': document_id,
                    'chunk_index': i,
                    'content': chunk_text,
                    'source_page_ids': page_ids,
                    'embedding': embedding
                })
            
            try:
                chunk_ids = await chunk_repo.create_batch(chunk_data)
                chunks_created = len(chunk_ids)
                
                # Update page status to 'chunked'
                await page_repo.update_status_bulk(page_ids, 'chunked')
                
            except Exception as e:
                logger.error(f"Error storing chunks: {e}")
                errors += 1
            
            logger.info(
                f"Chunking complete: {chunks_created} chunks created, "
                f"{errors} errors"
            )
            
            return ChunkProcessingResult(
                document_id=document_id,
                pages_processed=len(page_ids),
                chunks_created=chunks_created,
                errors=errors
            )
```

**Configuration Updates Required:**

Add to `context_bridge/config.py`:

```python
class Config(BaseModel):
    # ... existing fields ...
    
    # Chunking configuration
    chunk_size: int = Field(default=2000, description="Default chunk size for markdown chunking")
    min_combined_content_size: int = Field(default=100, description="Minimum total size for combined page content")
    max_combined_content_size: int = Field(default=50000, description="Maximum total size for combined page content")
```

**Tasks:**
- [x] Implement DocManager class
- [x] Add configuration fields to Config
- [x] Implement crawl_and_store method
- [x] Implement list_pages method
- [x] Implement delete_page method
- [x] Implement process_chunking method with validation
- [x] Add comprehensive error handling
- [x] Write unit tests with mocked dependencies
- [x] Write integration tests

**Dependencies:** Phase 2, Phase 3  
**Testing:** 15+ unit tests, 8+ integration tests

---

#### 4.2 ContextBridge Public API (NEW)

**File:** `context_bridge/core.py`

**Purpose:** Unified entry point for all package functionality

**Implementation:**

```python
from typing import List, Optional
from pydantic import BaseModel
import logging

from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.service.doc_manager import DocManager, CrawlAndStoreResult, ChunkProcessingResult, PageInfo
from context_bridge.service.search_service import SearchService, ContentSearchResult
from context_bridge.service.crawling_service import CrawlingService
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService
from context_bridge.service.url_service import UrlService
from context_bridge.database.repositories.document_repository import DocumentRepository, Document

logger = logging.getLogger(__name__)

class ContextBridge:
    """
    Unified API for Context Bridge functionality.
    
    This class provides a simple interface for:
    - Crawling and storing documentation
    - Managing pages
    - Processing chunks with embeddings
    - Searching documentation content
    - Managing documents
    
    Example:
        ```python
        from context_bridge import ContextBridge
        
        # Initialize
        bridge = ContextBridge()
        await bridge.initialize()
        
        # Crawl documentation
        result = await bridge.crawl_documentation(
            name="psqlpy",
            version="0.9.0",
            source_url="https://psqlpy.readthedocs.io"
        )
        
        # List pages
        pages = await bridge.list_pages(result.document_id)
        
        # Process chunking
        page_ids = [p.id for p in pages[:10]]
        chunk_result = await bridge.process_pages(result.document_id, page_ids)
        
        # Search
        results = await bridge.search(
            query="connection pooling",
            document_id=result.document_id
        )
        
        # Cleanup
        await bridge.close()
        ```
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize ContextBridge.
        
        Args:
            config: Optional configuration. If not provided, loads from environment.
        """
        self.config = config or Config()
        self._db_manager: Optional[PostgreSQLManager] = None
        self._doc_manager: Optional[DocManager] = None
        self._search_service: Optional[SearchService] = None
        self._initialized = False
        
    async def initialize(self) -> None:
        """
        Initialize database connections and services.
        Must be called before using any other methods.
        """
        if self._initialized:
            logger.warning("ContextBridge already initialized")
            return
        
        logger.info("Initializing ContextBridge...")
        
        # Initialize database
        self._db_manager = PostgreSQLManager(self.config.postgres)
        await self._db_manager.initialize()
        
        # Initialize services
        url_service = UrlService()
        crawl_config = CrawlConfig(
            max_depth=self.config.crawl_max_depth,
            max_concurrent=self.config.crawl_max_concurrent
        )
        crawling_service = CrawlingService(crawl_config, url_service)
        chunking_service = ChunkingService(default_chunk_size=self.config.chunk_size)
        embedding_service = EmbeddingService(self.config.embedding)
        
        # Initialize high-level services
        self._doc_manager = DocManager(
            db_manager=self._db_manager,
            crawling_service=crawling_service,
            chunking_service=chunking_service,
            embedding_service=embedding_service,
            config=self.config
        )
        
        async with self._db_manager.connection() as conn:
            doc_repo = DocumentRepository(conn)
            chunk_repo = ChunkRepository(self._db_manager)
            self._search_service = SearchService(
                document_repo=doc_repo,
                chunk_repo=chunk_repo,
                embedding_service=embedding_service
            )
        
        self._initialized = True
        logger.info("ContextBridge initialized successfully")
    
    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        if self._db_manager:
            await self._db_manager.close()
        self._initialized = False
        logger.info("ContextBridge closed")
    
    def _check_initialized(self) -> None:
        """Verify that initialize() has been called."""
        if not self._initialized:
            raise RuntimeError(
                "ContextBridge not initialized. Call await bridge.initialize() first."
            )
    
    # Document Operations
    
    async def crawl_documentation(
        self,
        name: str,
        version: str,
        source_url: str,
        description: Optional[str] = None,
        max_depth: Optional[int] = None
    ) -> CrawlAndStoreResult:
        """
        Crawl and store documentation from a URL.
        
        Args:
            name: Document name
            version: Document version
            source_url: URL to crawl
            description: Optional description
            max_depth: Optional crawl depth override (1-10)
            
        Returns:
            CrawlAndStoreResult with summary
        """
        self._check_initialized()
        return await self._doc_manager.crawl_and_store(
            name=name,
            version=version,
            source_url=source_url,
            description=description,
            max_depth=max_depth
        )
    
    async def list_documents(
        self,
        offset: int = 0,
        limit: int = 100
    ) -> List[Document]:
        """
        List all documents with pagination.
        
        Args:
            offset: Pagination offset
            limit: Maximum results
            
        Returns:
            List of Document objects
        """
        self._check_initialized()
        async with self._db_manager.connection() as conn:
            doc_repo = DocumentRepository(conn)
            return await doc_repo.list_all(offset=offset, limit=limit)
    
    async def get_document(
        self,
        name: str,
        version: str
    ) -> Optional[Document]:
        """
        Get a specific document by name and version.
        
        Args:
            name: Document name
            version: Document version
            
        Returns:
            Document or None if not found
        """
        self._check_initialized()
        async with self._db_manager.connection() as conn:
            doc_repo = DocumentRepository(conn)
            return await doc_repo.get_by_name_version(name, version)
    
    async def delete_document(
        self,
        document_id: int
    ) -> bool:
        """
        Delete a document and all related data (pages, chunks).
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if successful
        """
        self._check_initialized()
        async with self._db_manager.connection() as conn:
            doc_repo = DocumentRepository(conn)
            return await doc_repo.delete(document_id)
    
    # Page Operations
    
    async def list_pages(
        self,
        document_id: int,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[PageInfo]:
        """
        List pages for a document.
        
        Args:
            document_id: Document ID
            status: Optional status filter ('pending', 'chunked', 'deleted')
            offset: Pagination offset
            limit: Maximum results
            
        Returns:
            List of PageInfo objects
        """
        self._check_initialized()
        return await self._doc_manager.list_pages(
            document_id=document_id,
            status=status,
            offset=offset,
            limit=limit
        )
    
    async def delete_page(
        self,
        page_id: int
    ) -> bool:
        """
        Delete a page (soft delete).
        
        Args:
            page_id: Page ID to delete
            
        Returns:
            True if successful
        """
        self._check_initialized()
        return await self._doc_manager.delete_page(page_id)
    
    # Chunking Operations
    
    async def process_pages(
        self,
        document_id: int,
        page_ids: List[int],
        chunk_size: Optional[int] = None
    ) -> ChunkProcessingResult:
        """
        Process pages for chunking and embedding.
        
        Validates pages, combines content, chunks, generates embeddings,
        and stores chunks with source page tracking.
        
        Args:
            document_id: Document ID
            page_ids: List of page IDs to process together
            chunk_size: Optional chunk size override
            
        Returns:
            ChunkProcessingResult with summary
        """
        self._check_initialized()
        return await self._doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            chunk_size=chunk_size
        )
    
    # Search Operations
    
    async def search(
        self,
        query: str,
        document_id: int,
        limit: int = 10,
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None
    ) -> List[ContentSearchResult]:
        """
        Search within document content using hybrid search.
        
        Args:
            query: Search query
            document_id: Document ID to search within
            limit: Maximum results
            vector_weight: Optional vector search weight (0-1)
            bm25_weight: Optional BM25 search weight (0-1)
            
        Returns:
            List of ContentSearchResult objects ranked by relevance
        """
        self._check_initialized()
        return await self._search_service.search_content(
            query=query,
            document_id=document_id,
            limit=limit,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight
        )
    
    async def search_across_versions(
        self,
        query: str,
        document_name: str,
        limit_per_version: int = 5
    ) -> dict[str, List[ContentSearchResult]]:
        """
        Search across all versions of a document.
        
        Args:
            query: Search query
            document_name: Document name
            limit_per_version: Maximum results per version
            
        Returns:
            Dict mapping version -> list of results
        """
        self._check_initialized()
        return await self._search_service.search_across_versions(
            query=query,
            document_name=document_name,
            limit_per_version=limit_per_version
        )
```

**Tasks:**
- [x] Implement ContextBridge class
- [x] Add all public methods with proper documentation
- [x] Add context manager support (`async with`)
- [x] Add initialization validation
- [x] Add comprehensive docstrings with examples
- [x] Write unit tests with mocked services
- [x] Write integration tests for end-to-end workflows
- [x] Create usage examples in docs

**Dependencies:** Phase 4.1, Phase 3  
**Testing:** 20+ unit tests, 10+ integration tests, example scripts

---

### Phase 5: Testing & Documentation 🧪 (Priority: Medium)

**Goal:** Ensure reliability and maintainability

#### 5.1 Unit Testing

**Files:** `tests/unit/test_*.py`

**Test Coverage Requirements:**

- [x] Repository layer: 80%+ coverage (77% overall, 81% chunk_repository)
- [x] Service layer: 80%+ coverage (89%+ for most services)
- [ ] Workflow layer: 70%+ coverage

**Test Categories:**

1. **Repository Tests** (with mocked DB)
   - [x] CRUD operations
   - [x] Query building
   - [x] Error handling
   - [x] Edge cases

2. **Service Tests** (with mocked dependencies)
   - [x] Business logic
   - [x] Validation
   - [x] Error handling
   - [x] Edge cases

3. **Workflow Tests** (with mocked services)
   - [x] Orchestration logic
   - [x] Error recovery
   - [x] Transaction handling

**Completed Tasks:**
- [x] Set up pytest configuration (pyproject.toml)
- [x] Create test fixtures (conftest.py with comprehensive mocks)
- [x] Write repository unit tests (document, page, chunk repositories)
- [x] Write service unit tests (all services implemented)
- [x] Write workflow unit tests (ContextBridge, DocManager)
- [x] Set up coverage reporting (term, html, xml)

**Current Status:**
- **Total Tests:** 240 unit tests
- **Passing:** 225+ tests
- **Coverage:** 77% overall (up from 70%)
- **Repository Coverage:** 81% chunk_repository, 99% document_repository, 66% page_repository
- **Service Coverage:** 89%+ for most services
- **Remaining Issues:** Some postgres_manager tests need fixes, page_repository coverage needs improvement

**Tasks:**
- [ ] Set up pytest configuration
- [ ] Create test fixtures
- [ ] Write repository unit tests
- [ ] Write service unit tests
- [ ] Write workflow unit tests
- [ ] Set up coverage reporting

**Reference Documentation:** `docs/technical/python-testing-guide.md`

---

#### 5.2 Integration Testing

**Files:** `tests/integration/test_*.py`

**Test Coverage Requirements:**

- [ ] Database operations: Full CRUD cycles
- [ ] End-to-end workflows: Happy path + error cases
- [ ] External service integration: Ollama, Crawl4AI

**Test Categories:**

1. **Database Integration**
   - Schema creation
   - Repository operations with real DB
   - Transaction behavior
   - Index performance

2. **Service Integration**
   - Embedding service with real Ollama
   - Crawling service with real sites
   - Search service with real data

3. **Workflow Integration**
   - Complete crawl-to-search workflow
   - Error recovery scenarios
   - Concurrent operations

**Tasks:**
- [ ] Set up test PostgreSQL database
- [ ] Create integration test fixtures
- [ ] Write database integration tests
- [ ] Write service integration tests
- [ ] Write workflow integration tests
- [ ] Set up CI/CD for automated testing

**Dependencies:** Phase 1-4  
**Testing:** 50+ integration tests

---

#### 5.3 API Documentation

**Files:** `docs/api/*.md`

**Documentation Requirements:**

- [ ] Repository API reference
- [ ] Service API reference
- [ ] Workflow API reference
- [ ] Configuration reference
- [ ] Example usage

**Tasks:**
- [ ] Generate API docs from docstrings
- [ ] Add usage examples for each component
- [ ] Create quickstart guide
- [ ] Create troubleshooting guide
- [ ] Add architecture diagrams

**Tools:** Sphinx or MkDocs

---

### Phase 6: Performance Optimization ⚡ (Priority: Low)

**Goal:** Optimize for production use

#### 6.1 Database Optimization

**Tasks:**
- [ ] Analyze query performance with EXPLAIN
- [ ] Optimize indexes based on usage patterns
- [ ] Add connection pool monitoring
- [ ] Implement query result caching
- [ ] Add database statistics logging

**Metrics:**
- Query response time < 100ms (95th percentile)
- Connection pool utilization < 80%
- Index hit ratio > 99%

---

#### 6.2 Embedding Optimization

**Tasks:**
- [ ] Implement embedding result caching
- [ ] Optimize batch embedding performance
- [ ] Add concurrent embedding generation
- [ ] Profile memory usage
- [ ] Add rate limiting for API calls

**Metrics:**
- Embedding generation < 200ms per chunk (Ollama)
- Batch embedding 5x faster than individual
- Cache hit ratio > 60%

---

#### 6.3 Search Optimization

**Tasks:**
- [ ] Implement search result caching
- [ ] Optimize hybrid search algorithm
- [ ] Add result pre-filtering
- [ ] Profile query execution time
- [ ] Implement pagination for large result sets

**Metrics:**
- Search response time < 500ms (95th percentile)
- Hybrid search accuracy > 85% (manual evaluation)

---

## 📊 Progress Tracking

### Overall Progress (v2.0 Architecture)

```
Phase 1: Database Foundation          [ ▰▰▰▰▱ ] 80% - Schema update pending
Phase 2: Repository Layer             [ ▰▰▰▰▱ ] 85% - Group removal pending
Phase 3: Service Layer                [ ▰▰▰▰▰ ] 100% - Completed
Phase 4: High-Level Services & API    [ ▰▰▰▰▰ ] 100% - Completed
Phase 5: Testing & Docs               [ ▰▰▱▱▱ ] 40% - Unit testing in progress
Phase 6: Optimization                 [ ▱▱▱▱▱ ]  0%

Total Progress:                       [ ▰▰▰▰▱ ] 75%
```

### Critical Path (Updated)

```
Phase 1.1 → Phase 1.2 → Phase 1.3
    ↓
Phase 2.1 → Phase 2.2 → Phase 2.3 (REMOVED) → Phase 2.4
    ↓
Phase 3.1 → Phase 3.2 → Phase 3.3 → Phase 3.4 → Phase 3.5
    ↓
Phase 4.1 (DocManager) → Phase 4.2 (ContextBridge)
    ↓
Phase 5.1 (Unit Testing - IN PROGRESS) → Phase 5.2
```
    ↓
Phase 6 (Parallel optimizations)
```

### Architectural Changes Summary

**Removed:**
- ❌ `page_groups` table
- ❌ `page_group_members` table
- ❌ `GroupRepository` class
- ❌ Group-based workflow

**Updated:**
- 🔄 `chunks` table: `group_id` → `source_page_ids` array
- 🔄 `pages.status`: 'grouped' → 'chunked'
- 🔄 `ChunkRepository`: Updated to use source_page_ids
- 🔄 `PageRepository`: Added content combining and validation methods

**Added:**
- ✅ `DocManager` service (high-level document operations)
- ✅ `ContextBridge` class (unified public API)
- ✅ Configuration fields for size validation
- ✅ Direct page-to-chunk workflow

---

## 🎯 Next Steps

### Immediate (Current Sprint)

**Priority 1: Database Schema Update**
- [ ] Update `context_bridge/schema/extensions.sql`:
  - Remove `page_groups` and `page_group_members` tables
  - Update `chunks` table schema (add `source_page_ids`, remove `group_id`)
  - Update `pages.status` constraint
- [ ] Run database migration script
- [ ] Verify schema changes

**Priority 2: Repository Updates**
- [ ] Update `PageRepository`:
  - Add `get_combined_content()` method
  - Add `validate_pages_for_chunking()` method
  - Update status values in existing methods
- [ ] Update `ChunkRepository`:
  - Update `create()` and `create_batch()` signatures
  - Remove `list_by_group()` method
  - Add `list_by_pages()` method
  - Update Chunk model

**Priority 3: Configuration**
- [ ] Add chunking configuration fields to `Config` class:
  - `chunk_size`
  - `min_combined_content_size`
  - `max_combined_content_size`

### Short-term (Week 1-2)

**Priority 4: DocManager Implementation**
- [ ] Create `context_bridge/service/doc_manager.py`
- [ ] Implement `crawl_and_store()` method
- [ ] Implement `list_pages()` method
- [ ] Implement `delete_page()` method
- [ ] Implement `process_chunking()` method with validation
- [ ] Write unit tests

**Priority 5: ContextBridge Implementation**
- [ ] Create `context_bridge/core.py`
- [ ] Implement ContextBridge class with all public methods
- [ ] Add initialization and cleanup logic
- [ ] Add context manager support
- [ ] Write comprehensive docstrings
- [ ] Write unit tests

### Medium-term (Week 3-4)

**Priority 6: Integration Testing**
- [ ] Write end-to-end integration tests
- [ ] Test complete workflow: crawl → list pages → chunk → search
- [ ] Test error handling and edge cases
- [ ] Performance testing with real documentation

**Priority 7: Documentation & Examples**
- [ ] Create usage examples for ContextBridge
- [ ] Update API documentation
- [ ] Create quickstart guide
- [ ] Add troubleshooting guide

### Long-term (Week 5+)

1. Performance optimization (Phase 6)
2. Prepare for MCP server integration
3. Prepare for Streamlit UI integration

---

## 🗑️ Cleanup Tasks

**Files to Remove:**
- [ ] `context_bridge/database/repositories/group_repository.py`
- [ ] `context_bridge/workflows/` directory (if exists)
- [ ] `tests/test_group_repository.py`
- [ ] `scripts/test_group_repo.py`

**Files to Update:**
- [ ] Any imports of `GroupRepository`
- [ ] Any references to `page_groups` in tests
- [ ] Documentation mentioning grouping workflow

---

## 📚 Reference Documentation

**Internal Documents:**
- `docs/technical/crawl4ai_complete_guide.md` - Web crawling
- `docs/technical/embedding_service.md` - Embedding generation
- `docs/technical/psqlpy-complete-guide.md` - PostgreSQL operations
- `docs/technical/python_mcp_server_guide.md` - MCP server (future)
- `docs/technical/python-testing-guide.md` - Testing best practices
- `docs/technical/smart_chunk_markdown_algorithm.md` - Chunking algorithm

**External Resources:**
- PSQLPy: https://github.com/qaspen-python/psqlpy
- Crawl4AI: https://github.com/unclecode/crawl4ai
- pgvector: https://github.com/pgvector/pgvector
- Pydantic: https://docs.pydantic.dev

---

## 🔧 Development Environment Setup

### Prerequisites

```bash
# Python 3.11+
python --version

# PostgreSQL 14+ with extensions
psql --version

# Ollama (for local embeddings)
ollama --version
```

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd context_bridge

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Create .env file
cp .env.example .env
# Edit .env with your settings

# Initialize database
python -m context_bridge.database.init_databases

# Run tests
pytest
```

---

## ✅ Definition of Done

A phase is considered complete when:

- [ ] All code is implemented and reviewed
- [ ] All unit tests pass with >80% coverage
- [ ] All integration tests pass
- [ ] Code follows style guide (Black, Ruff)
- [ ] Type hints are complete (mypy passes)
- [ ] Documentation is updated
- [ ] API reference is generated
- [ ] Example usage is provided
- [ ] Performance metrics are met (if applicable)

---

## 📝 Change Log

### Version 2.0 (October 12, 2025)

**Major Architecture Revision:**

**Removed:**
- Page grouping concept (tables, repository, workflow)
- `page_groups` and `page_group_members` database tables
- `GroupRepository` class
- Complex group-based chunking workflow

**Added:**
- `DocManager` service for high-level document operations
- `ContextBridge` class as unified public API
- Direct page selection for chunking workflow
- Configuration-based size validation for combined content
- `source_page_ids` tracking in chunks table

**Simplified:**
- Workflow: Pages → Chunks (no intermediate grouping)
- User provides list of page IDs for chunking
- Validation moved to repository layer
- Single entry point via ContextBridge class

**Rationale:**
- Eliminate unnecessary complexity of page grouping
- Provide simpler, more flexible user experience
- Maintain all original capabilities with cleaner architecture
- Better separation of concerns between layers

### Version 1.0 (October 11, 2025)

**Initial Implementation Plan:**
- Defined 6-phase implementation approach
- Completed Phases 1-3 (Database, Repositories, Services)
- Established group-based workflow architecture

---

**Document Status:** Living document - update as implementation progresses

**Last Review:** October 12, 2025

**Next Review:** Weekly during active development
