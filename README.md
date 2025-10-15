# Context Bridge 🌉

> **Unified Python package for RAG-powered documentation management** - Crawl, store, chunk, and retrieve technical documentation with vector + BM25 hybrid search.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Database Schema](#-database-schema)
- [Development](#-development)
- [Technical Documentation](#-technical-documentation)
- [License](#-license)

---

## 🎯 Overview

**Context Bridge** is a standalone Python package designed to help AI agents, LLMs, and developers manage technical documentation with RAG (Retrieval-Augmented Generation) capabilities. It bridges the gap between scattered online documentation and AI-ready, searchable knowledge bases.

### What It Does

1. **Crawls** technical documentation from URLs using Crawl4AI
2. **Organizes** crawled pages into logical groups with size management
3. **Chunks** Markdown content intelligently while preserving structure
4. **Embeds** chunks using vector embeddings (Ollama/Gemini)
5. **Stores** everything in PostgreSQL with vector and vchord_bm25
6. **Searches** with hybrid vector + BM25 search for best results
7. **Serves** via MCP (Model Context Protocol) for AI agent integration
8. **Manages** through a Streamlit UI for human oversight

---

## ✨ Features

### Core Capabilities

- **🕷️ Smart Crawling**: Automatically detect and crawl documentation sites, sitemaps, and text files
- **📦 Intelligent Chunking**: Smart Markdown chunking that respects code blocks, paragraphs, and sentences
- **🔍 Hybrid Search**: Dual vector + BM25 search for superior retrieval accuracy
- **📚 Version Management**: Track multiple versions of the same documentation
- **🎯 Document Organization**: Manual page grouping with size constraints before chunking
- **⚡ High Performance**: PSQLPy for fast async PostgreSQL operations
- **🤖 AI-Ready**: MCP server for seamless AI agent integration
- **🎨 User-Friendly**: Streamlit UI for documentation management

### Technical Features

- **Vector Search**: Powered by vector extension
- **BM25 Full-Text Search**: Using vchord_bm25 extension
- **Async/Await**: Fully asynchronous operations for scalability
- **Configurable Embeddings**: Support for Ollama (local) and Google Gemini (cloud)
- **Type-Safe**: Pydantic models for configuration and data validation
- **Modular Design**: Clean separation of concerns (repositories, services, managers)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Context Bridge Architecture               │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Streamlit   │    │ MCP Server   │    │  Python API  │
│      UI      │    │  (AI Agent)  │    │   (Direct)   │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────┐
       │         Service Layer                 │
       │  - CrawlingService                    │
       │  - ChunkingService                    │
       │  - EmbeddingService                   │
       │  - SearchService                      │
       └───────────────┬───────────────────────┘
                       │
                       ▼
       ┌───────────────────────────────────────┐
       │       Repository Layer                │
       │  - DocumentRepository                 │
       │  - PageRepository                     │
       │  - GroupRepository                    │
       │  - ChunkRepository                    │
       └───────────────┬───────────────────────┘
                       │
                       ▼
       ┌───────────────────────────────────────┐
       │      PostgreSQL Manager               │
       │  - Connection Pooling                 │
       │  - Transaction Management             │
       └───────────────┬───────────────────────┘
                       │
                       ▼
       ┌───────────────────────────────────────┐
       │     PostgreSQL Database               │
       │  Extensions:                          │
       │  - vector (vector search)           │
       │  - vchord_bm25 (BM25 search)        │
       │  - pg_tokenizer (text tokenization) │
       └───────────────────────────────────────┘

External Dependencies:
┌──────────────┐    ┌──────────────┐
│   Crawl4AI   │    │    Ollama    │
│  (Crawling)  │    │  or Gemini   │
│              │    │ (Embeddings) │
└──────────────┘    └──────────────┘
```

### Workflow

```
1. Crawl Documentation
   ↓
2. Store Raw Pages
   ↓
3. Manual Organization (Group Pages)
   ↓
4. Smart Chunking
   ↓
5. Generate Embeddings
   ↓
6. Store with Vector + BM25 Indexes
   ↓
7. Hybrid Search (Vector + BM25)
```

---

## 📦 Installation

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 14+** with extensions:
  - `vector`
  - `vchord`
  - `pg_tokenizer`
  - `vchord_bm25`
- **Ollama** (for local embeddings) or **Google API Key** (for Gemini)

### Install from PyPI

```bash
pip install context-bridge
```

### Install with Optional Dependencies

```bash
# With Gemini support
pip install context-bridge[gemini]

# With MCP server
pip install context-bridge[mcp]

# With Streamlit UI
pip install context-bridge[ui]

# All features
pip install context-bridge[all]
```

### Running the Applications

**MCP Server:**
```bash
# Using the installed script
context-bridge-mcp

# Or run directly
python -m context_bridge_mcp
```

**Streamlit UI:**
```bash
# Using streamlit directly
streamlit run streamlit_app/app.py

# Or with uv
uv run streamlit run streamlit_app/app.py
```

### Install from Source

```bash
git clone https://github.com/yourusername/context-bridge.git
cd context-bridge
pip install -e .
```

---

## 🚀 Quick Start

### 1. Setup Environment

Create a `.env` file:

```bash
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=context_bridge

# Embedding Provider (ollama or gemini)
EMBEDDING_PROVIDER=ollama

# Ollama Configuration (if using ollama)
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
VECTOR_DIMENSION=768

# Gemini Configuration (if using gemini)
# GOOGLE_API_KEY=your_google_api_key
# GEMINI_EMBEDDING_MODEL=gemini-embedding-001
# GEMINI_OUTPUT_DIMENSIONALITY=768

# Search Configuration
SIMILARITY_THRESHOLD=0.7
BM25_WEIGHT=0.3
VECTOR_WEIGHT=0.7
```

### 2. Initialize Database

```bash
python -m context_bridge.database.init_databases
```

This will:
- Create required PostgreSQL extensions
- Create all necessary tables
- Set up vector and BM25 indexes

### 3. Basic Usage

```python
import asyncio
from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.service.crawling_service import CrawlingService, CrawlConfig
from crawl4ai import AsyncWebCrawler

async def main():
    # Initialize
    config = get_config()
    db_manager = PostgreSQLManager(config)
    await db_manager.initialize()
    
    # Crawl documentation
    crawl_service = CrawlingService(CrawlConfig(max_depth=3))
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawl_service.crawl_webpage(
            crawler,
            "https://docs.python.org/3/library/"
        )
    
    print(f"Crawled {result.successful_count} pages")
    
    # Store in database (using repositories)
    # ... (see full examples below)
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚙️ Configuration

The package uses Pydantic for type-safe configuration. All settings can be configured via environment variables or `.env` file.

### Core Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `postgres` | PostgreSQL user |
| `POSTGRES_PASSWORD` | *(required)* | PostgreSQL password (min 8 chars) |
| `POSTGRES_DB` | `context_bridge` | Database name |

### Embedding Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `EMBEDDING_PROVIDER` | `ollama` | Embedding provider (`ollama` or `gemini`) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model name |
| `VECTOR_DIMENSION` | `768` | Embedding vector dimension |
| `GOOGLE_API_KEY` | - | Google API key (for Gemini) |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Gemini model name |

### Search Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `SIMILARITY_THRESHOLD` | `0.7` | Minimum similarity score |
| `BM25_WEIGHT` | `0.3` | BM25 weight in hybrid search |
| `VECTOR_WEIGHT` | `0.7` | Vector weight in hybrid search |

---

## 📚 Usage

### Crawling Documentation

```python
from context_bridge.service.crawling_service import CrawlingService, CrawlConfig
from crawl4ai import AsyncWebCrawler

# Configure crawler
config = CrawlConfig(
    max_depth=3,          # How deep to follow links
    max_concurrent=10,    # Concurrent requests
    memory_threshold=70.0 # Memory usage threshold
)

service = CrawlingService(config)

# Crawl a documentation site
async with AsyncWebCrawler(verbose=True) as crawler:
    result = await service.crawl_webpage(
        crawler,
        "https://docs.example.com"
    )

# Access results
for crawl_result in result.results:
    print(f"URL: {crawl_result.url}")
    print(f"Content length: {len(crawl_result.markdown)}")
```

### Storing Documents

```python
from context_bridge.repositories.document_repository import DocumentRepository

async with db_manager.connection() as conn:
    doc_repo = DocumentRepository(conn)
    
    # Create a new document
    doc_id = await doc_repo.create(
        name="Python Documentation",
        version="3.11",
        source_url="https://docs.python.org/3/",
        description="Official Python 3.11 documentation"
    )
    
    # Store crawled pages
    for page in crawled_pages:
        await page_repo.create(
            document_id=doc_id,
            url=page.url,
            content=page.markdown,
            content_hash=hash(page.markdown)
        )
```

### Organizing Pages into Groups

```python
from context_bridge.repositories.group_repository import GroupRepository

# User manually selects pages to group
page_ids = [1, 2, 3, 4, 5]

# Create a group
async with db_manager.connection() as conn:
    group_repo = GroupRepository(conn)
    
    group_id = await group_repo.create_group(
        document_id=doc_id,
        page_ids=page_ids,
        min_size=1000,   # Minimum total content size
        max_size=50000   # Maximum total content size
    )
```

### Chunking and Embedding

```python
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService

chunking_service = ChunkingService()
embedding_service = EmbeddingService(config)

# Get groups ready for chunking
eligible_groups = await group_repo.get_eligible_groups(doc_id)

for group in eligible_groups:
    # Get combined content
    content = await group_repo.get_group_content(group.id)
    
    # Smart chunking
    chunks = chunking_service.smart_chunk_markdown(
        content,
        chunk_size=2000
    )
    
    # Generate embeddings and store
    for i, chunk_text in enumerate(chunks):
        embedding = await embedding_service.get_embedding(chunk_text)
        
        await chunk_repo.create(
            document_id=doc_id,
            group_id=group.id,
            chunk_index=i,
            content=chunk_text,
            embedding=embedding
        )
```

### Searching Documents

#### Find Documents by Query

```python
from context_bridge.repositories.document_repository import DocumentRepository

# Find relevant documents
documents = await doc_repo.find_by_query(
    query="python asyncio tutorial",
    limit=5
)

for doc in documents:
    print(f"{doc.name} (v{doc.version})")
```

#### Search Document Content (Hybrid Search)

```python
from context_bridge.repositories.chunk_repository import ChunkRepository

# Search within a specific document
chunks = await chunk_repo.hybrid_search(
    document_id=doc_id,
    version="3.11",
    query="async await examples",
    query_embedding=await embedding_service.get_embedding("async await examples"),
    limit=10,
    vector_weight=0.7,
    bm25_weight=0.3
)

for chunk in chunks:
    print(f"Score: {chunk.score}")
    print(f"Content: {chunk.content[:200]}...")
```

### Using the Streamlit UI

The Context Bridge includes a full-featured web interface for managing documentation:

```bash
# Install with UI support
pip install context-bridge[ui]

# Run the Streamlit application
uv run streamlit run streamlit_app/app.py

# Or use the installed script
context-bridge-ui
```

**Features:**
- **Document Management**: View, search, and delete documents
- **Page Organization**: Select and group crawled pages for processing
- **Chunk Processing**: Convert page groups into searchable chunks
- **Hybrid Search**: Search across all documentation with advanced filtering

### Using the MCP Server

The Model Context Protocol server allows AI agents to interact with Context Bridge:

```bash
# Install with MCP support
pip install context-bridge[mcp]

# Run the MCP server
uv run python -m context_bridge_mcp

# Or use the installed script
context-bridge-mcp
```

**Available Tools:**
- `find_documents`: Search for documents by query
- `search_content`: Perform hybrid vector + BM25 search within specific documents

**Integration with AI Clients:**
The MCP server can be integrated with AI assistants like Claude Desktop for seamless documentation access.

For detailed usage instructions, see the [MCP Server Usage Guide](docs/guide/MCP_SERVER_USAGE.md).

---

## 🗄️ Database Schema

### Core Tables

```sql
-- Documents (versioned documentation)
CREATE TABLE documents (
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

-- Pages (raw crawled content)
CREATE TABLE pages (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    url TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_length INTEGER GENERATED ALWAYS AS (length(content)) STORED,
    crawled_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'chunked', 'deleted')),
    group_id UUID, -- For future grouping feature
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Chunks (embedded content)
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    group_id UUID, -- For future grouping feature
    embedding VECTOR(768), -- Dimension must match config
    bm25_vector bm25vector, -- Auto-generated by trigger
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, group_id, chunk_index)
);

-- Indexes
CREATE INDEX idx_pages_document ON pages(document_id);
CREATE INDEX idx_pages_status ON pages(status);
CREATE INDEX idx_pages_hash ON pages(content_hash);
CREATE INDEX idx_pages_group ON pages(group_id);
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_group ON chunks(group_id);
CREATE INDEX idx_chunks_vector ON chunks USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_chunks_bm25 ON chunks USING bm25(bm25_vector bm25_ops);
```

---

## 🛠️ Development

### Project Structure

```
context_bridge/               # Core package
├── __init__.py
├── config.py                 # Configuration management
├── core.py                   # Main ContextBridge API
├── database/
│   ├── init_databases.py     # Database initialization
│   └── postgres_manager.py   # Connection pool manager
├── schema/
│   └── extensions.sql        # PostgreSQL extensions & schema
├── repositories/             # Data access layer
│   ├── document_repository.py
│   ├── page_repository.py
│   ├── group_repository.py
│   └── chunk_repository.py
├── service/                  # Business logic layer
│   ├── crawling_service.py
│   ├── chunking_service.py
│   ├── embedding.py
│   ├── search_service.py
│   └── url_service.py

context_bridge_mcp/          # MCP Server (Model Context Protocol)
├── __init__.py
├── server.py                 # MCP server implementation
├── schemas.py                # Tool input/output schemas
└── __main__.py               # CLI entry point

streamlit_app/               # Streamlit Web UI
├── __init__.py
├── app.py                    # Main application
├── pages/                    # Multi-page navigation
│   ├── documents.py          # Document management
│   ├── crawled_pages.py      # Page management
│   └── search.py             # Search interface
├── components/               # Reusable UI components
├── utils/                    # UI utilities and helpers
└── README.md                 # UI-specific documentation

docs/                        # Documentation
├── guide/
│   └── MCP_SERVER_USAGE.md   # MCP server usage guide
├── plan/                    # Development plans
│   └── ui_and_mcp_implementation_plan.md
├── technical/               # Technical guides
│   ├── crawl4ai_complete_guide.md
│   ├── embedding_service.md
│   ├── psqlpy-complete-guide.md
│   ├── python_mcp_server_guide.md
│   ├── python-testing-guide.md
│   └── smart_chunk_markdown_algorithm.md
└── memory_templates.yaml    # Memory usage templates

tests/                       # Test suite
├── conftest.py
├── integration/
├── unit/
└── e2e/                     # End-to-end tests
    ├── conftest.py
    └── test_streamlit_ui.py
```
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=context_bridge --cov-report=html

# Run specific test file
pytest tests/test_chunking_service.py -v
```

### Code Quality

```bash
# Format code
black context_bridge tests

# Type checking
mypy context_bridge

# Linting
ruff check context_bridge
```

---

## 📖 Technical Documentation

Comprehensive technical guides are available in `docs/`:

### Testing & Quality Assurance
- **[UI Testing Report](docs/ui_testing_report.md)** - Comprehensive Playwright testing results and bug fixes
- **[MCP Server Usage Guide](docs/guide/MCP_SERVER_USAGE.md)** - How to use the MCP server with AI clients

### Technical Guides (`docs/technical/`)
- **[Crawl4AI Guide](docs/technical/crawl4ai_complete_guide.md)** - Complete crawling documentation
- **[Embedding Service](docs/technical/embedding_service.md)** - Ollama and Gemini embedding setup
- **[PSQLPy Guide](docs/technical/psqlpy-complete-guide.md)** - PostgreSQL driver usage
- **[MCP Server Guide](docs/technical/python_mcp_server_guide.md)** - MCP server implementation
- **[Testing Guide](docs/technical/python-testing-guide.md)** - Testing best practices
- **[Smart Chunking Algorithm](docs/technical/smart_chunk_markdown_algorithm.md)** - Chunking implementation

### Implementation Plans (`docs/plan/`)
- **[UI & MCP Implementation Plan](docs/plan/ui_and_mcp_implementation_plan.md)** - Development roadmap and progress

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **[Crawl4AI](https://github.com/unclecode/crawl4ai)** - High-performance web crawler
- **[PSQLPy](https://github.com/qaspen-python/psqlpy)** - Async PostgreSQL driver
- **[pgvector](https://github.com/pgvector/pgvector)** - Vector similarity search
- **[MCP](https://modelcontextprotocol.io/)** - Model Context Protocol

---

## 📧 Support

For questions, issues, or feature requests:
- **Issues**: [GitHub Issues](https://github.com/yourusername/context-bridge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/context-bridge/discussions)
- **Email**: your.email@example.com

---

**Built with ❤️ for AI agents and developers**
