"""
Unit tests for DocManager.

Tests DocManager operations with mocked dependencies.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List
from uuid import uuid4

from context_bridge.config import Config
from context_bridge.service.doc_manager import (
    DocManager,
    CrawlAndStoreResult,
    ChunkProcessingResult,
    PageInfo,
)
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.service.crawling_service import CrawlingService, CrawlBatchResult, CrawlResult
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock(spec=Config)
    config.chunk_size = 2000
    config.min_combined_content_size = 100
    config.max_combined_content_size = 50000
    config.crawl_max_depth = 3
    config.crawl_max_concurrent = 10
    return config


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    return MagicMock()


@pytest.fixture
def mock_crawling_service():
    """Create a mock crawling service."""
    service = MagicMock(spec=CrawlingService)
    return service


@pytest.fixture
def mock_chunking_service():
    """Create a mock chunking service."""
    service = MagicMock(spec=ChunkingService)
    service.smart_chunk_markdown.return_value = ["Chunk 1", "Chunk 2", "Chunk 3"]
    return service


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = MagicMock(spec=EmbeddingService)
    service.get_embedding.return_value = [0.1] * 768
    service.get_embeddings_batch.return_value = [[0.1] * 768] * 3
    return service


@pytest.fixture
def mock_doc_repo():
    """Create a mock document repository."""
    repo = MagicMock(spec=DocumentRepository)
    return repo


@pytest.fixture
def mock_page_repo():
    """Create a mock page repository."""
    repo = MagicMock(spec=PageRepository)
    return repo


@pytest.fixture
def mock_chunk_repo():
    """Create a mock chunk repository."""
    repo = MagicMock(spec=ChunkRepository)
    return repo


@pytest.fixture
def doc_manager(
    mock_db_manager,
    mock_crawling_service,
    mock_chunking_service,
    mock_embedding_service,
    mock_config,
    mock_doc_repo,
    mock_page_repo,
    mock_chunk_repo,
):
    """Create a DocManager instance with mocked dependencies."""
    manager = DocManager(
        db_manager=mock_db_manager,
        crawling_service=mock_crawling_service,
        chunking_service=mock_chunking_service,
        embedding_service=mock_embedding_service,
        config=mock_config,
    )

    # Replace repositories with mocks
    manager.doc_repo = mock_doc_repo
    manager.page_repo = mock_page_repo
    manager.chunk_repo = mock_chunk_repo

    return manager


class TestDocManager:
    """Unit tests for DocManager with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_crawl_and_store_new_document(
        self, doc_manager, mock_doc_repo, mock_page_repo, mock_crawling_service
    ):
        """Test crawling and storing a new document."""
        # Setup mocks
        mock_doc_repo.get_by_name_version.return_value = None
        mock_doc_repo.create.return_value = 1

        crawl_result = MagicMock()
        crawl_result.results = [
            MagicMock(markdown="Content 1", url="https://example.com/page1"),
            MagicMock(markdown="Content 2", url="https://example.com/page2"),
        ]
        mock_crawling_service.crawl_webpage.return_value = crawl_result

        mock_page_repo.get_by_url.return_value = None

        # Execute
        result = await doc_manager.crawl_and_store(
            name="test-doc",
            version="1.0.0",
            source_url="https://example.com",
            description="Test document",
        )

        # Verify
        assert isinstance(result, CrawlAndStoreResult)
        assert result.document_id == 1
        assert result.document_name == "test-doc"
        assert result.document_version == "1.0.0"
        assert result.pages_crawled == 2
        assert result.pages_stored == 2
        assert result.duplicates_skipped == 0
        assert result.errors == 0

        mock_doc_repo.create.assert_called_once()
        assert mock_page_repo.create.call_count == 2

    @pytest.mark.asyncio
    async def test_crawl_and_store_existing_document(
        self, doc_manager, mock_doc_repo, mock_page_repo, mock_crawling_service
    ):
        """Test crawling when document already exists."""
        # Setup mocks
        existing_doc = MagicMock()
        existing_doc.id = 5
        mock_doc_repo.get_by_name_version.return_value = existing_doc

        crawl_result = MagicMock()
        crawl_result.results = [
            MagicMock(markdown="Content 1", url="https://example.com/page1"),
        ]
        mock_crawling_service.crawl_webpage.return_value = crawl_result

        mock_page_repo.get_by_url.return_value = None

        # Execute
        result = await doc_manager.crawl_and_store(
            name="test-doc", version="1.0.0", source_url="https://example.com"
        )

        # Verify
        assert result.document_id == 5
        assert result.pages_stored == 1

        mock_doc_repo.create.assert_not_called()
        mock_page_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_and_store_with_duplicates(
        self, doc_manager, mock_doc_repo, mock_page_repo, mock_crawling_service
    ):
        """Test crawling with duplicate pages."""
        # Setup mocks
        mock_doc_repo.get_by_name_version.return_value = None
        mock_doc_repo.create.return_value = 1

        crawl_result = MagicMock()
        crawl_result.results = [
            MagicMock(markdown="Content 1", url="https://example.com/page1"),
            MagicMock(markdown="Content 1", url="https://example.com/page1"),  # Duplicate
        ]
        mock_crawling_service.crawl_webpage.return_value = crawl_result

        mock_page_repo.get_by_url.return_value = (
            MagicMock()
        )  # First call returns existing, second returns None

        # Execute
        result = await doc_manager.crawl_and_store(
            name="test-doc", version="1.0.0", source_url="https://example.com"
        )

        # Verify
        assert result.pages_crawled == 2
        assert result.pages_stored == 0  # No new pages stored
        assert result.duplicates_skipped == 2

        mock_page_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_crawl_and_store_with_errors(
        self, doc_manager, mock_doc_repo, mock_page_repo, mock_crawling_service
    ):
        """Test crawling with page storage errors."""
        # Setup mocks
        mock_doc_repo.get_by_name_version.return_value = None
        mock_doc_repo.create.return_value = 1

        crawl_result = MagicMock()
        crawl_result.results = [
            MagicMock(markdown="Content 1", url="https://example.com/page1"),
        ]
        mock_crawling_service.crawl_webpage.return_value = crawl_result

        mock_page_repo.get_by_url.return_value = None
        mock_page_repo.create.side_effect = Exception("Database error")

        # Execute
        result = await doc_manager.crawl_and_store(
            name="test-doc", version="1.0.0", source_url="https://example.com"
        )

        # Verify
        assert result.pages_crawled == 1
        assert result.pages_stored == 0
        assert result.errors == 1

    @pytest.mark.asyncio
    async def test_list_pages(self, doc_manager, mock_page_repo):
        """Test listing pages for a document."""
        # Setup mocks
        mock_pages = [
            MagicMock(
                id=1,
                url="https://example.com/page1",
                content_length=1000,
                status="pending",
                crawled_at=MagicMock(),
            ),
            MagicMock(
                id=2,
                url="https://example.com/page2",
                content_length=2000,
                status="chunked",
                crawled_at=MagicMock(),
            ),
        ]
        mock_page_repo.list_by_document.return_value = mock_pages

        # Execute
        result = await doc_manager.list_pages(document_id=1, status="pending", offset=0, limit=10)

        # Verify
        assert len(result) == 2
        assert all(isinstance(p, PageInfo) for p in result)
        assert result[0].id == 1
        assert result[0].url == "https://example.com/page1"
        assert result[0].status == "pending"

        mock_page_repo.list_by_document.assert_called_once_with(
            1, status="pending", offset=0, limit=10
        )

    @pytest.mark.asyncio
    async def test_delete_page(self, doc_manager, mock_page_repo):
        """Test soft deleting a page."""
        # Setup mocks
        mock_page_repo.delete.return_value = True

        # Execute
        result = await doc_manager.delete_page(page_id=5)

        # Verify
        assert result is True
        mock_page_repo.delete.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_process_chunking_validation_success(self, doc_manager, mock_page_repo):
        """Test chunking processing with valid pages."""
        # Setup mocks
        mock_page_repo.validate_pages_for_chunking.return_value = (True, "", 3000)
        mock_page_repo.get_combined_content.return_value = "Combined content from multiple pages"

        # Execute
        result = await doc_manager.process_chunking(
            document_id=1, page_ids=[1, 2, 3], chunk_size=1000, batch_enabled=True
        )

        # Verify
        assert isinstance(result, ChunkProcessingResult)
        assert result.document_id == 1
        assert result.pages_processed == 3

        mock_page_repo.validate_pages_for_chunking.assert_called_once_with(
            [1, 2, 3], min_size=100, max_size=50000
        )
        mock_page_repo.update_status_bulk.assert_called_once_with([1, 2, 3], "processing")

    @pytest.mark.asyncio
    async def test_process_chunking_validation_failure(self, doc_manager, mock_page_repo):
        """Test chunking processing with invalid pages."""
        # Setup mocks
        mock_page_repo.validate_pages_for_chunking.return_value = (False, "Invalid pages", 0)

        # Execute and verify
        with pytest.raises(ValueError, match="Page validation failed: Invalid pages"):
            await doc_manager.process_chunking(document_id=1, page_ids=[1, 2, 3])

        mock_page_repo.validate_pages_for_chunking.assert_called_once()
        mock_page_repo.update_status_bulk.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_chunking_background_batch_mode(
        self,
        doc_manager,
        mock_page_repo,
        mock_chunk_repo,
        mock_chunking_service,
        mock_embedding_service,
    ):
        """Test background chunking processing in batch mode."""
        # Setup mocks
        mock_page_repo.get_combined_content.return_value = "Long combined content for chunking"
        mock_chunk_repo.create_batch.return_value = [1, 2, 3]
        mock_chunk_repo.get_max_chunk_index.return_value = 0

        # Execute background task
        group_id = uuid4()
        await doc_manager._process_chunking_background(
            document_id=1, page_ids=[1, 2], group_id=group_id, chunk_size=1000, batch_enabled=True
        )

        # Verify
        mock_chunking_service.smart_chunk_markdown.assert_called_once_with(
            "Long combined content for chunking", chunk_size=1000
        )
        mock_embedding_service.get_embeddings_batch.assert_called_once_with(
            ["Chunk 1", "Chunk 2", "Chunk 3"]
        )
        mock_chunk_repo.create_batch.assert_called_once()
        mock_page_repo.update_status_bulk.assert_called_with([1, 2], "chunked")

    @pytest.mark.asyncio
    async def test_process_chunking_background_single_mode(
        self,
        doc_manager,
        mock_page_repo,
        mock_chunk_repo,
        mock_chunking_service,
        mock_embedding_service,
    ):
        """Test background chunking processing in single mode."""
        # Setup mocks
        mock_page_repo.get_combined_content.return_value = "Content for chunking"
        mock_chunk_repo.get_max_chunk_index.return_value = 0

        # Execute background task
        group_id = uuid4()
        await doc_manager._process_chunking_background(
            document_id=1, page_ids=[1], group_id=group_id, chunk_size=1000, batch_enabled=False
        )

        # Verify
        mock_chunking_service.smart_chunk_markdown.assert_called_once()
        assert mock_embedding_service.get_embedding.call_count == 3  # Once per chunk
        assert mock_chunk_repo.create.call_count == 3  # Once per chunk
        mock_page_repo.update_status_bulk.assert_called_with([1], "chunked")

    @pytest.mark.asyncio
    async def test_process_chunking_background_with_errors(
        self,
        doc_manager,
        mock_page_repo,
        mock_chunking_service,
        mock_embedding_service,
        mock_chunk_repo,
    ):
        """Test background chunking processing with errors."""
        # Setup mocks
        mock_page_repo.get_combined_content.return_value = "Content"
        mock_chunk_repo.get_max_chunk_index.return_value = 0
        mock_embedding_service.get_embeddings_batch.side_effect = Exception("Embedding error")

        # Execute background task
        group_id = uuid4()
        await doc_manager._process_chunking_background(
            document_id=1, page_ids=[1], group_id=group_id, chunk_size=1000, batch_enabled=True
        )

        # Verify error handling
        mock_page_repo.update_status_bulk.assert_called_with(
            [1], "pending"
        )  # Reset to pending on error

    @pytest.mark.asyncio
    async def test_process_chunking_custom_chunk_size(
        self, doc_manager, mock_page_repo, mock_config
    ):
        """Test chunking processing with custom chunk size."""
        # Setup mocks
        mock_page_repo.validate_pages_for_chunking.return_value = (True, "", 2000)

        # Execute
        result = await doc_manager.process_chunking(
            document_id=1, page_ids=[1], chunk_size=500, batch_enabled=True  # Custom size
        )

        # Verify
        assert result.pages_processed == 1
        # Should use custom chunk size, not config default
        mock_page_repo.validate_pages_for_chunking.assert_called_once_with(
            [1], min_size=100, max_size=50000
        )
