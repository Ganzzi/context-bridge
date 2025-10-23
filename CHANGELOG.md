# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and setup
- Core RAG documentation management pipeline
- PostgreSQL integration with pgvector and BM25
- Hybrid vector + BM25 search capabilities
- Document and page management
- Intelligent Markdown chunking
- Multiple embedding backends (Ollama, Google Gemini)
- MCP (Model Context Protocol) server for AI agent integration
- Streamlit UI for documentation management
- Comprehensive test suite (254+ unit tests)
- Docker support with docker-compose
- Configuration management (environment variables, .env files, direct instantiation)

### Technical Achievements
- 100% unit test pass rate (254/254 tests)
- 74% code coverage
- Async/await architecture with pytest-asyncio
- Type-safe Pydantic models
- Clean repository and service layer architecture
- Comprehensive error handling and validation

## [0.1.0] - 2025-10-23

### Added
- **Initial Release** - Beta version of Context Bridge package

#### Core Features
- 🕷️ **Smart Web Crawling**: Automatic documentation discovery and crawling using Crawl4AI
- 📦 **Intelligent Chunking**: Smart Markdown chunking that respects code blocks and structure
- 🔍 **Hybrid Search**: Dual vector + BM25 search for accurate document retrieval
- 📚 **Version Management**: Track and manage multiple versions of documentation
- ⚡ **Async Architecture**: Fully asynchronous operations for high performance
- 🤖 **MCP Integration**: Model Context Protocol server for AI agent integration
- 🎨 **Streamlit UI**: User-friendly interface for documentation management

#### Database & Search
- PostgreSQL integration with psqlpy async driver
- pgvector extension for vector similarity search
- vchord_bm25 extension for full-text search
- Automatic schema initialization and migrations

#### API & Integration
- Python API (ContextBridge class)
- MCP Server (Model Context Protocol)
- Streamlit Web UI
- CLI tools via Typer
- Comprehensive documentation

#### Configuration
- Environment variable support
- .env file configuration
- Direct Python instantiation
- Config validation with Pydantic

#### Testing & Quality
- 254+ unit tests with 74% coverage
- Integration tests
- E2E tests with Playwright
- Type hints with mypy
- Code formatting with Black
- Linting with Ruff

#### Documentation
- Comprehensive README
- API documentation
- Architecture diagrams
- Configuration guides
- Development setup instructions

### Dependencies
- Python 3.11+
- PostgreSQL 13+
- psqlpy for async PostgreSQL
- crawl4ai for web scraping
- pydantic for configuration
- aiohttp for HTTP requests
- MCP server support
- Streamlit for UI
- Optional: Ollama or Google Gemini for embeddings

### Known Limitations
- E2E tests: 10/18 passing (56%) - Streamlit server rendering issues in CI/CD
- Integration tests: Requires PostgreSQL database setup
- Some database initialization errors in test environment

---

## Release Guidelines

### Versioning Scheme
- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- MAJOR: Breaking API changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes only

### Breaking Changes
Document any breaking changes in a "⚠️ BREAKING CHANGES" section.

### Deprecations
List deprecations with removal timeline in a "🗑️ DEPRECATIONS" section.

### Security
Report security vulnerabilities privately. Do not include in public changelogs.

---

**Legend**:
- ✨ New Feature
- 🐛 Bug Fix
- 📝 Documentation
- ♻️ Refactoring
- 🚀 Performance
- 🔒 Security
- ⚠️ Breaking Changes
- 🗑️ Deprecation
