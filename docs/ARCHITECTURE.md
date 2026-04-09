# Context Bridge Architecture

**Version:** 0.2.0  
**Last Updated:** November 2025

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architectural Layers](#architectural-layers)
3. [Component Responsibilities](#component-responsibilities)
4. [Data Flow](#data-flow)
5. [Design Patterns](#design-patterns)
6. [Database Schema](#database-schema)
7. [Phase Architecture](#phase-architecture)
8. [Security Considerations](#security-considerations)
9. [Scalability Strategy](#scalability-strategy)
10. [Deployment Architecture](#deployment-architecture)

---

## System Overview

Context Bridge is a modular, async-first Python application that enables intelligent document processing and retrieval. The system is organized into distinct phases, each adding capabilities:

- **Phase 1:** Tags System - Document organization and categorization
- **Phase 2:** Groups Management - Logical page grouping within documents
- **Phase 3:** AI Context Generation - LLM-powered semantic enhancement
- **Phase 4:** Re-processing - Batch operations on existing data
- **Phase 5:** Integration & Testing - System validation and optimization

### Core Principles

1. **Async-First:** All I/O operations are non-blocking using asyncio
2. **Modular:** Each phase is independent and can be enabled/disabled
3. **Database-Centric:** PostgreSQL with pgvector is the source of truth
4. **Type-Safe:** Full type hints throughout codebase
5. **Testable:** Comprehensive unit and integration test coverage

---

## Architectural Layers

### Layer 1: Interface Layer

**Responsibility:** User interaction and system integration

**Components:**
- **Streamlit App** (`streamlit_app/`)
  - Multi-page web UI for document management
  - Real-time search and tag management
  - Group monitoring and re-processing
  - Interactive visualization

- **MCP Server** (`context_bridge_mcp/`)
  - Language Model Protocol integration
  - Claude/LLM tool interface
  - Programmatic API access
  - Tool-based architecture

**API Contracts:**
```python
# Streamlit pages handle HTTP requests
# MCP server handles tool calls
# Both interact with core layer
```

### Layer 2: Core Application Layer

**Responsibility:** Business logic and orchestration

**Components:**
- **ContextBridge** (`context_bridge/core.py`)
  - Main application class
  - Public API surface
  - Service orchestration
  - Request routing

- **Services** (`context_bridge/service/`)
  - `DocManager` - Document lifecycle management
  - `CrawlingService` - URL content fetching
  - `ChunkingService` - Content segmentation
  - `EmbeddingService` - Vector generation
  - `SearchService` - Hybrid search
  - `ContextGenerationAgent` - LLM context creation
  - `ReprocessingService` - Batch re-processing

**Key Operations:**
```
Request → Core → Service Selection → Execution → Response
```

### Layer 3: Data Access Layer

**Responsibility:** Database interaction and data persistence

**Components:**
- **Repositories** (`context_bridge/database/repositories/`)
  - `DocumentRepository` - Document CRUD
  - `PageRepository` - Page management (with group support)
  - `ChunkRepository` - Chunk storage and search
  - `TagRepository` - Tag and document-tag operations
  - `GroupRepository` - Group lifecycle

- **Models** (`context_bridge/database/models/`)
  - Pydantic models with validation
  - Type definitions and enums
  - Data transformation

- **Database Manager** (`context_bridge/database/postgres_manager.py`)
  - Connection pooling
  - Transaction management
  - Query execution

**Pattern:**
```
Service → Repository → PostgreSQL
```

### Layer 4: Infrastructure Layer

**Responsibility:** Configuration and system resources

**Components:**
- **Configuration** (`context_bridge/config.py`)
  - Environment variable handling
  - Validation and defaults
  - Feature flags

- **Database** (`context_bridge/database/`)
  - Schema management
  - Migrations
  - Indexes and constraints

---

## Component Responsibilities

### DocumentRepository

**Responsibility:** Manage document metadata and lifecycle

**Key Methods:**
- `create_document()` - Create new document entry
- `get_document()` - Retrieve document with metadata
- `list_documents()` - List all documents with pagination
- `delete_document()` - Remove document (cascade to pages/chunks)
- `update_document()` - Modify document metadata

**Database Table:** `documents`

### PageRepository

**Responsibility:** Manage pages and their associations

**Key Methods:**
- `create_page()` - Add page to document
- `get_pages_for_document()` - Retrieve all pages
- `get_pages_for_group()` - Retrieve pages in group (Phase 2)
- `update_page_group()` - Assign page to group (Phase 2)
- `update_page_status()` - Track processing status

**Database Table:** `pages`

### ChunkRepository

**Responsibility:** Store chunks and enable semantic search

**Key Methods:**
- `create_chunk()` - Store chunk with embedding
- `search_chunks()` - Hybrid vector + BM25 search
- `get_chunks_for_document()` - Retrieve all chunks
- `get_chunks_for_group()` - Retrieve group chunks (Phase 2)
- `delete_by_group()` - Batch delete chunks (Phase 4)
- `search_chunks_in_group()` - Group-scoped search (Phase 2)

**Database Table:** `chunks`

**Indexes:**
- `idx_chunks_embedding` - Vector similarity search
- `idx_chunks_document` - Document filtering
- `idx_chunks_bm25_content` - Full-text search

### TagRepository

**Responsibility:** Manage tags and document-tag relationships

**Key Methods:**
- `list_tags()` - Get all available tags
- `get_predefined_tags()` - Get 48 built-in tags
- `add_tags_to_document()` - Associate tags with document
- `remove_tag_from_document()` - Remove tag association
- `get_document_tags()` - Get tags for document
- `search_by_tags()` - Find documents by tags

**Database Tables:**
- `tags` - Tag definitions
- `document_tags` - Document-tag associations

### GroupRepository

**Responsibility:** Manage page groups and their metadata

**Key Methods:**
- `create_group()` - Create new group
- `get_group_by_id()` - Retrieve group with stats
- `list_groups_for_document()` - Get all groups in document
- `update_group()` - Modify group properties
- `delete_group()` - Remove group (cascade behavior)
- `get_group_chunk_statistics()` - Aggregated stats

**Database Table:** `groups`

### Services

#### DocManager

**Responsibility:** Orchestrate document processing workflows

**Key Methods:**
- `import_from_url()` - Crawl and process URL
- `process_pages()` - Chunk and embed pages
- `process_group()` - Process group with optional context (Phase 2)
- `reprocess_group()` - Re-process existing group (Phase 4)

**Workflow:**
```
URL → Crawl → Chunk → Embed → Store
              ↓
         (optional) Generate Context → Store
```

#### CrawlingService

**Responsibility:** Fetch and extract content from URLs

**Features:**
- Async HTTP fetching with timeouts
- JavaScript rendering support
- HTML to Markdown conversion
- Link extraction and validation
- Error handling and retry logic

**Output:** Markdown content

#### ChunkingService

**Responsibility:** Split content into manageable pieces

**Features:**
- Configurable chunk size (default: 512 tokens)
- Overlap for context preservation
- Markdown-aware chunking
- Metadata preservation

**Output:** List of Chunk objects with content and metadata

#### EmbeddingService

**Responsibility:** Convert text to vector embeddings

**Features:**
- Async embedding generation
- Batch processing support
- Model: all-MiniLM-L6-v2 (384 dimensions)
- Caching for identical inputs
- Error handling and fallbacks

**Output:** 384-dimensional vectors

#### SearchService

**Responsibility:** Execute hybrid searches

**Hybrid Search Formula:**
```
score = (VECTOR_WEIGHT * vector_score) + (BM25_WEIGHT * bm25_score)
```

**Configuration:**
- `VECTOR_WEIGHT` = 0.7 (default)
- `BM25_WEIGHT` = 0.3 (default)
- Configurable via environment variables

**Output:** Ranked search results with relevance scores

#### ContextGenerationAgent

**Responsibility:** Generate AI-powered context for chunks

**Features:**
- Multiple LLM provider support (Anthropic, OpenAI)
- Batch processing with concurrency limits
- Prompt caching for cost optimization
- Configurable temperature and token limits
- Error handling with graceful degradation

**Output:** Context strings prepended to chunks

#### ReprocessingService

**Responsibility:** Update existing groups with new context

**Workflow:**
```
1. Validate group exists
2. Update status → REPROCESSING
3. Delete existing chunks
4. Retrieve pages
5. Chunk content
6. Generate context (if enabled)
7. Generate embeddings
8. Store new chunks
9. Update status → COMPLETED
```

**Output:** Updated group with new chunks

---

## Data Flow

### Document Ingestion Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    Document Upload                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              CrawlingService                                │
│  URL → HTML Fetching → Markdown Conversion → Validation    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              ChunkingService                                │
│  Markdown → Tokenization → Chunk Boundaries → Segment      │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
    ┌─────────────────┐   ┌──────────────────┐
    │ EmbeddingService│   │ TaggingService   │
    │ Text → Vector   │   │ Assign Tags      │
    └────────┬────────┘   └────────┬─────────┘
             │                     │
             └───────────┬─────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────┐
    │  ChunkRepository.create_chunk()         │
    │  Store: chunk, embedding, tags, group   │
    └─────────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────┐
    │  (Optional) ContextGenerationAgent      │
    │  If context_enabled:                    │
    │    - Generate context for chunk         │
    │    - Prepend context to content         │
    │    - Update chunk in database           │
    └─────────────────────────────────────────┘
```

### Search Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    Search Query                             │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
    ┌──────────────────┐  ┌──────────────────┐
    │ Vector Search    │  │ BM25 Search      │
    │ Query → Embed    │  │ Full-text index  │
    │ Find similar     │  │ Term matching    │
    └────────┬─────────┘  └────────┬─────────┘
             │                     │
             └───────────┬─────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────┐
    │  Score Combination                      │
    │  hybrid_score = (0.7 * vec) + (0.3 * bm25)
    └─────────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────┐
    │  Result Ranking & Filtering             │
    │  Sort by score, apply filters, limit    │
    └─────────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────┐
    │  Return Results                         │
    │  Format for UI/API/MCP                  │
    └─────────────────────────────────────────┘
```

### Re-processing Pipeline

```
┌──────────────────────────────────────────┐
│  Reprocess Group Request                 │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│  Validate & Update Status                │
│  PENDING → REPROCESSING                  │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│  Delete Existing Chunks                  │
│  WHERE group_id = target_group           │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│  Retrieve Pages in Group                 │
│  Get content from pages                  │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│  Re-chunk & Re-embed                     │
│  Same process as initial ingestion       │
└────────────────────┬─────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼ (if context enabled)  │
┌──────────────────────────────┐ │
│ Generate Context             │ │
│ Create semantic summaries    │ │
└────────────────┬─────────────┘ │
                 │               │
                 └───────┬───────┘
                         │
                         ▼
┌──────────────────────────────────────────┐
│  Store New Chunks                        │
│  UPDATE group status → COMPLETED         │
└──────────────────────────────────────────┘
```

---

## Design Patterns

### 1. Repository Pattern

**Purpose:** Isolate data access logic

**Implementation:**
```python
class ChunkRepository:
    async def create_chunk(self, chunk: Chunk) -> Chunk:
        # Handle database operation
        
    async def search_chunks(self, query: str) -> List[SearchResult]:
        # Handle search logic
```

**Benefits:**
- Testability (mock repository in tests)
- Consistency (single source of data access)
- Flexibility (swap implementations)

### 2. Service Pattern

**Purpose:** Encapsulate business logic

**Implementation:**
```python
class DocManager:
    async def import_from_url(self, url: str) -> Document:
        # Orchestrate: crawl → chunk → embed → store
        
    async def process_group(self, group_id: UUID) -> dict:
        # Orchestrate: retrieve → process → update
```

**Benefits:**
- Separation of concerns
- Reusability across interfaces
- Testability of workflows

### 3. Dependency Injection

**Purpose:** Decouple components

**Implementation:**
```python
class DocManager:
    def __init__(
        self,
        db_manager: PostgreSQLManager,
        crawling_service: CrawlingService,
        embedding_service: EmbeddingService,
        config: Config,
    ):
        self.db_manager = db_manager
        self.crawling_service = crawling_service
        # ...
```

**Benefits:**
- Easy testing (inject mocks)
- Flexible configuration
- Clear dependencies

### 4. Factory Pattern

**Purpose:** Create objects based on configuration

**Implementation:**
```python
class ModelProvider:
    def get_model(self, model_info: str) -> Model:
        provider_name, model_name = model_info.split(":", 1)
        model_class = self.PROVIDER_MODEL_MAPPING[provider_name]
        return model_class(model_name, api_key=...)
```

**Benefits:**
- Flexible model selection
- Runtime configuration
- Support for multiple providers

### 5. Async/Await Pattern

**Purpose:** Non-blocking I/O throughout

**Implementation:**
```python
async def process_pages(self, page_ids: List[int]):
    tasks = [
        self.chunking_service.chunk_page(page_id)
        for page_id in page_ids
    ]
    results = await asyncio.gather(*tasks)
    return results
```

**Benefits:**
- Scalability (handle many concurrent requests)
- Performance (efficient resource usage)
- Responsiveness (UI stays responsive)

---

## Database Schema

### Core Tables

#### documents
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    url VARCHAR(2048),
    content_hash VARCHAR(64),
    document_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);
```

#### pages
```sql
CREATE TABLE pages (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER,
    url VARCHAR(2048),
    title VARCHAR(255),
    content TEXT,
    processing_status VARCHAR(20) DEFAULT 'pending',
    group_id UUID REFERENCES groups(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### chunks
```sql
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id INTEGER REFERENCES pages(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    context TEXT,
    context_enabled BOOLEAN DEFAULT FALSE,
    embedding vector(384),
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### tags (Phase 1)
```sql
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### document_tags (Phase 1)
```sql
CREATE TABLE document_tags (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_id, tag_id)
);
```

#### groups (Phase 2)
```sql
CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    processing_status VARCHAR(20) DEFAULT 'pending',
    page_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    context_enabled BOOLEAN DEFAULT FALSE,
    context_model VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);
```

### Indexes

```sql
-- Search performance
CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_bm25_content ON chunks USING GIN (to_tsvector('english', content));

-- Foreign keys
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_page ON chunks(page_id);
CREATE INDEX idx_chunks_group ON chunks(group_id);
CREATE INDEX idx_pages_document ON pages(document_id);
CREATE INDEX idx_pages_group ON pages(group_id);
CREATE INDEX idx_groups_document ON groups(document_id);

-- Status tracking
CREATE INDEX idx_pages_status ON pages(processing_status);
CREATE INDEX idx_groups_status ON groups(processing_status);

-- Tags
CREATE INDEX idx_document_tags_document ON document_tags(document_id);
CREATE INDEX idx_document_tags_tag ON document_tags(tag_id);
```

---

## Phase Architecture

### Phase 1: Tags System

**Adds:** Tag management and document categorization

**New Components:**
- TagRepository (23 methods)
- Tag models and enums
- MCP tag tools

**Database Changes:**
- `tags` table (48 predefined)
- `document_tags` junction table

### Phase 2: Groups Management

**Adds:** Logical page grouping within documents

**New Components:**
- GroupRepository (21 methods)
- Updated PageRepository (4 new methods)
- Updated ChunkRepository (4 new methods)
- Updated DocManager (3 new methods)

**Database Changes:**
- `groups` table
- Foreign keys to `pages` and `chunks`

### Phase 3: AI Context Generation

**Adds:** LLM-powered semantic enhancement

**New Components:**
- ContextGenerationAgent
- ModelProvider
- New config fields for LLM settings

**Database Changes:**
- `context` column in chunks
- `context_enabled` flags

### Phase 4: Re-processing

**Adds:** Batch operations on existing data

**New Components:**
- ReprocessingService
- Updated DocManager (reprocessing methods)

**Database Changes:**
- None (reuses existing schema)

### Phase 5: Integration & Testing

**Adds:** System validation and optimization

**New Components:**
- Integration tests (28+ tests)
- Performance benchmarking
- Documentation

---

## Security Considerations

### 1. Input Validation

**All user inputs validated:**
- URL format validation (crawling)
- SQL injection prevention (parameterized queries)
- XSS prevention (HTML escaping in Streamlit)
- API key validation (format and presence)

**Implementation:**
```python
from pydantic import BaseModel, validator

class ChunkCreate(BaseModel):
    content: str
    
    @validator('content')
    def validate_content(cls, v):
        if len(v) < 10:
            raise ValueError('Content too short')
        return v
```

### 2. Authentication & Authorization

**Recommendation:** Implement at deployment layer

**Options:**
- OAuth2 via Streamlit auth extension
- API key authentication for MCP
- Role-based access control (RBAC) for multi-user

### 3. Data Protection

**Best Practices:**
- Database encryption at rest
- SSL/TLS for network communication
- API keys never logged
- Sensitive data masked in logs

### 4. API Keys Management

**Secure Handling:**
```python
# Never hardcode
ANTHROPIC_API_KEY=sk-ant-...  # In .env, not in code

# Never log
logger.info(f"Using key: {api_key}")  # ❌ Bad
logger.info("Using Anthropic API")   # ✅ Good
```

---

## Scalability Strategy

### Horizontal Scaling

**Multi-Instance Setup:**
```
Load Balancer
├── Instance 1 (Web + MCP)
├── Instance 2 (Web + MCP)
└── Instance 3 (Web + MCP)
    ↓
PostgreSQL (shared)
```

**Requires:**
- Session store (Redis)
- Database connection pooling
- Shared cache layer

### Vertical Scaling

**Single Instance Optimization:**
1. Increase worker processes
2. Optimize database indexes
3. Implement caching (Redis)
4. GPU acceleration for embeddings

### Database Scaling

**Optimization Strategies:**
1. **Partitioning:**
   - Partition chunks by document_id
   - Partition vectors by document_id

2. **Replication:**
   - Read replicas for search queries
   - Write replica for ingestion

3. **Archival:**
   - Move old documents to archive table
   - Keep active documents in main table

### Monitoring Metrics

**Key Metrics:**
- Embedding latency (p50, p95, p99)
- Search latency by dataset size
- Database connection pool usage
- API rate limits and quota usage
- Memory usage trends
- Disk space usage

---

## Deployment Architecture

### Development Environment

```
Developer Laptop
├── Python virtual env
├── PostgreSQL (local or Docker)
├── Streamlit (dev mode)
└── MCP Server (local)
```

### Production Environment

```
┌─────────────────────────────────────────┐
│         Load Balancer (nginx)           │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌────────┐
│App 1   │  │App 2   │  │App 3   │
│Streamlit    │Streamlit   │Streamlit
│+ MCP   │  │+ MCP   │  │+ MCP   │
└────────┘  └────────┘  └────────┘
    │            │            │
    └────────────┼────────────┘
                 │
         ┌───────▼────────┐
         │  PostgreSQL    │
         │  (HA Cluster)  │
         └────────────────┘
         
         ┌──────────────┐
         │ Redis Cache  │ (optional)
         └──────────────┘
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY context_bridge/ ./context_bridge/
COPY streamlit_app/ ./streamlit_app/

CMD ["streamlit", "run", "streamlit_app/app.py"]
```

---

## Summary

Context Bridge v0.2.0 provides a modular, scalable architecture for intelligent document processing. The layered design ensures separation of concerns, while the repository pattern enables testability. With comprehensive async/await usage, the system efficiently handles concurrent requests at scale.

**Key Strengths:**
- Clean separation of concerns
- Comprehensive type safety
- Testable design patterns
- Scalability-ready architecture
- Flexible LLM integration

**Next Steps:**
- Implement caching layer (Redis)
- Add horizontal scaling support
- Implement RBAC for multi-user
- Add real-time indexing
