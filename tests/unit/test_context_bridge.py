"""
Unit tests for ContextBridge public API.

Tests ContextBridge operations with mocked dependencies.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from context_bridge.core import ContextBridge
from context_bridge.config import Config
from context_bridge.service.doc_manager import CrawlAndStoreResult, ChunkProcessingResult, PageInfo
from context_bridge.service.search_service import ContentSearchResult
from context_bridge.database.repositories.document_repository import Document


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock(spec=Config)
    config.postgres = MagicMock()
    config.crawl_max_depth = 3
    config.crawl_max_concurrent = 10
    config.chunk_size = 2000
    config.embedding = MagicMock()
    return config


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    manager = MagicMock()
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()
    manager.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    manager.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def mock_doc_manager():
    """Create a mock document manager."""
    manager = MagicMock()
    manager.crawl_and_store = AsyncMock()
    manager.list_pages = AsyncMock()
    manager.delete_page = AsyncMock()
    manager.delete_document = AsyncMock()
    manager.process_chunking = AsyncMock()
    manager.embedding_service = MagicMock()
    manager.embedding_service.verify_connection = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def mock_search_service():
    """Create a mock search service."""
    service = MagicMock()
    service.search_content = AsyncMock()
    service.search_across_versions = AsyncMock()
    return service


@pytest.fixture
def mock_doc_repo():
    """Create a mock document repository."""
    repo = MagicMock()
    repo.list_all = AsyncMock()
    repo.get_by_name_version = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def context_bridge(
    mock_config, mock_db_manager, mock_doc_manager, mock_search_service, mock_doc_repo
):
    """Create a ContextBridge instance with mocked dependencies."""
    bridge = ContextBridge(config=mock_config)

    # Replace internal components with mocks
    bridge._db_manager = mock_db_manager
    bridge._doc_manager = mock_doc_manager
    bridge._search_service = mock_search_service
    bridge._initialized = True

    # Mock the connection context manager for doc repo
    mock_conn = MagicMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_db_manager.connection.return_value = mock_conn

    # Mock doc repo creation
    with (
        patch(
            "context_bridge.database.repositories.document_repository.DocumentRepository",
            return_value=mock_doc_repo,
        ),
        patch("context_bridge.database.repositories.chunk_repository.ChunkRepository"),
    ):
        yield bridge


class TestContextBridge:
    """Unit tests for ContextBridge with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config, mock_db_manager):
        """Test ContextBridge initialization."""
        bridge = ContextBridge(config=mock_config)

        assert not bridge._initialized
        assert bridge._db_manager is None

        # Mock all the service initializations
        with (
            patch("context_bridge.core.PostgreSQLManager", return_value=mock_db_manager),
            patch("context_bridge.core.UrlService"),
            patch("context_bridge.core.CrawlConfig"),
            patch("context_bridge.core.CrawlingService"),
            patch("context_bridge.core.ChunkingService"),
            patch("context_bridge.core.EmbeddingService"),
            patch("context_bridge.core.DocManager"),
            patch("context_bridge.database.repositories.document_repository.DocumentRepository"),
            patch("context_bridge.database.repositories.chunk_repository.ChunkRepository"),
            patch("context_bridge.core.SearchService"),
        ):

            await bridge.initialize()

            assert bridge._initialized
            assert bridge._db_manager is not None
            mock_db_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, context_bridge, mock_db_manager):
        """Test ContextBridge close."""
        await context_bridge.close()

        assert not context_bridge._initialized
        mock_db_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config, mock_db_manager):
        """Test ContextBridge as async context manager."""
        bridge = ContextBridge(config=mock_config)

        # Mock all the service initializations
        with (
            patch("context_bridge.core.PostgreSQLManager", return_value=mock_db_manager),
            patch("context_bridge.core.UrlService"),
            patch("context_bridge.core.CrawlConfig"),
            patch("context_bridge.core.CrawlingService"),
            patch("context_bridge.core.ChunkingService"),
            patch("context_bridge.core.EmbeddingService"),
            patch("context_bridge.core.DocManager"),
            patch("context_bridge.database.repositories.document_repository.DocumentRepository"),
            patch("context_bridge.database.repositories.chunk_repository.ChunkRepository"),
            patch("context_bridge.core.SearchService"),
        ):

            async with bridge:
                assert bridge._initialized

            assert not bridge._initialized
            mock_db_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_documentation(self, context_bridge, mock_doc_manager):
        """Test document crawling."""
        # Setup mock
        result = MagicMock(spec=CrawlAndStoreResult)
        result.document_id = 1
        mock_doc_manager.crawl_and_store.return_value = result

        # Execute
        response = await context_bridge.crawl_documentation(
            name="test-doc", version="1.0.0", source_url="https://example.com"
        )

        # Verify
        assert response == result
        mock_doc_manager.crawl_and_store.assert_called_once_with(
            name="test-doc",
            version="1.0.0",
            source_url="https://example.com",
            description=None,
            max_depth=None,
            additional_urls=None,
        )

    @pytest.mark.asyncio
    async def test_crawl_documentation_with_additional_urls(self, context_bridge, mock_doc_manager):
        """Test document crawling with additional URLs."""
        # Setup mock
        result = MagicMock(spec=CrawlAndStoreResult)
        result.document_id = 1
        mock_doc_manager.crawl_and_store.return_value = result

        # Execute
        additional_urls = ["https://example.com/api", "https://example.com/docs"]
        response = await context_bridge.crawl_documentation(
            name="test-doc",
            version="1.0.0",
            source_url="https://example.com",
            additional_urls=additional_urls,
        )

        # Verify
        assert response == result
        mock_doc_manager.crawl_and_store.assert_called_once_with(
            name="test-doc",
            version="1.0.0",
            source_url="https://example.com",
            description=None,
            max_depth=None,
            additional_urls=additional_urls,
        )

    @pytest.mark.asyncio
    async def test_crawl_documentation_not_initialized(self, mock_config):
        """Test crawl_documentation when not initialized."""
        bridge = ContextBridge(config=mock_config)
        bridge._initialized = False

        with pytest.raises(RuntimeError, match="ContextBridge not initialized"):
            await bridge.crawl_documentation("test", "1.0.0", "https://example.com")

    @pytest.mark.asyncio
    async def test_list_documents(self, context_bridge, mock_doc_repo):
        """Test listing documents."""
        # Setup mock
        docs = [MagicMock(spec=Document), MagicMock(spec=Document)]
        mock_doc_repo.list_all.return_value = docs

        # Execute
        with patch("context_bridge.core.DocumentRepository", return_value=mock_doc_repo):
            result = await context_bridge.list_documents(offset=10, limit=50)

        # Verify
        assert result == docs
        mock_doc_repo.list_all.assert_called_once_with(offset=10, limit=50)

    @pytest.mark.asyncio
    async def test_get_document(self, context_bridge, mock_doc_repo):
        """Test getting a specific document."""
        # Setup mock
        doc = MagicMock(spec=Document)
        mock_doc_repo.get_by_name_version.return_value = doc

        # Execute
        with patch("context_bridge.core.DocumentRepository", return_value=mock_doc_repo):
            result = await context_bridge.get_document("test-doc", "1.0.0")

        # Verify
        assert result == doc
        mock_doc_repo.get_by_name_version.assert_called_once_with("test-doc", "1.0.0")

    @pytest.mark.asyncio
    async def test_delete_document(self, context_bridge, mock_doc_manager):
        """Test deleting a document."""
        # Setup mock
        mock_doc_manager.delete_document.return_value = True

        # Execute
        result = await context_bridge.delete_document(123)

        # Verify
        assert result is True
        mock_doc_manager.delete_document.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_list_pages(self, context_bridge, mock_doc_manager):
        """Test listing pages."""
        # Setup mock
        pages = [MagicMock(spec=PageInfo), MagicMock(spec=PageInfo)]
        mock_doc_manager.list_pages.return_value = pages

        # Execute
        result = await context_bridge.list_pages(
            document_id=1, status="pending", offset=5, limit=25
        )

        # Verify
        assert result == pages
        mock_doc_manager.list_pages.assert_called_once_with(
            document_id=1, status="pending", offset=5, limit=25
        )

    @pytest.mark.asyncio
    async def test_delete_page(self, context_bridge, mock_doc_manager):
        """Test deleting a page."""
        # Setup mock
        mock_doc_manager.delete_page.return_value = True

        # Execute
        result = await context_bridge.delete_page(456)

        # Verify
        assert result is True
        mock_doc_manager.delete_page.assert_called_once_with(456)

    @pytest.mark.asyncio
    async def test_process_pages(self, context_bridge, mock_doc_manager):
        """Test processing pages for chunking."""
        # Setup mock
        result = MagicMock(spec=ChunkProcessingResult)
        result.document_id = 1
        result.pages_processed = 5
        mock_doc_manager.process_chunking.return_value = result

        # Execute
        response = await context_bridge.process_pages(
            document_id=1, page_ids=[1, 2, 3, 4, 5], chunk_size=1500
        )

        # Verify
        assert response == result
        mock_doc_manager.process_chunking.assert_called_once_with(
            document_id=1, page_ids=[1, 2, 3, 4, 5], chunk_size=1500, run_async=True
        )

    @pytest.mark.asyncio
    async def test_search(self, context_bridge, mock_search_service):
        """Test content search."""
        # Setup mock
        results = [MagicMock(spec=ContentSearchResult), MagicMock(spec=ContentSearchResult)]
        mock_search_service.search_content.return_value = results

        # Execute
        response = await context_bridge.search(
            query="test query", document_id=1, limit=20, vector_weight=0.7, bm25_weight=0.3
        )

        # Verify
        assert response == results
        mock_search_service.search_content.assert_called_once_with(
            query="test query", document_id=1, limit=20, vector_weight=0.7, bm25_weight=0.3
        )

    @pytest.mark.asyncio
    async def test_search_across_versions(self, context_bridge, mock_search_service):
        """Test cross-version search."""
        # Setup mock
        results = {
            "1.0.0": [MagicMock(spec=ContentSearchResult)],
            "1.1.0": [MagicMock(spec=ContentSearchResult)],
        }
        mock_search_service.search_across_versions.return_value = results

        # Execute
        response = await context_bridge.search_across_versions(
            query="test query", document_name="test-doc", limit_per_version=3
        )

        # Verify
        assert response == results
        mock_search_service.search_across_versions.assert_called_once_with(
            query="test query", document_name="test-doc", limit_per_version=3
        )

    @pytest.mark.asyncio
    async def test_health_check(self, context_bridge, mock_db_manager, mock_doc_manager):
        """Test health check functionality."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_manager.connection.return_value = mock_conn

        mock_doc_manager.embedding_service.verify_connection.return_value = True

        # Execute
        health = await context_bridge.health_check()

        # Verify
        assert health["initialized"] is True
        assert health["database"] is True
        assert health["embedding_service"] is True
        assert "services" in health
        assert health["services"]["doc_manager"] is True
        assert health["services"]["search_service"] is True

    @pytest.mark.asyncio
    async def test_health_check_database_failure(self, context_bridge, mock_db_manager):
        """Test health check with database failure."""
        # Setup mock to fail
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_manager.connection.return_value = mock_conn

        # Execute
        health = await context_bridge.health_check()

        # Verify
        assert health["initialized"] is True
        assert health["database"] is False
        assert "database_error" in health

    def test_get_config(self, context_bridge, mock_config):
        """Test getting configuration."""
        assert context_bridge.get_config() == mock_config

    def test_is_initialized(self, context_bridge):
        """Test initialization status check."""
        assert context_bridge.is_initialized() is True

        bridge = ContextBridge()
        assert bridge.is_initialized() is False
