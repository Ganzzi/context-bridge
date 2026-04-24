"""
Shared test fixtures for Context Bridge testing.

This module provides common test fixtures used across unit and integration tests.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any
from psqlpy.exceptions import BaseConnectionPoolError

from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.service.doc_manager import DocManager
from context_bridge.service.search_service import SearchService
from context_bridge.service.crawling_service import CrawlingService, CrawlConfig
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService
from context_bridge.service.url_service import UrlService
from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from context_bridge.database.repositories.page_repository import PageRepository, Page
from context_bridge.database.repositories.chunk_repository import ChunkRepository, Chunk


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply test markers consistently based on file path.

    This keeps PR-gated runs deterministic with:
    `pytest -m "not integration and not e2e"`.
    """
    for item in items:
        path = str(item.fspath).replace("\\", "/")

        if "/tests/e2e/" in path:
            item.add_marker(pytest.mark.e2e)
        elif "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/" in path or "/tests/" in path:
            # Root-level tests in this repo are integration-oriented/manual-heavy.
            item.add_marker(pytest.mark.integration)


# Configuration Fixtures


@pytest.fixture
def sample_config() -> Config:
    """Create a sample configuration for testing."""
    return Config(
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="test_user",
        postgres_password="test_password",
        postgres_db="test_db",
        postgres_max_pool_size=10,
        ollama_base_url="http://localhost:11434",
        embedding_model="nomic-embed-text:latest",
        vector_dimension=768,
        crawl_max_depth=3,
        crawl_max_concurrent=10,
        chunk_size=2000,
        min_combined_content_size=100,
        max_combined_content_size=50000,
    )


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock configuration."""
    config = MagicMock(spec=Config)
    config.postgres_host = "localhost"
    config.postgres_port = 5432
    config.postgres_user = "test_user"
    config.postgres_password = "test_password"
    config.postgres_db = "test_db"
    config.postgres_max_pool_size = 10
    config.ollama_base_url = "http://localhost:11434"
    config.embedding_model = "nomic-embed-text:latest"
    config.vector_dimension = 768
    config.crawl_max_depth = 3
    config.crawl_max_concurrent = 10
    config.chunk_size = 2000
    config.min_combined_content_size = 100
    config.max_combined_content_size = 50000
    config.context_agent_model = "anthropic:claude-3-5-sonnet-20241022"
    config.anthropic_api_key = None
    config.openai_api_key = None
    return config


# Database Manager Fixtures


@pytest.fixture
def mock_db_manager() -> AsyncMock:
    """Create a mock database manager with proper async context manager support."""
    manager = AsyncMock(spec=PostgreSQLManager)
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()

    # Create a mock connection that supports async context manager protocol
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Make connection() return the async context manager
    manager.connection = MagicMock(return_value=mock_conn)

    return manager


@pytest.fixture(scope="session")
def test_db_config() -> Dict[str, Any]:
    """Configuration for test database."""
    import os

    return {
        "host": os.getenv("TEST_POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("TEST_POSTGRES_PORT", "5432")),
        "user": os.getenv("TEST_POSTGRES_USER", "postgres"),
        "password": os.getenv("TEST_POSTGRES_PASSWORD", ""),
        "database": os.getenv("TEST_POSTGRES_DB", "context_bridge_test"),
    }


@pytest.fixture(scope="session")
async def test_db_manager(test_db_config: Dict[str, Any]):
    """Real database manager for integration tests."""
    from context_bridge.database.postgres_manager import PostgreSQLManager
    from context_bridge.config import Config

    config = Config(
        postgres_host=test_db_config["host"],
        postgres_port=test_db_config["port"],
        postgres_user=test_db_config["user"],
        postgres_password=test_db_config["password"],
        postgres_db=test_db_config["database"],
    )

    manager = PostgreSQLManager(config)
    try:
        await manager.initialize()
    except BaseConnectionPoolError as exc:
        pytest.skip(f"PostgreSQL unavailable for integration tests: {exc}")

    # Set up test schema
    from context_bridge.database.init_databases import init_postgresql

    try:
        await init_postgresql()
    except BaseConnectionPoolError as exc:
        await manager.close()
        pytest.skip(f"PostgreSQL unavailable for integration tests: {exc}")

    yield manager

    await manager.close()


# Repository Fixtures


@pytest.fixture
def mock_document_repo() -> AsyncMock:
    """Create a mock document repository."""
    repo = AsyncMock(spec=DocumentRepository)
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_url = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.list_all = AsyncMock()
    repo.search = AsyncMock()
    return repo


@pytest.fixture
def mock_page_repo() -> AsyncMock:
    """Create a mock page repository."""
    repo = AsyncMock(spec=PageRepository)
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_url = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.list_by_document = AsyncMock()
    repo.search = AsyncMock()
    return repo


@pytest.fixture
def mock_chunk_repo() -> AsyncMock:
    """Create a mock chunk repository."""
    repo = AsyncMock(spec=ChunkRepository)
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_document = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.search_similar = AsyncMock()
    repo.list_by_document = AsyncMock()
    return repo


# Service Fixtures


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    """Create a mock embedding service."""
    service = AsyncMock(spec=EmbeddingService)
    service.get_embedding = AsyncMock(return_value=[0.1] * 768)
    service.get_embeddings = AsyncMock(return_value=[[0.1] * 768])
    service.verify_connection = AsyncMock(return_value=True)
    service.ensure_model_available = AsyncMock(return_value=True)
    service.validate_configuration = AsyncMock(return_value=[])
    service.get_cache_stats = AsyncMock(
        return_value={"enabled": True, "size": 0, "hits": 0, "misses": 0, "hit_rate": 0.0}
    )
    service.clear_cache = AsyncMock()
    return service


@pytest.fixture
def mock_crawling_service() -> AsyncMock:
    """Create a mock crawling service."""
    service = AsyncMock(spec=CrawlingService)
    service.crawl_url = AsyncMock()
    service.crawl_urls = AsyncMock()
    service.get_crawl_status = AsyncMock()
    service.cancel_crawl = AsyncMock()
    return service


@pytest.fixture
def mock_chunking_service() -> AsyncMock:
    """Create a mock chunking service."""
    service = AsyncMock(spec=ChunkingService)
    service.chunk_text = AsyncMock(
        return_value=[{"content": "chunk1", "metadata": {}}, {"content": "chunk2", "metadata": {}}]
    )
    service.chunk_html = AsyncMock(
        return_value=[{"content": "chunk1", "metadata": {}}, {"content": "chunk2", "metadata": {}}]
    )
    return service


@pytest.fixture
def mock_url_service() -> AsyncMock:
    """Create a mock URL service."""
    service = AsyncMock(spec=UrlService)
    service.normalize_url = AsyncMock(return_value="https://example.com")
    service.is_valid_url = AsyncMock(return_value=True)
    service.extract_domain = AsyncMock(return_value="example.com")
    service.get_url_metadata = AsyncMock(return_value={"title": "Test"})
    return service


@pytest.fixture
def mock_doc_manager() -> AsyncMock:
    """Create a mock document manager."""
    manager = AsyncMock(spec=DocManager)
    manager.create_document = AsyncMock()
    manager.get_document = AsyncMock()
    manager.update_document = AsyncMock()
    manager.delete_document = AsyncMock()
    manager.list_documents = AsyncMock()
    manager.search_documents = AsyncMock()
    return manager


@pytest.fixture
def mock_search_service() -> AsyncMock:
    """Create a mock search service."""
    service = AsyncMock(spec=SearchService)
    service.search = AsyncMock(return_value=[])
    service.search_similar = AsyncMock(return_value=[])
    service.get_relevant_chunks = AsyncMock(return_value=[])
    return service


# Sample Data Fixtures


@pytest.fixture
def sample_document() -> Document:
    """Create a sample document."""
    return Document(
        id=1,
        name="test-doc",
        version="1.0",
        url="https://example.com",
        title="Test Document",
        content="This is test content.",
        summary="Test summary",
        status="completed",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
        crawled_at="2025-01-01T00:00:00Z",
        error_message=None,
    )


@pytest.fixture
def sample_page() -> Page:
    """Create a sample page."""
    return Page(
        id=1,
        document_id=1,
        url="https://example.com/page1",
        title="Test Page",
        content="<html><body>Test content</body></html>",
        summary="Test page summary",
        status="completed",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
        crawled_at="2025-01-01T00:00:00Z",
        error_message=None,
    )


@pytest.fixture
def sample_chunk() -> Chunk:
    """Create a sample chunk."""
    return Chunk(
        id=1,
        document_id=1,
        chunk_index=0,
        content="This is a test chunk.",
        source_page_ids=[1],
        embedding=[0.1] * 768,
        created_at="2025-01-01T00:00:00Z",
    )


# Integration Test Fixtures for Real Database Operations


@pytest.fixture(scope="session")
async def test_database_setup(test_db_manager):
    """Set up test database with schema and basic data."""
    from context_bridge.database.init_databases import init_postgresql

    # Initialize schema
    await init_postgresql(test_db_manager)
    yield test_db_manager


@pytest.fixture
async def clean_test_db(test_database_setup):
    """Clean test database between tests."""
    # Clean up any existing test data
    async with test_database_setup.connection() as conn:
        await conn.execute(
            "DELETE FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE name LIKE 'test-%')"
        )
        await conn.execute(
            "DELETE FROM pages WHERE document_id IN (SELECT id FROM documents WHERE name LIKE 'test-%')"
        )
        await conn.execute("DELETE FROM documents WHERE name LIKE 'test-%'")
    yield test_database_setup


@pytest.fixture
async def sample_test_document(clean_test_db):
    """Create a sample test document in the database."""
    from context_bridge.database.repositories.document_repository import DocumentRepository

    async with clean_test_db.connection() as conn:
        repo = DocumentRepository(conn)
        doc_id = await repo.create(
            name="test-integration-doc", version="1.0.0", description="Integration test document"
        )

        doc = await repo.get_by_id(doc_id)
        return doc


@pytest.fixture
async def sample_test_pages(clean_test_db, sample_test_document):
    """Create sample test pages in the database."""
    from context_bridge.database.repositories.page_repository import PageRepository
    import hashlib

    async with clean_test_db.connection() as conn:
        repo = PageRepository(conn)

        test_pages = [
            {
                "url": "https://example.com/page1",
                "content": "# Page 1\n\nThis is the first test page with some content.",
                "title": "Test Page 1",
            },
            {
                "url": "https://example.com/page2",
                "content": "# Page 2\n\nThis is the second test page with different content.",
                "title": "Test Page 2",
            },
            {
                "url": "https://example.com/page3",
                "content": "# Page 3\n\nThis is the third test page with more content for testing.",
                "title": "Test Page 3",
            },
        ]

        page_ids = []
        for page_data in test_pages:
            content_hash = hashlib.sha256(page_data["content"].encode()).hexdigest()
            page_id = await repo.create(
                document_id=sample_test_document.id,
                url=page_data["url"],
                content=page_data["content"],
                title=page_data["title"],
                content_hash=content_hash,
                status="pending",
            )
            page_ids.append(page_id)

        # Return page objects
        pages = []
        for page_id in page_ids:
            page = await repo.get_by_id(page_id)
            pages.append(page)

        return pages


@pytest.fixture
async def sample_test_chunks(clean_test_db, sample_test_document, sample_test_pages):
    """Create sample test chunks in the database."""
    from context_bridge.database.repositories.chunk_repository import ChunkRepository

    async with clean_test_db.connection() as conn:
        repo = ChunkRepository(clean_test_db)

        # Create some test chunks
        test_chunks = [
            {
                "document_id": sample_test_document.id,
                "chunk_index": 0,
                "content": "This is chunk 1 content from page 1.",
                "source_page_ids": [sample_test_pages[0].id],
                "embedding": [0.1] * 768,
            },
            {
                "document_id": sample_test_document.id,
                "chunk_index": 1,
                "content": "This is chunk 2 content from pages 1 and 2.",
                "source_page_ids": [sample_test_pages[0].id, sample_test_pages[1].id],
                "embedding": [0.2] * 768,
            },
            {
                "document_id": sample_test_document.id,
                "chunk_index": 2,
                "content": "This is chunk 3 content from page 3.",
                "source_page_ids": [sample_test_pages[2].id],
                "embedding": [0.3] * 768,
            },
        ]

        chunk_ids = []
        for chunk_data in test_chunks:
            chunk_id = await repo.create(
                document_id=chunk_data["document_id"],
                chunk_index=chunk_data["chunk_index"],
                content=chunk_data["content"],
                source_page_ids=chunk_data["source_page_ids"],
                embedding=chunk_data["embedding"],
            )
            chunk_ids.append(chunk_id)

        # Return chunk objects
        chunks = []
        for chunk_id in chunk_ids:
            chunk = await repo.get_by_id(chunk_id)
            chunks.append(chunk)

        return chunks


# Service Integration Fixtures


@pytest.fixture
async def real_embedding_service():
    """Create a real embedding service for integration testing."""
    from context_bridge.service.embedding import EmbeddingService
    from context_bridge.config import Config

    config = Config()
    service = EmbeddingService(config, enable_cache=True, max_cache_size=10)

    # Verify connection (skip if Ollama not available)
    try:
        connection_ok = await service.verify_connection()
        if not connection_ok:
            pytest.skip("Ollama is not running or model is not available")
    except Exception:
        pytest.skip("Ollama integration not available for testing")

    return service


@pytest.fixture
async def real_crawling_service():
    """Create a real crawling service for integration testing."""
    from context_bridge.service.crawling_service import CrawlingService, CrawlConfig
    from context_bridge.service.url_service import UrlService

    url_service = UrlService()
    crawl_config = CrawlConfig(max_depth=2, max_concurrent=5, memory_threshold=80.0)

    service = CrawlingService(crawl_config, url_service)
    return service


@pytest.fixture
async def real_chunking_service():
    """Create a real chunking service for integration testing."""
    from context_bridge.service.chunking_service import ChunkingService

    service = ChunkingService(default_chunk_size=1000)
    return service


# Workflow Integration Fixtures


@pytest.fixture
async def real_doc_manager(
    clean_test_db, real_crawling_service, real_chunking_service, real_embedding_service
):
    """Create a real document manager for integration testing."""
    from context_bridge.service.doc_manager import DocManager
    from context_bridge.config import Config

    config = Config()
    manager = DocManager(
        db_manager=clean_test_db,
        crawling_service=real_crawling_service,
        chunking_service=real_chunking_service,
        embedding_service=real_embedding_service,
        config=config,
    )

    return manager


@pytest.fixture
async def real_search_service(clean_test_db, real_embedding_service):
    """Create a real search service for integration testing."""
    from context_bridge.service.search_service import SearchService
    from context_bridge.database.repositories.document_repository import DocumentRepository
    from context_bridge.database.repositories.chunk_repository import ChunkRepository

    async with clean_test_db.connection() as conn:
        doc_repo = DocumentRepository(conn)
        chunk_repo = ChunkRepository(clean_test_db)

        service = SearchService(
            document_repo=doc_repo, chunk_repo=chunk_repo, embedding_service=real_embedding_service
        )

        return service


@pytest.fixture
async def real_context_bridge(clean_test_db):
    """Create a real ContextBridge instance for integration testing."""
    from context_bridge import ContextBridge

    bridge = ContextBridge()
    await bridge.initialize()

    yield bridge

    await bridge.close()


# Test Data Factories


@pytest.fixture
def test_document_factory():
    """Factory for creating test document data."""

    def _create_test_doc(name="test-doc", version="1.0.0", description="Test document"):
        return {"name": name, "version": version, "description": description}

    return _create_test_doc


@pytest.fixture
def test_page_factory():
    """Factory for creating test page data."""

    def _create_test_page(
        url="https://example.com/test", title="Test Page", content="# Test\n\nContent"
    ):
        import hashlib

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return {
            "url": url,
            "title": title,
            "content": content,
            "content_hash": content_hash,
            "status": "pending",
        }

    return _create_test_page


@pytest.fixture
def test_chunk_factory():
    """Factory for creating test chunk data."""

    def _create_test_chunk(
        document_id=1, chunk_index=0, content="Test chunk", source_page_ids=None, embedding=None
    ):
        if source_page_ids is None:
            source_page_ids = [1]
        if embedding is None:
            embedding = [0.1] * 768
        return {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "content": content,
            "source_page_ids": source_page_ids,
            "embedding": embedding,
        }

    return _create_test_chunk
