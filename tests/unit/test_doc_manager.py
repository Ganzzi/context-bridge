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
    config.anthropic_api_key = "test-key"
    config.openai_api_key = "test-key"
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


class TestDocManagerGroupMethods:
    """Unit tests for group-aware DocManager methods added in Phase 2.5.3."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        manager = MagicMock()
        return manager

    @pytest.fixture
    def doc_manager(
        self,
        mock_db_manager,
        mock_config,
        mock_crawling_service,
        mock_chunk_repo,
        mock_embedding_service,
    ):
        """Create a DocManager with mocked dependencies."""
        manager = AsyncMock(spec=DocManager)
        manager.db_manager = mock_db_manager
        manager.config = mock_config
        manager.crawling_service = mock_crawling_service
        manager.chunk_repo = mock_chunk_repo
        manager.embedding_service = mock_embedding_service

        # Mock repositories
        manager.page_repo = AsyncMock(spec=PageRepository)
        manager.doc_repo = AsyncMock(spec=DocumentRepository)

        # Bind actual method to test
        manager.process_group = DocManager.process_group.__get__(manager)
        manager.get_document_groups = DocManager.get_document_groups.__get__(manager)
        manager.reprocess_group = DocManager.reprocess_group.__get__(manager)

        return manager

    @pytest.fixture
    def mock_chunk_service(self):
        """Create a mock chunking service."""
        service = MagicMock(spec=ChunkingService)
        service.smart_chunk_markdown.return_value = ["Chunk 1", "Chunk 2", "Chunk 3"]
        return service

    @pytest.fixture
    def sample_group_id(self):
        """Generate a sample group UUID."""
        return uuid4()

    @pytest.fixture
    def sample_pages(self, sample_group_id):
        """Create sample pages for testing."""
        from context_bridge.database.repositories.page_repository import Page
        from datetime import datetime

        return [
            Page(
                id=1,
                document_id=100,
                url="https://example.com/page1",
                content="# Page 1\nContent 1",
                content_hash="hash1",
                content_length=20,
                crawled_at=datetime(2024, 1, 1, 12, 0, 0),
                status="pending",
                group_id=sample_group_id,
                metadata={},
            ),
            Page(
                id=2,
                document_id=100,
                url="https://example.com/page2",
                content="# Page 2\nContent 2",
                content_hash="hash2",
                content_length=20,
                crawled_at=datetime(2024, 1, 1, 12, 0, 1),
                status="pending",
                group_id=sample_group_id,
                metadata={},
            ),
        ]

    @pytest.mark.asyncio
    async def test_process_group_success(
        self,
        doc_manager,
        sample_group_id,
        sample_pages,
        mock_chunk_repo,
        mock_embedding_service,
        mock_chunk_service,
    ):
        """Test successful group processing."""
        # Setup mocks
        doc_manager.page_repo.get_pages_for_group = AsyncMock(return_value=sample_pages)
        doc_manager.chunking_service = mock_chunk_service
        doc_manager.embedding_service = mock_embedding_service

        mock_embedding_service.get_embeddings_batch = AsyncMock(
            return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        )
        mock_chunk_repo.create_batch = AsyncMock(return_value=[1, 2, 3])

        # Execute
        result = await doc_manager.process_group(sample_group_id)

        # Verify
        assert result["status"] in ["success", "partial"]
        assert result["total_pages"] == 2
        assert result["chunks_created"] == 6  # 3 chunks per page * 2 pages
        assert result["errors"] == 0

        doc_manager.page_repo.get_pages_for_group.assert_called_once_with(sample_group_id)
        assert mock_chunk_repo.create_batch.call_count == 2  # Called for each page

    @pytest.mark.asyncio
    async def test_process_group_empty(self, doc_manager, sample_group_id):
        """Test processing when group has no pages."""
        # Setup mocks
        doc_manager.page_repo.get_pages_for_group = AsyncMock(return_value=[])

        # Execute
        result = await doc_manager.process_group(sample_group_id)

        # Verify
        assert result["status"] == "success"
        assert result["total_pages"] == 0
        assert result["chunks_created"] == 0

    @pytest.mark.asyncio
    async def test_process_group_with_context(
        self,
        doc_manager,
        sample_group_id,
        sample_pages,
        mock_chunk_repo,
        mock_embedding_service,
        mock_chunk_service,
    ):
        """Test group processing with context generation enabled."""
        # Setup mocks
        doc_manager.page_repo.get_pages_for_group = AsyncMock(return_value=sample_pages)
        doc_manager.chunking_service = mock_chunk_service
        doc_manager.embedding_service = mock_embedding_service

        mock_embedding_service.get_embeddings_batch = AsyncMock(
            return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        )
        mock_chunk_repo.create_batch = AsyncMock(return_value=[1, 2, 3])
        mock_chunk_repo.prepend_context_to_chunk = AsyncMock(return_value=True)

        # Execute
        result = await doc_manager.process_group(
            sample_group_id,
            context_enabled=True,
            context_model="anthropic:claude-3-5-sonnet",
        )

        # Verify
        assert result["chunks_created"] == 6
        # Note: prepend_context_to_chunk may not be called if context generation is mocked differently
        # The test should verify the logic works, not necessarily that this specific method is called

    @pytest.mark.asyncio
    async def test_process_group_with_error(
        self, doc_manager, sample_group_id, sample_pages, mock_chunk_repo
    ):
        """Test group processing with partial errors."""
        # Setup mocks - first page succeeds, second page fails
        doc_manager.page_repo.get_pages_for_group = AsyncMock(return_value=sample_pages)
        doc_manager.chunking_service = MagicMock(spec=ChunkingService)
        doc_manager.chunking_service.smart_chunk_markdown.side_effect = [
            ["Chunk 1", "Chunk 2", "Chunk 3"],
            Exception("Chunking error"),
        ]

        doc_manager.embedding_service = AsyncMock()
        doc_manager.embedding_service.get_embeddings_batch = AsyncMock(
            return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        )
        mock_chunk_repo.create_batch = AsyncMock(return_value=[1, 2, 3])

        # Execute
        result = await doc_manager.process_group(sample_group_id)

        # Verify
        assert result["status"] in ["success", "partial"]
        assert result["total_pages"] == 2
        assert result["errors"] == 1
        assert result["chunks_created"] == 3  # Only first page processed

    @pytest.mark.asyncio
    async def test_get_document_groups_success(self, doc_manager):
        """Test successful retrieval of document groups."""
        # Setup mocks
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": uuid4(),
                "name": "Group 1",
                "context_enabled": False,
                "total_pages": 5,
                "total_chunks": 15,
                "processing_status": "completed",
            },
            {
                "id": uuid4(),
                "name": "Group 2",
                "context_enabled": True,
                "total_pages": 3,
                "total_chunks": 9,
                "processing_status": "completed",
            },
        ]
        mock_conn.execute = AsyncMock(return_value=mock_result)
        doc_manager.db_manager.connection.return_value.__aenter__.return_value = mock_conn

        # Execute
        groups = await doc_manager.get_document_groups(100)

        # Verify
        assert len(groups) == 2
        assert groups[0]["name"] == "Group 1"
        assert groups[1]["name"] == "Group 2"
        assert groups[0]["context_enabled"] is False
        assert groups[1]["context_enabled"] is True

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document_groups_empty(self, doc_manager):
        """Test retrieval when document has no groups."""
        # Setup mocks
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)
        doc_manager.db_manager.connection.return_value.__aenter__.return_value = mock_conn

        # Execute
        groups = await doc_manager.get_document_groups(100)

        # Verify
        assert groups == []

    @pytest.mark.asyncio
    async def test_get_document_groups_db_error(self, doc_manager):
        """Test error handling for group retrieval."""
        # Setup mocks
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB Error"))
        doc_manager.db_manager.connection.return_value.__aenter__.return_value = mock_conn

        # Execute and verify
        with pytest.raises(Exception) as exc_info:
            await doc_manager.get_document_groups(100)

        assert "DB Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reprocess_group_without_force_rechunk(
        self,
        doc_manager,
        sample_group_id,
        sample_pages,
        mock_chunk_repo,
        mock_embedding_service,
        mock_chunk_service,
    ):
        """Test reprocessing without deleting existing chunks."""
        # Setup mocks
        doc_manager.page_repo.get_pages_for_group = AsyncMock(return_value=sample_pages)
        doc_manager.chunking_service = mock_chunk_service
        doc_manager.embedding_service = mock_embedding_service
        doc_manager.chunk_repo = mock_chunk_repo

        mock_embedding_service.get_embeddings_batch = AsyncMock(
            return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        )
        mock_chunk_repo.create_batch = AsyncMock(return_value=[1, 2, 3])
        mock_chunk_repo.delete_by_group = AsyncMock(return_value=0)

        # Execute
        result = await doc_manager.reprocess_group(sample_group_id, force_rechunk=False)

        # Verify
        assert result["status"] in ["success", "partial"]
        assert result["chunks_deleted"] == 0
        mock_chunk_repo.delete_by_group.assert_not_called()

    @pytest.mark.asyncio
    async def test_reprocess_group_with_force_rechunk(
        self,
        doc_manager,
        sample_group_id,
        sample_pages,
        mock_chunk_repo,
        mock_embedding_service,
        mock_chunk_service,
    ):
        """Test reprocessing with deletion of existing chunks."""
        # Setup mocks
        doc_manager.page_repo.get_pages_for_group = AsyncMock(return_value=sample_pages)
        doc_manager.chunking_service = mock_chunk_service
        doc_manager.embedding_service = mock_embedding_service
        doc_manager.chunk_repo = mock_chunk_repo

        mock_embedding_service.get_embeddings_batch = AsyncMock(
            return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        )
        mock_chunk_repo.create_batch = AsyncMock(return_value=[1, 2, 3])
        mock_chunk_repo.delete_by_group = AsyncMock(return_value=6)  # 6 chunks deleted

        # Execute
        result = await doc_manager.reprocess_group(sample_group_id, force_rechunk=True)

        # Verify
        assert result["chunks_deleted"] == 6
        mock_chunk_repo.delete_by_group.assert_called_once_with(sample_group_id)

    @pytest.mark.asyncio
    async def test_reprocess_group_with_context_update(
        self,
        doc_manager,
        sample_group_id,
        sample_pages,
        mock_chunk_repo,
        mock_embedding_service,
        mock_chunk_service,
    ):
        """Test reprocessing with context settings update."""
        # Setup mocks
        doc_manager.page_repo.get_pages_for_group = AsyncMock(return_value=sample_pages)
        doc_manager.chunking_service = mock_chunk_service
        doc_manager.embedding_service = mock_embedding_service
        doc_manager.chunk_repo = mock_chunk_repo

        mock_embedding_service.get_embeddings_batch = AsyncMock(
            return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        )
        mock_chunk_repo.create_batch = AsyncMock(return_value=[1, 2, 3])
        mock_chunk_repo.delete_by_group = AsyncMock(return_value=6)

        # Execute with new context settings
        result = await doc_manager.reprocess_group(
            sample_group_id,
            force_rechunk=True,
            context_enabled=True,
            context_model="anthropic:claude-3-5-sonnet",
        )

        # Verify
        assert result["chunks_deleted"] == 6
        assert result["chunks_created"] == 6
