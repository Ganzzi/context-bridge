"""
Unit tests for ReprocessingService.

Tests cover:
- Reprocessing single groups
- Batch reprocessing multiple groups
- Context generation during reprocessing
- Error handling and recovery
- Status transitions
- Group validation
"""

import pytest
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from context_bridge.config import Config
from context_bridge.database.models.group_models import Group, ProcessingStatus
from context_bridge.service.reprocessing_service import ReprocessingService


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = MagicMock(spec=Config)
    config.chunk_size = 2000
    config.context_agent_model = "anthropic:claude-3-5-sonnet-20241022"
    config.anthropic_api_key = None
    config.openai_api_key = None
    return config


@pytest.fixture
def mock_db_manager():
    """Create mock database manager."""
    return AsyncMock()


@pytest.fixture
def mock_chunking_service():
    """Create mock chunking service."""
    service = AsyncMock()
    service.chunk_markdown = AsyncMock()
    return service


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    service = AsyncMock()
    service.embed_batch = AsyncMock()
    return service


@pytest.fixture
def reprocessing_service(
    mock_db_manager,
    mock_chunking_service,
    mock_embedding_service,
    mock_config,
):
    """Create ReprocessingService instance with mocked dependencies."""
    service = ReprocessingService(
        db_manager=mock_db_manager,
        chunking_service=mock_chunking_service,
        embedding_service=mock_embedding_service,
        config=mock_config,
    )

    # Mock repositories
    service.group_repo = AsyncMock()
    service.chunk_repo = AsyncMock()
    service.page_repo = AsyncMock()
    service.context_agent = None  # Disable context agent for basic tests

    return service


class TestReprocessingServiceInitialization:
    """Tests for ReprocessingService initialization."""

    def test_initialization_with_all_dependencies(
        self,
        mock_db_manager,
        mock_chunking_service,
        mock_embedding_service,
        mock_config,
    ):
        """Test that service initializes with all required dependencies."""
        service = ReprocessingService(
            db_manager=mock_db_manager,
            chunking_service=mock_chunking_service,
            embedding_service=mock_embedding_service,
            config=mock_config,
        )

        assert service.db_manager is mock_db_manager
        assert service.chunking_service is mock_chunking_service
        assert service.embedding_service is mock_embedding_service
        assert service.config is mock_config

    def test_initialization_creates_repositories(
        self,
        mock_db_manager,
        mock_chunking_service,
        mock_embedding_service,
        mock_config,
    ):
        """Test that initialization creates repository instances."""
        service = ReprocessingService(
            db_manager=mock_db_manager,
            chunking_service=mock_chunking_service,
            embedding_service=mock_embedding_service,
            config=mock_config,
        )

        assert service.group_repo is not None
        assert service.chunk_repo is not None
        assert service.page_repo is not None


class TestReprocessGroupBasic:
    """Tests for basic reprocess_group functionality."""

    @pytest.mark.asyncio
    async def test_reprocess_group_success(self, reprocessing_service):
        """Test successful group reprocessing."""
        group_id = uuid4()

        # Mock group
        group = Group(
            id=group_id,
            document_id=1,
            name="Test Group",
            description="Test description",
            context_enabled=False,
            context_model=None,
            combined_content_length=1000,
            total_pages=2,
            total_chunks=5,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_service.group_repo.get_group_by_id.return_value = group
        reprocessing_service.group_repo.update_group = AsyncMock()

        # Mock pages
        mock_page = MagicMock()
        mock_page.title = "Page 1"
        mock_page.content = "Page content"
        reprocessing_service.page_repo.get_pages_for_group.return_value = [mock_page]

        # Mock chunks
        mock_chunk = MagicMock()
        mock_chunk.content = "Chunk content"
        reprocessing_service.chunking_service.chunk_markdown.return_value = [mock_chunk]

        # Mock embeddings
        reprocessing_service.embedding_service.embed_batch.return_value = [[0.1] * 768]

        # Mock chunk storage
        reprocessing_service.chunk_repo.create_chunk = AsyncMock()

        # Execute
        result = await reprocessing_service.reprocess_group(group_id)

        # Verify
        assert result["status"] == "success"
        assert result["group_id"] == str(group_id)
        assert result["chunks_created"] == 1
        assert result["context_enabled"] is False

    @pytest.mark.asyncio
    async def test_reprocess_group_not_found(self, reprocessing_service):
        """Test reprocessing non-existent group."""
        group_id = uuid4()
        reprocessing_service.group_repo.get_group_by_id.return_value = None

        with pytest.raises(RuntimeError, match="not found"):
            await reprocessing_service.reprocess_group(group_id)

    @pytest.mark.asyncio
    async def test_reprocess_group_no_pages(self, reprocessing_service):
        """Test reprocessing group with no pages."""
        group_id = uuid4()

        # Mock group
        group = Group(
            id=group_id,
            document_id=1,
            name="Empty Group",
            description=None,
            context_enabled=False,
            context_model=None,
            combined_content_length=0,
            total_pages=0,
            total_chunks=0,
            created_at=datetime.now(timezone.utc),
            processed_at=None,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_service.group_repo.get_group_by_id.return_value = group
        reprocessing_service.page_repo.get_pages_for_group.return_value = []

        with pytest.raises(RuntimeError, match="No pages found"):
            await reprocessing_service.reprocess_group(group_id)

    @pytest.mark.asyncio
    async def test_reprocess_group_status_transitions(self, reprocessing_service):
        """Test status transitions during reprocessing."""
        group_id = uuid4()

        # Mock group
        group = Group(
            id=group_id,
            document_id=1,
            name="Test Group",
            description=None,
            context_enabled=False,
            context_model=None,
            combined_content_length=1000,
            total_pages=1,
            total_chunks=1,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_service.group_repo.get_group_by_id.return_value = group
        reprocessing_service.group_repo.update_group = AsyncMock()

        # Mock page and chunking
        mock_page = MagicMock()
        mock_page.content = "Test content"
        mock_page.title = "Test"
        reprocessing_service.page_repo.get_pages_for_group.return_value = [mock_page]

        mock_chunk = MagicMock()
        mock_chunk.content = "Chunk"
        reprocessing_service.chunking_service.chunk_markdown.return_value = [mock_chunk]

        reprocessing_service.embedding_service.embed_batch.return_value = [[0.1] * 768]
        reprocessing_service.chunk_repo.create_chunk = AsyncMock()

        # Execute
        await reprocessing_service.reprocess_group(group_id)

        # Verify status transitions
        calls = reprocessing_service.group_repo.update_group.call_args_list

        # First call should set to REPROCESSING
        assert calls[0][1]["updates"]["processing_status"] == ProcessingStatus.REPROCESSING

        # Final call should set to COMPLETED
        assert calls[-1][1]["updates"]["processing_status"] == ProcessingStatus.COMPLETED


class TestReprocessGroupWithContext:
    """Tests for reprocessing with context generation."""

    @pytest.mark.asyncio
    async def test_reprocess_with_context_enabled(self, reprocessing_service):
        """Test reprocessing with context generation enabled."""
        group_id = uuid4()

        # Enable context agent
        reprocessing_service.context_agent = AsyncMock()
        reprocessing_service.context_agent.generate_contexts_batch = AsyncMock(
            return_value=["Context 1", "Context 2"]
        )

        # Mock group
        group = Group(
            id=group_id,
            document_id=1,
            name="Test Group",
            description=None,
            context_enabled=False,
            context_model=None,
            combined_content_length=1000,
            total_pages=1,
            total_chunks=2,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_service.group_repo.get_group_by_id.return_value = group
        reprocessing_service.group_repo.update_group = AsyncMock()

        # Mock pages
        mock_page = MagicMock()
        mock_page.content = "Test content"
        mock_page.title = "Test"
        reprocessing_service.page_repo.get_pages_for_group.return_value = [mock_page]

        # Mock chunks
        chunks = [MagicMock(content="Chunk 1"), MagicMock(content="Chunk 2")]
        reprocessing_service.chunking_service.chunk_markdown.return_value = chunks

        reprocessing_service.embedding_service.embed_batch.return_value = [
            [0.1] * 768,
            [0.2] * 768,
        ]

        reprocessing_service.chunk_repo.create_chunk = AsyncMock()

        # Execute
        result = await reprocessing_service.reprocess_group(
            group_id,
            context_enabled=True,
            context_model="anthropic:claude-3-5-sonnet-20241022",
        )

        # Verify
        assert result["context_enabled"] is True
        assert result["contexts_generated"] == 2

        # Verify context_agent was called
        reprocessing_service.context_agent.generate_contexts_batch.assert_called_once()


class TestReprocessMultipleGroups:
    """Tests for batch reprocessing."""

    @pytest.mark.asyncio
    async def test_reprocess_multiple_groups_success(self, reprocessing_service):
        """Test successful batch reprocessing."""
        group_ids = [uuid4(), uuid4()]

        # Mock groups
        groups = []
        for group_id in group_ids:
            group = Group(
                id=group_id,
                document_id=1,
                name=f"Group {group_id}",
                description=None,
                context_enabled=False,
                context_model=None,
                combined_content_length=1000,
                total_pages=1,
                total_chunks=1,
                created_at=datetime.now(timezone.utc),
                processed_at=datetime.now(timezone.utc),
                processing_status=ProcessingStatus.COMPLETED,
                metadata={},
            )
            groups.append(group)

        reprocessing_service.group_repo.get_group_by_id = AsyncMock(side_effect=groups)
        reprocessing_service.group_repo.update_group = AsyncMock()

        # Mock pages
        mock_page = MagicMock()
        mock_page.content = "Test content"
        mock_page.title = "Test"
        reprocessing_service.page_repo.get_pages_for_group.return_value = [mock_page]

        # Mock chunks
        mock_chunk = MagicMock()
        mock_chunk.content = "Chunk"
        reprocessing_service.chunking_service.chunk_markdown.return_value = [mock_chunk]

        reprocessing_service.embedding_service.embed_batch.return_value = [[0.1] * 768]
        reprocessing_service.chunk_repo.create_chunk = AsyncMock()

        # Execute
        result = await reprocessing_service.reprocess_multiple_groups(group_ids)

        # Verify
        assert result["status"] == "success"
        assert result["total_groups"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_reprocess_multiple_groups_partial_failure(self, reprocessing_service):
        """Test batch reprocessing with partial failures."""
        group_ids = [uuid4(), uuid4()]

        # First group succeeds, second fails
        def side_effect(group_id):
            group = Group(
                id=group_id,
                document_id=1,
                name=f"Group {group_id}",
                description=None,
                context_enabled=False,
                context_model=None,
                combined_content_length=1000,
                total_pages=0 if group_id == group_ids[1] else 1,
                total_chunks=1,
                created_at=datetime.now(timezone.utc),
                processed_at=datetime.now(timezone.utc),
                processing_status=ProcessingStatus.COMPLETED,
                metadata={},
            )
            return group

        reprocessing_service.group_repo.get_group_by_id = AsyncMock(side_effect=side_effect)
        reprocessing_service.group_repo.update_group = AsyncMock()

        # Only first group has pages
        pages_called = False

        async def get_pages_side_effect(group_id):
            nonlocal pages_called
            if not pages_called and group_id == group_ids[0]:
                pages_called = True
                mock_page = MagicMock()
                mock_page.content = "Test content"
                mock_page.title = "Test"
                return [mock_page]
            return []

        reprocessing_service.page_repo.get_pages_for_group = AsyncMock(
            side_effect=get_pages_side_effect
        )

        # Mock chunks
        mock_chunk = MagicMock()
        mock_chunk.content = "Chunk"
        reprocessing_service.chunking_service.chunk_markdown.return_value = [mock_chunk]

        reprocessing_service.embedding_service.embed_batch.return_value = [[0.1] * 768]
        reprocessing_service.chunk_repo.create_chunk = AsyncMock()

        # Execute
        result = await reprocessing_service.reprocess_multiple_groups(
            group_ids,
            continue_on_error=True,
        )

        # Verify
        assert result["total_groups"] == 2
        assert result["successful"] == 1
        assert result["failed"] == 1


class TestListReprocessableGroups:
    """Tests for listing reprocessable groups."""

    @pytest.mark.asyncio
    async def test_list_reprocessable_groups_empty(self, reprocessing_service):
        """Test listing when no reprocessable groups exist."""
        reprocessing_service.group_repo.list_groups.return_value = []

        result = await reprocessing_service.list_reprocessable_groups()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_reprocessable_groups_with_results(self, reprocessing_service):
        """Test listing reprocessable groups."""
        group = Group(
            id=uuid4(),
            document_id=1,
            name="Reprocessable Group",
            description="Test description",
            context_enabled=False,
            context_model=None,
            combined_content_length=1000,
            total_pages=5,
            total_chunks=10,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_service.group_repo.list_groups.return_value = [group]

        result = await reprocessing_service.list_reprocessable_groups(document_id=1)

        assert len(result) == 1
        assert result[0]["id"] == str(group.id)
        assert result[0]["context_enabled"] is False
        assert result[0]["total_pages"] == 5

    @pytest.mark.asyncio
    async def test_list_reprocessable_groups_filters_context_enabled(
        self,
        reprocessing_service,
    ):
        """Test that context-enabled groups are filtered out."""
        context_group = Group(
            id=uuid4(),
            document_id=1,
            name="Already Context Enabled",
            description=None,
            context_enabled=True,
            context_model="anthropic:claude-3-5-sonnet-20241022",
            combined_content_length=1000,
            total_pages=5,
            total_chunks=10,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_group = Group(
            id=uuid4(),
            document_id=1,
            name="Reprocessable Group",
            description=None,
            context_enabled=False,
            context_model=None,
            combined_content_length=1000,
            total_pages=5,
            total_chunks=10,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_service.group_repo.list_groups.return_value = [
            context_group,
            reprocessing_group,
        ]

        result = await reprocessing_service.list_reprocessable_groups(document_id=1)

        # Should only return the non-context-enabled group
        assert len(result) == 1
        assert result[0]["context_enabled"] is False


class TestErrorHandling:
    """Tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_reprocess_group_handles_chunk_storage_error(self, reprocessing_service):
        """Test proper error handling when chunk storage fails."""
        group_id = uuid4()

        # Mock group
        group = Group(
            id=group_id,
            document_id=1,
            name="Test Group",
            description=None,
            context_enabled=False,
            context_model=None,
            combined_content_length=1000,
            total_pages=1,
            total_chunks=1,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_service.group_repo.get_group_by_id.return_value = group
        reprocessing_service.group_repo.update_group = AsyncMock(
            side_effect=Exception("Update failed")
        )

        # Mock pages
        mock_page = MagicMock()
        mock_page.content = "Test content"
        mock_page.title = "Test"
        reprocessing_service.page_repo.get_pages_for_group.return_value = [mock_page]

        # Mock chunks
        mock_chunk = MagicMock()
        mock_chunk.content = "Chunk"
        reprocessing_service.chunking_service.chunk_markdown.return_value = [mock_chunk]

        reprocessing_service.embedding_service.embed_batch.return_value = [[0.1] * 768]
        reprocessing_service.chunk_repo.create_chunk = AsyncMock()

        # Execute - should raise RuntimeError
        with pytest.raises(RuntimeError):
            await reprocessing_service.reprocess_group(group_id)

        # Verify status was updated to FAILED
        failed_call = [
            call
            for call in reprocessing_service.group_repo.update_group.call_args_list
            if call[1]["updates"]["processing_status"] == ProcessingStatus.FAILED
        ]
        assert len(failed_call) > 0

    @pytest.mark.asyncio
    async def test_reprocess_group_deletes_chunks_when_requested(self, reprocessing_service):
        """Test that chunks are deleted when force_delete_chunks is True."""
        group_id = uuid4()

        # Mock group
        group = Group(
            id=group_id,
            document_id=1,
            name="Test Group",
            description=None,
            context_enabled=False,
            context_model=None,
            combined_content_length=1000,
            total_pages=1,
            total_chunks=5,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        )

        reprocessing_service.group_repo.get_group_by_id.return_value = group
        reprocessing_service.group_repo.update_group = AsyncMock()
        reprocessing_service.chunk_repo.delete_by_group = AsyncMock(return_value=5)

        # Mock pages
        mock_page = MagicMock()
        mock_page.content = "Test content"
        mock_page.title = "Test"
        reprocessing_service.page_repo.get_pages_for_group.return_value = [mock_page]

        # Mock chunks
        mock_chunk = MagicMock()
        mock_chunk.content = "Chunk"
        reprocessing_service.chunking_service.chunk_markdown.return_value = [mock_chunk]

        reprocessing_service.embedding_service.embed_batch.return_value = [[0.1] * 768]
        reprocessing_service.chunk_repo.create_chunk = AsyncMock()

        # Execute with force_delete_chunks=True
        await reprocessing_service.reprocess_group(
            group_id,
            force_delete_chunks=True,
        )

        # Verify delete was called
        reprocessing_service.chunk_repo.delete_by_group.assert_called_once_with(group_id)


class TestCombinePageContent:
    """Tests for page content combination."""

    @pytest.mark.asyncio
    async def test_combine_page_content_single_page(self, reprocessing_service):
        """Test combining content from a single page."""
        mock_page = MagicMock()
        mock_page.title = "Test Page"
        mock_page.content = "Page content here"

        result = await reprocessing_service._combine_page_content([mock_page])

        assert "# Test Page" in result
        assert "Page content here" in result

    @pytest.mark.asyncio
    async def test_combine_page_content_multiple_pages(self, reprocessing_service):
        """Test combining content from multiple pages."""
        pages = []
        for i in range(3):
            mock_page = MagicMock()
            mock_page.title = f"Page {i+1}"
            mock_page.content = f"Content {i+1}"
            pages.append(mock_page)

        result = await reprocessing_service._combine_page_content(pages)

        assert "# Page 1" in result
        assert "# Page 2" in result
        assert "# Page 3" in result
        assert "---" in result  # Separator between pages

    @pytest.mark.asyncio
    async def test_combine_page_content_skips_empty(self, reprocessing_service):
        """Test that pages with empty content are skipped."""
        pages = [
            MagicMock(title="Page 1", content="Content 1"),
            MagicMock(title="Page 2", content=None),  # Empty
            MagicMock(title="Page 3", content="Content 3"),
        ]

        result = await reprocessing_service._combine_page_content(pages)

        assert "# Page 1" in result
        assert "# Page 3" in result
        # Page 2 should not be included
        assert "# Page 2" not in result
