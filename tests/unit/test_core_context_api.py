"""
Unit tests for Core API context generation methods.

Tests cover:
- Updated process_pages with context parameters
- generate_context_for_group method
- list_non_context_groups method
- Configuration passing to lower layers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from context_bridge.config import Config
from context_bridge.core import ContextBridge
from context_bridge.database.models.group_models import Group, ProcessingStatus


@pytest.fixture
def mock_config():
    """Fixture providing test configuration."""
    return Config(
        context_agent_model="anthropic:claude-3-5-sonnet-20241022",
        context_agent_temperature=0.3,
        context_agent_max_tokens=500,
    )


@pytest.fixture
def mock_db_manager():
    """Fixture providing mocked database manager."""
    manager = MagicMock()
    return manager


@pytest.fixture
async def context_bridge(mock_config, mock_db_manager):
    """Fixture providing a ContextBridge instance with mocked dependencies."""
    with patch("context_bridge.core.PostgreSQLManager", return_value=mock_db_manager):
        with patch("context_bridge.core.CrawlingService"):
            with patch("context_bridge.core.ChunkingService"):
                with patch("context_bridge.core.EmbeddingService"):
                    with patch("context_bridge.core.SearchService"):
                        with patch("context_bridge.core.UrlService"):
                            with patch("context_bridge.core.DocumentRepository"):
                                with patch("context_bridge.core.ChunkRepository"):
                                    with patch("context_bridge.core.TagRepository"):
                                        with patch(
                                            "context_bridge.core.GroupRepository"
                                        ) as mock_group_repo_class:
                                            with patch(
                                                "context_bridge.core.DocManager"
                                            ) as mock_doc_manager_class:
                                                bridge = ContextBridge(mock_config)

                                                # Mock the repositories and services
                                                bridge._group_repository = AsyncMock()
                                                bridge._doc_manager = AsyncMock()
                                                bridge._initialized = True

                                                yield bridge


class TestProcessPagesWithContext:
    """Tests for updated process_pages method with context parameters."""

    @pytest.mark.asyncio
    async def test_process_pages_without_context(self, context_bridge):
        """Test process_pages without context generation."""
        document_id = 1
        page_ids = [1, 2, 3]

        # Mock DocManager response
        context_bridge._doc_manager.process_chunking.return_value = {
            "document_id": 1,
            "pages_processed": 3,
        }

        result = await context_bridge.process_pages(document_id=document_id, page_ids=page_ids)

        context_bridge._doc_manager.process_chunking.assert_called_once()
        call_kwargs = context_bridge._doc_manager.process_chunking.call_args[1]

        assert call_kwargs["context_enabled"] is False
        assert call_kwargs["context_model"] == context_bridge.config.context_agent_model

    @pytest.mark.asyncio
    async def test_process_pages_with_context_enabled(self, context_bridge):
        """Test process_pages with context generation enabled."""
        document_id = 1
        page_ids = [1, 2, 3]

        context_bridge._doc_manager.process_chunking.return_value = {
            "document_id": 1,
            "pages_processed": 3,
        }

        result = await context_bridge.process_pages(
            document_id=document_id,
            page_ids=page_ids,
            context_enabled=True,
        )

        call_kwargs = context_bridge._doc_manager.process_chunking.call_args[1]

        assert call_kwargs["context_enabled"] is True
        assert call_kwargs["context_model"] == context_bridge.config.context_agent_model

    @pytest.mark.asyncio
    async def test_process_pages_with_custom_context_model(self, context_bridge):
        """Test process_pages with custom context model override."""
        document_id = 1
        page_ids = [1, 2, 3]
        custom_model = "openai:gpt-4"

        context_bridge._doc_manager.process_chunking.return_value = {
            "document_id": 1,
            "pages_processed": 3,
        }

        result = await context_bridge.process_pages(
            document_id=document_id,
            page_ids=page_ids,
            context_enabled=True,
            context_model=custom_model,
        )

        call_kwargs = context_bridge._doc_manager.process_chunking.call_args[1]

        assert call_kwargs["context_enabled"] is True
        assert call_kwargs["context_model"] == custom_model

    @pytest.mark.asyncio
    async def test_process_pages_not_initialized(self, mock_config):
        """Test process_pages raises error when not initialized."""
        with patch("context_bridge.core.PostgreSQLManager"):
            with patch("context_bridge.core.CrawlingService"):
                with patch("context_bridge.core.ChunkingService"):
                    with patch("context_bridge.core.EmbeddingService"):
                        with patch("context_bridge.core.SearchService"):
                            with patch("context_bridge.core.UrlService"):
                                with patch("context_bridge.core.DocumentRepository"):
                                    with patch("context_bridge.core.ChunkRepository"):
                                        with patch("context_bridge.core.TagRepository"):
                                            with patch("context_bridge.core.GroupRepository"):
                                                with patch("context_bridge.core.DocManager"):
                                                    bridge = ContextBridge(mock_config)

                                                    # Not initialized
                                                    with pytest.raises(RuntimeError):
                                                        await bridge.process_pages(1, [1, 2])


class TestGenerateContextForGroup:
    """Tests for generate_context_for_group method."""

    @pytest.mark.asyncio
    async def test_generate_context_success(self, context_bridge):
        """Test successful context generation for a group."""
        group_id = str(uuid4())
        parsed_id = UUID(group_id)

        # Mock group
        mock_group = MagicMock(spec=Group)
        mock_group.id = parsed_id
        mock_group.context_enabled = False

        context_bridge._group_repository.get_group_by_id.return_value = mock_group
        context_bridge._doc_manager.process_group.return_value = {
            "status": "success",
            "chunks_created": 10,
            "errors": 0,
        }

        result = await context_bridge.generate_context_for_group(group_id)

        assert result["status"] == "success"
        assert result["chunks_processed"] == 10
        assert result["chunks_failed"] == 0
        assert "context_model" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_generate_context_with_custom_model(self, context_bridge):
        """Test context generation with custom model override."""
        group_id = str(uuid4())
        parsed_id = UUID(group_id)
        custom_model = "openai:gpt-4"

        mock_group = MagicMock(spec=Group)
        mock_group.id = parsed_id

        context_bridge._group_repository.get_group_by_id.return_value = mock_group
        context_bridge._doc_manager.process_group.return_value = {
            "status": "success",
            "chunks_created": 5,
            "errors": 0,
        }

        result = await context_bridge.generate_context_for_group(
            group_id, context_model=custom_model
        )

        assert result["context_model"] == custom_model

        # Verify DocManager was called with correct model
        call_kwargs = context_bridge._doc_manager.process_group.call_args[1]
        assert call_kwargs["context_model"] == custom_model

    @pytest.mark.asyncio
    async def test_generate_context_invalid_group_id(self, context_bridge):
        """Test error handling for invalid group ID format."""
        with pytest.raises(ValueError, match="Invalid group ID format"):
            await context_bridge.generate_context_for_group("not-a-uuid")

    @pytest.mark.asyncio
    async def test_generate_context_group_not_found(self, context_bridge):
        """Test error handling when group not found."""
        group_id = str(uuid4())

        context_bridge._group_repository.get_group_by_id.return_value = None

        with pytest.raises(ValueError, match="Group not found"):
            await context_bridge.generate_context_for_group(group_id)

    @pytest.mark.asyncio
    async def test_generate_context_not_initialized(self, mock_config):
        """Test error when ContextBridge not initialized."""
        with patch("context_bridge.core.PostgreSQLManager"):
            with patch("context_bridge.core.CrawlingService"):
                with patch("context_bridge.core.ChunkingService"):
                    with patch("context_bridge.core.EmbeddingService"):
                        with patch("context_bridge.core.SearchService"):
                            with patch("context_bridge.core.UrlService"):
                                with patch("context_bridge.core.DocumentRepository"):
                                    with patch("context_bridge.core.ChunkRepository"):
                                        with patch("context_bridge.core.TagRepository"):
                                            with patch("context_bridge.core.GroupRepository"):
                                                with patch("context_bridge.core.DocManager"):
                                                    bridge = ContextBridge(mock_config)

                                                    with pytest.raises(RuntimeError):
                                                        await bridge.generate_context_for_group(
                                                            str(uuid4())
                                                        )

    @pytest.mark.asyncio
    async def test_generate_context_partial_failure(self, context_bridge):
        """Test context generation with partial failures."""
        group_id = str(uuid4())
        parsed_id = UUID(group_id)

        mock_group = MagicMock(spec=Group)
        mock_group.id = parsed_id

        context_bridge._group_repository.get_group_by_id.return_value = mock_group
        context_bridge._doc_manager.process_group.return_value = {
            "status": "partial",
            "chunks_created": 8,
            "errors": 2,
        }

        result = await context_bridge.generate_context_for_group(group_id)

        assert result["status"] == "partial"
        assert result["chunks_processed"] == 8
        assert result["chunks_failed"] == 2


class TestListNonContextGroups:
    """Tests for list_non_context_groups method."""

    @pytest.mark.asyncio
    async def test_list_non_context_groups_all(self, context_bridge):
        """Test listing all non-context groups."""
        # Create mock groups
        group1 = MagicMock(spec=Group)
        group1.id = uuid4()
        group1.document_id = 1
        group1.name = "Group 1"
        group1.total_pages = 5
        group1.total_chunks = 20
        group1.processing_status = ProcessingStatus.COMPLETED
        group1.created_at = datetime.now()

        group2 = MagicMock(spec=Group)
        group2.id = uuid4()
        group2.document_id = 1
        group2.name = "Group 2"
        group2.total_pages = 3
        group2.total_chunks = 15
        group2.processing_status = ProcessingStatus.COMPLETED
        group2.created_at = datetime.now()

        context_bridge._group_repository.get_non_context_groups.return_value = [
            group1,
            group2,
        ]

        result = await context_bridge.list_non_context_groups()

        assert len(result) == 2
        assert result[0]["name"] == "Group 1"
        assert result[1]["name"] == "Group 2"

        # Verify repository was called without document_id filter
        context_bridge._group_repository.get_non_context_groups.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_list_non_context_groups_by_document(self, context_bridge):
        """Test listing non-context groups for specific document."""
        document_id = 1

        group = MagicMock(spec=Group)
        group.id = uuid4()
        group.document_id = document_id
        group.name = "Document Group"
        group.total_pages = 2
        group.total_chunks = 10
        group.processing_status = ProcessingStatus.COMPLETED
        group.created_at = datetime.now()

        context_bridge._group_repository.get_non_context_groups.return_value = [group]

        result = await context_bridge.list_non_context_groups(document_id=document_id)

        assert len(result) == 1
        assert result[0]["document_id"] == document_id

        # Verify repository was called with document_id filter
        context_bridge._group_repository.get_non_context_groups.assert_called_once_with(document_id)

    @pytest.mark.asyncio
    async def test_list_non_context_groups_empty(self, context_bridge):
        """Test listing when no non-context groups exist."""
        context_bridge._group_repository.get_non_context_groups.return_value = []

        result = await context_bridge.list_non_context_groups()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_non_context_groups_not_initialized(self, mock_config):
        """Test error when ContextBridge not initialized."""
        with patch("context_bridge.core.PostgreSQLManager"):
            with patch("context_bridge.core.CrawlingService"):
                with patch("context_bridge.core.ChunkingService"):
                    with patch("context_bridge.core.EmbeddingService"):
                        with patch("context_bridge.core.SearchService"):
                            with patch("context_bridge.core.UrlService"):
                                with patch("context_bridge.core.DocumentRepository"):
                                    with patch("context_bridge.core.ChunkRepository"):
                                        with patch("context_bridge.core.TagRepository"):
                                            with patch("context_bridge.core.GroupRepository"):
                                                with patch("context_bridge.core.DocManager"):
                                                    bridge = ContextBridge(mock_config)

                                                    with pytest.raises(RuntimeError):
                                                        await bridge.list_non_context_groups()

    @pytest.mark.asyncio
    async def test_list_non_context_groups_returns_formatted_data(self, context_bridge):
        """Test that returned data has correct format and fields."""
        group = MagicMock(spec=Group)
        group.id = uuid4()
        group.document_id = 1
        group.name = "Test Group"
        group.total_pages = 5
        group.total_chunks = 25
        group.processing_status = ProcessingStatus.COMPLETED
        group.created_at = datetime(2025, 11, 16, 12, 0, 0)

        context_bridge._group_repository.get_non_context_groups.return_value = [group]

        result = await context_bridge.list_non_context_groups()

        assert len(result) == 1
        group_data = result[0]

        # Verify all required fields are present
        assert "id" in group_data
        assert "document_id" in group_data
        assert "name" in group_data
        assert "total_pages" in group_data
        assert "total_chunks" in group_data
        assert "processing_status" in group_data
        assert "created_at" in group_data

        # Verify data types
        assert isinstance(group_data["id"], str)
        assert isinstance(group_data["document_id"], int)
        assert isinstance(group_data["total_pages"], int)
        assert isinstance(group_data["created_at"], str)
