# Context Bridge - Core Implementation Plan

**Version:** 1.0  
**Last Updated:** October 11, 2025  
**Status:** Active Implementation - Phase 3.2 Completed

---

## 📋 Document Overview

This document outlines the complete implementation plan for the **Context Bridge** core package, focusing on the essential functionality needed for crawling, storing, chunking, and searching technical documentation with RAG capabilities.

**Scope:**
- ✅ Core Python package implementation
- ✅ Database schema and initialization
- ✅ Repository layer (data access)
- ✅ Service layer (business logic)
- ✅ Complete crawling workflow
- ❌ MCP server (separate phase)
- ❌ Streamlit UI (separate phase)

---

## 🎯 Project Goals

### Primary Objectives

1. **Enable intelligent documentation crawling** with automatic type detection (webpages, sitemaps, text files)
2. **Store raw crawled content** with deduplication and metadata tracking
3. **Provide manual page organization** with size-constrained grouping
4. **Implement smart Markdown chunking** that preserves code blocks and structure
5. **Generate and store embeddings** with dual vector + BM25 indexing
6. **Enable hybrid search** combining vector similarity and BM25 full-text search
7. **Support document versioning** for multiple versions of the same documentation

### Success Criteria

- [ ] Successfully crawl and store 1000+ pages from technical documentation sites
- [ ] Chunk content with >95% preservation of code block integrity
- [ ] Achieve <500ms average search response time for hybrid queries
- [ ] Support concurrent operations with connection pooling
- [ ] Maintain type safety throughout with Pydantic models
- [ ] Provide comprehensive test coverage (>80%)

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer Architecture                        │
└─────────────────────────────────────────────────────────────┘

Layer 1: Configuration
├── config.py (Pydantic models, environment variables)

Layer 2: Database Foundation
├── postgres_manager.py (Connection pooling, context managers)
├── init_databases.py (Schema initialization)
└── schema/extensions.sql (SQL schema definitions)

Layer 3: Repository Layer (Data Access)
├── document_repository.py (CRUD for documents)
├── page_repository.py (CRUD for crawled pages)
├── group_repository.py (Page grouping logic)
└── chunk_repository.py (Chunk storage and hybrid search)

Layer 4: Service Layer (Business Logic)
├── url_service.py (URL parsing and type detection)
├── crawling_service.py (Orchestrate crawling workflow)
├── chunking_service.py (Smart Markdown chunking)
├── embedding.py (Generate embeddings via Ollama/Gemini)
└── search_service.py (Orchestrate hybrid search)

Layer 5: External Dependencies
├── PSQLPy (PostgreSQL driver)
├── Crawl4AI (Web crawling)
├── Ollama/Gemini (Embeddings)
└── PostgreSQL Extensions (pgvector, vchord_bm25)
```

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
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'grouped', 'deleted')),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Table: page_groups (manual organization)
CREATE TABLE IF NOT EXISTS page_groups (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    name TEXT,
    total_size INTEGER,
    page_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'eligible' CHECK (status IN ('eligible', 'processed'))
);

-- Table: page_group_members (many-to-many)
CREATE TABLE IF NOT EXISTS page_group_members (
    group_id INTEGER NOT NULL REFERENCES page_groups(id) ON DELETE CASCADE,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id, page_id)
);

-- Table: chunks (embedded content)
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    group_id INTEGER REFERENCES page_groups(id) ON DELETE SET NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768), -- Dimension must match config
    bm25_vector bm25vector, -- Auto-generated by trigger
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, group_id, chunk_index)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pages_document ON pages(document_id);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_hash ON pages(content_hash);

CREATE INDEX IF NOT EXISTS idx_groups_document ON page_groups(document_id);
CREATE INDEX IF NOT EXISTS idx_groups_status ON page_groups(status);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_group ON chunks(group_id);
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

**Tasks:**
- [x] Review existing `extensions.sql`
- [x] Add missing tables (page_groups, page_group_members)
- [x] Add comprehensive indexes
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

### Phase 2: Repository Layer 🗄️ (Priority: Critical)

**Goal:** Create type-safe data access layer with PSQLPy

#### 2.1 Document Repository

**File:** `context_bridge/database/repositories/document_repository.py`

**Implementation:**

```python
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from psqlpy import Connection

class Document(BaseModel):
    """Document model."""
    id: int
    name: str
    version: str
    source_url: Optional[str]
    description: Optional[str]
    metadata: dict
    created_at: datetime
    updated_at: datetime

class DocumentRepository:
    """Repository for document operations."""
    
    def __init__(self, connection: Connection):
        self.conn = connection
    
    async def create(
        self,
        name: str,
        version: str,
        source_url: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> int:
        """Create a new document and return its ID."""
        
    async def get_by_id(self, doc_id: int) -> Optional[Document]:
        """Get document by ID."""
        
    async def get_by_name_version(self, name: str, version: str) -> Optional[Document]:
        """Get document by name and version."""
        
    async def find_by_query(
        self,
        query: str,
        limit: int = 10
    ) -> List[Document]:
        """Find documents by text query (searches name, description)."""
        
    async def list_all(
        self,
        offset: int = 0,
        limit: int = 100
    ) -> List[Document]:
        """List all documents with pagination."""
        
    async def list_versions(self, name: str) -> List[str]:
        """Get all versions of a document."""
        
    async def update(
        self,
        doc_id: int,
        **fields
    ) -> bool:
        """Update document fields."""
        
    async def delete(self, doc_id: int) -> bool:
        """Delete document and cascade to all related data."""
```

**Tasks:**
- [x] Implement all CRUD methods
- [x] Add query builder for find_by_query
- [x] Add proper error handling
- [x] Add dataclass to/from row conversion
- [x] Write comprehensive unit tests with mocks
- [x] Write integration tests with test database

**Dependencies:** Phase 1.1, 1.2  
**Testing:** 15+ unit tests, 5+ integration tests

---

#### 2.2 Page Repository

**File:** `context_bridge/database/repositories/page_repository.py`

**Implementation:**

```python
from typing import Optional, List, Set
from pydantic import BaseModel, Field
from datetime import datetime
from psqlpy import Connection

class Page(BaseModel):
    """Page model."""
    id: int
    document_id: int
    url: str
    content: str
    content_hash: str
    content_length: int
    crawled_at: datetime
    status: str  # pending, grouped, deleted
    metadata: dict

class PageRepository:
    """Repository for page operations."""
    
    def __init__(self, connection: Connection):
        self.conn = connection
    
    async def create(
        self,
        document_id: int,
        url: str,
        content: str,
        content_hash: str,
        metadata: Optional[dict] = None
    ) -> int:
        """Create a page. Returns ID or existing ID if duplicate URL."""
        
    async def get_by_id(self, page_id: int) -> Optional[Page]:
        """Get page by ID."""
        
    async def get_by_url(self, url: str) -> Optional[Page]:
        """Get page by URL."""
        
    async def list_by_document(
        self,
        document_id: int,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[Page]:
        """List pages for a document, optionally filtered by status."""
        
    async def count_by_document(
        self,
        document_id: int,
        status: Optional[str] = None
    ) -> int:
        """Count pages for a document."""
        
    async def update_status(
        self,
        page_id: int,
        status: str
    ) -> bool:
        """Update page status."""
        
    async def update_status_bulk(
        self,
        page_ids: List[int],
        status: str
    ) -> int:
        """Update status for multiple pages. Returns count updated."""
        
    async def delete(self, page_id: int) -> bool:
        """Soft delete (mark as deleted)."""
        
    async def delete_bulk(self, page_ids: List[int]) -> int:
        """Soft delete multiple pages. Returns count deleted."""
        
    async def check_duplicates(
        self,
        content_hashes: List[str]
    ) -> Set[str]:
        """Check which content hashes already exist. Returns set of existing hashes."""
```

**Tasks:**
- [x] Implement all CRUD methods
- [x] Add bulk operations for efficiency
- [x] Add deduplication logic
- [x] Add status transition validation
- [x] Write unit tests
- [x] Write integration tests

**Dependencies:** Phase 2.1  
**Testing:** 20+ unit tests, 8+ integration tests

---

#### 2.3 Group Repository

**File:** `context_bridge/database/repositories/group_repository.py`

**Implementation:**

```python
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime
from psqlpy import Connection

class PageGroup(BaseModel):
    """Page group model."""
    id: int
    document_id: int
    name: Optional[str]
    total_size: int
    page_count: int
    created_at: datetime
    status: str  # eligible, processed

class GroupWithPages(BaseModel):
    """Group with its member pages."""
    group: PageGroup
    page_ids: List[int]

class GroupRepository:
    """Repository for page group operations."""
    
    def __init__(self, connection: Connection):
        self.conn = connection
    
    async def create_group(
        self,
        document_id: int,
        page_ids: List[int],
        name: Optional[str] = None
    ) -> int:
        """
        Create a group from pages.
        Validates:
        - All pages belong to the same document
        - All pages have status 'pending'
        - Updates pages to status 'grouped'
        Returns group ID.
        """
        
    async def get_by_id(self, group_id: int) -> Optional[PageGroup]:
        """Get group by ID."""
        
    async def get_with_pages(self, group_id: int) -> Optional[GroupWithPages]:
        """Get group with its member page IDs."""
        
    async def list_by_document(
        self,
        document_id: int,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[PageGroup]:
        """List groups for a document."""
        
    async def get_eligible_groups(
        self,
        document_id: int,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None
    ) -> List[PageGroup]:
        """
        Get groups eligible for chunking.
        Filters by status='eligible' and optional size constraints.
        """
        
    async def get_group_content(self, group_id: int) -> str:
        """
        Get combined content of all pages in group.
        Pages are ordered by ID and joined with '\\n\\n---\\n\\n'.
        """
        
    async def update_status(
        self,
        group_id: int,
        status: str
    ) -> bool:
        """Update group status."""
        
    async def ungroup(self, group_id: int) -> bool:
        """
        Dissolve a group:
        - Set member pages back to 'pending'
        - Delete group
        Returns True if successful.
        """
        
    async def delete(self, group_id: int) -> bool:
        """Delete group (cascades to members via FK)."""
        
    async def validate_group_constraints(
        self,
        page_ids: List[int],
        min_size: Optional[int] = None,
        max_size: Optional[int] = None
    ) -> Tuple[bool, Optional[str], int]:
        """
        Validate if pages can form a valid group.
        Returns: (is_valid, error_message, total_size)
        """
```

**Tasks:**
- [x] Implement group creation with validation
- [x] Implement content concatenation logic
- [x] Add transaction support for atomic operations
- [x] Add constraint validation
- [x] Write unit tests
- [x] Write integration tests

**Status:** ✅ **COMPLETED**  
**Dependencies:** Phase 2.2  
**Testing:** 24 unit tests, 10+ integration tests

---

#### 2.4 Chunk Repository

**File:** `context_bridge/database/repositories/chunk_repository.py`

**Implementation:**

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from psqlpy.extra_types import PgVector

from context_bridge.database.postgres_manager import PostgreSQLManager

class Chunk(BaseModel):
    """Chunk model."""
    id: int
    document_id: int
    group_id: Optional[int]
    chunk_index: int
    content: str
    embedding: List[float]
    created_at: datetime

class SearchResult(BaseModel):
    """Search result with relevance score."""
    chunk: Chunk
    score: float
    rank: int

class ChunkRepository:
    """Repository for chunk operations with hybrid search."""
    
    def __init__(self, db_manager: PostgreSQLManager):
        self.db_manager = db_manager
    
    async def create(
        self,
        document_id: int,
        group_id: Optional[int],
        chunk_index: int,
        content: str,
        embedding: List[float]
    ) -> int:
        """
        Create a chunk with embedding.
        BM25 vector is auto-generated by trigger.
        """
        
    async def create_batch(
        self,
        chunks: List[dict]
    ) -> List[int]:
        """Create multiple chunks efficiently. Returns list of IDs."""
        
    async def get_by_id(self, chunk_id: int) -> Optional[Chunk]:
        """Get chunk by ID."""
        
    async def list_by_document(
        self,
        document_id: int,
        offset: int = 0,
        limit: int = 100
    ) -> List[Chunk]:
        """List chunks for a document."""
        
    async def list_by_group(
        self,
        group_id: int
    ) -> List[Chunk]:
        """Get all chunks for a group, ordered by chunk_index."""
        
    async def count_by_document(self, document_id: int) -> int:
        """Count chunks for a document."""
        
    async def vector_search(
        self,
        document_id: int,
        query_embedding: List[float],
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[SearchResult]:
        """
        Vector similarity search using pgvector.
        Returns chunks ordered by cosine similarity.
        """
        
    async def bm25_search(
        self,
        document_id: int,
        query: str,
        limit: int = 10
    ) -> List[SearchResult]:
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

### Phase 4: Workflow Integration 🔄 (Priority: High)

**Goal:** Create end-to-end workflows

#### 4.1 Complete Crawling Workflow

**File:** `context_bridge/workflows/crawling_workflow.py`

**Implementation:**

```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class CrawlWorkflowResult(BaseModel):
    """Result of complete crawl workflow."""
    document_id: int
    pages_crawled: int
    pages_stored: int
    duplicates_skipped: int
    errors: int

class CrawlingWorkflow:
    """Orchestrate complete crawling workflow."""
    
    def __init__(
        self,
        db_manager: PostgreSQLManager,
        crawling_service: CrawlingService,
        config: CrawlConfig
    ):
        self.db_manager = db_manager
        self.crawling_service = crawling_service
        self.config = config
    
    async def crawl_and_store_documentation(
        self,
        name: str,
        version: str,
        source_url: str,
        description: Optional[str] = None
    ) -> CrawlWorkflowResult:
        """
        Complete workflow:
        1. Create or get document
        2. Crawl source URL
        3. Store pages (skip duplicates)
        4. Return summary
        """
        
        logger.info(f"Starting crawl workflow for {name} v{version}")
        
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
            
            # Crawl
            async with AsyncWebCrawler(verbose=True) as crawler:
                crawl_result = await self.crawling_service.crawl_webpage(
                    crawler, source_url
                )
            
            # Store pages
            stored = 0
            duplicates = 0
            errors = 0
            
            for page in crawl_result.results:
                try:
                    # Check for duplicate
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
            
            return CrawlWorkflowResult(
                document_id=doc_id,
                pages_crawled=len(crawl_result.results),
                pages_stored=stored,
                duplicates_skipped=duplicates,
                errors=errors
            )
```

**Tasks:**
- [ ] Implement complete workflow method
- [ ] Add transaction support
- [ ] Add progress reporting
- [ ] Add error recovery
- [ ] Write integration tests

**Dependencies:** Phase 2, 3  
**Testing:** 10+ integration tests

---

#### 4.2 Chunking Workflow

**File:** `context_bridge/workflows/chunking_workflow.py`

**Implementation:**

```python
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class ChunkWorkflowResult(BaseModel):
    """Result of chunking workflow."""
    document_id: int
    groups_processed: int
    chunks_created: int
    errors: int

class ChunkingWorkflow:
    """Orchestrate chunking and embedding workflow."""
    
    def __init__(
        self,
        db_manager: PostgreSQLManager,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        chunk_size: int = 2000
    ):
        self.db_manager = db_manager
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.chunk_size = chunk_size
    
    async def process_group(
        self,
        group_id: int
    ) -> int:
        """
        Process a single group:
        1. Get group content
        2. Chunk content
        3. Generate embeddings
        4. Store chunks
        5. Mark group as processed
        Returns number of chunks created.
        """
        
    async def process_document(
        self,
        document_id: int,
        group_status_filter: str = 'eligible'
    ) -> ChunkWorkflowResult:
        """
        Process all eligible groups for a document.
        """
        
        logger.info(f"Starting chunking workflow for document {document_id}")
        
        async with self.db_manager.connection() as conn:
            group_repo = GroupRepository(conn)
            chunk_repo = ChunkRepository(conn)
            
            # Get eligible groups
            groups = await group_repo.list_by_document(
                document_id,
                status=group_status_filter
            )
            
            total_chunks = 0
            errors = 0
            
            for group in groups:
                try:
                    # Get content
                    content = await group_repo.get_group_content(group.id)
                    
                    # Chunk
                    chunks = self.chunking_service.smart_chunk_markdown(
                        content,
                        chunk_size=self.chunk_size
                    )
                    
                    # Generate embeddings and store
                    for i, chunk_text in enumerate(chunks):
                        try:
                            embedding = await self.embedding_service.get_embedding(
                                chunk_text
                            )
                            
                            await chunk_repo.create(
                                document_id=document_id,
                                group_id=group.id,
                                chunk_index=i,
                                content=chunk_text,
                                embedding=embedding
                            )
                            total_chunks += 1
                            
                        except Exception as e:
                            logger.error(f"Error creating chunk {i} for group {group.id}: {e}")
                            errors += 1
                    
                    # Mark group as processed
                    await group_repo.update_status(group.id, 'processed')
                    
                except Exception as e:
                    logger.error(f"Error processing group {group.id}: {e}")
                    errors += 1
            
            logger.info(
                f"Chunking complete: {len(groups)} groups, "
                f"{total_chunks} chunks, {errors} errors"
            )
            
            return ChunkWorkflowResult(
                document_id=document_id,
                groups_processed=len(groups),
                chunks_created=total_chunks,
                errors=errors
            )
```

**Tasks:**
- [ ] Implement group processing
- [ ] Implement document processing
- [ ] Add batch embedding for efficiency
- [ ] Add transaction support
- [ ] Add error recovery
- [ ] Write integration tests

**Dependencies:** Phase 2, 3  
**Testing:** 8+ integration tests

---

### Phase 5: Testing & Documentation 🧪 (Priority: Medium)

**Goal:** Ensure reliability and maintainability

#### 5.1 Unit Testing

**Files:** `tests/unit/test_*.py`

**Test Coverage Requirements:**

- [ ] Repository layer: 80%+ coverage
- [ ] Service layer: 80%+ coverage
- [ ] Workflow layer: 70%+ coverage

**Test Categories:**

1. **Repository Tests** (with mocked DB)
   - CRUD operations
   - Query building
   - Error handling
   - Edge cases

2. **Service Tests** (with mocked dependencies)
   - Business logic
   - Validation
   - Error handling
   - Edge cases

3. **Workflow Tests** (with mocked services)
   - Orchestration logic
   - Error recovery
   - Transaction handling

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

### Overall Progress

```
Phase 1: Database Foundation    [ ▰▰▰▰▱ ] 80%
Phase 2: Repository Layer       [ ▰▰▰▰▱ ] 80%
Phase 3: Service Layer          [ ▰▰▰▰▱ ] 80%
Phase 4: Workflow Integration   [ ▱▱▱▱▱ ]  0%
Phase 5: Testing & Docs         [ ▱▱▱▱▱ ]  0%
Phase 6: Optimization           [ ▱▱▱▱▱ ]  0%

Total Progress:                 [ ▰▰▰▰▱ ] 70%
```

### Critical Path

```
Phase 1.1 → Phase 1.2 → Phase 1.3
    ↓
Phase 2.1 → Phase 2.2 → Phase 2.3 → Phase 2.4
    ↓
Phase 3.2 → Phase 3.3 → Phase 3.4 → Phase 3.5
    ↓
Phase 4.1 → Phase 4.2
    ↓
Phase 5.1 → Phase 5.2
    ↓
Phase 6 (Parallel optimizations)
```

---

## 🎯 Next Steps

### Immediate (Week 1-2)

1. ✅ Complete database schema (Phase 1.1)
2. ✅ Enhance PostgreSQL manager (Phase 1.2)
3. ✅ Update initialization script (Phase 1.3)
4. ✅ Complete document repository (Phase 2.1)
5. ✅ Complete page repository (Phase 2.2)
6. ✅ Complete group repository (Phase 2.3)
7. ✅ Complete chunk repository (Phase 2.4)
8. ✅ Complete crawling service enhancement (Phase 3.2)
9. ✅ Complete chunking service (Phase 3.3)
10. ✅ Complete embedding service enhancement (Phase 3.4)
11. ▶️ Start search service implementation (Phase 3.5)

### Short-term (Week 3-4)

1. Complete all repositories (Phase 2)
2. Validate existing services (Phase 3)
3. Implement new services (Phase 3)

### Medium-term (Week 5-8)

1. Build workflow integrations (Phase 4)
2. Write comprehensive tests (Phase 5)
3. Create API documentation (Phase 5)

### Long-term (Week 9+)

1. Performance optimization (Phase 6)
2. Prepare for MCP server integration
3. Prepare for Streamlit UI integration

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

**Document Status:** Living document - update as implementation progresses

**Last Review:** October 12, 2025

**Next Review:** Weekly during active development
