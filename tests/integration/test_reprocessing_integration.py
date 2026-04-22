"""
Integration Tests for ReprocessingService and Core API

Tests complete re-processing workflows including:
- Full re-processing pipeline with context generation
- Batch re-processing operations
- Group state transitions and error recovery
- Integration with ContextBridge core API
"""

import pytest
from uuid import UUID
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from context_bridge.core import ContextBridge
from context_bridge.service.reprocessing_service import ReprocessingService
from context_bridge.database.models.group_models import Group, ProcessingStatus


@pytest.fixture
def mock_db_manager():
    """Mock PostgreSQLManager"""
    manager = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    manager.connection = MagicMock(return_value=mock_conn)
    return manager


@pytest.fixture
def mock_chunking_service():
    """Mock ChunkingService"""
    service = MagicMock()
    service.smart_chunk_markdown = MagicMock(return_value=["Chunk 1", "Chunk 2"])
    return service


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService"""
    service = AsyncMock()
    service.get_embeddings_batch = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])
    return service


@pytest.fixture
def mock_config():
    """Mock Config"""
    config = MagicMock()
    config.chunk_size = 2000
    config.anthropic_api_key = "test-key"
    config.openai_api_key = "test-key"
    config.embedding_dimension = 768
    return config


def _make_mock_page(page_id, content, title="Test Page"):
    """Create a mock Page object."""
    page = MagicMock()
    page.id = page_id
    page.content = content
    page.title = title
    page.document_id = 1
    return page


class TestReprocessingCoreAPI:
    """Integration tests for reprocessing Core API methods"""

    @pytest.mark.asyncio
    async def test_reprocess_group_success(
        self,
        mock_db_manager,
        mock_chunking_service,
        mock_embedding_service,
        mock_config,
    ):
        """Test successful group reprocessing"""
        group_id = UUID("550e8400-e29b-41d4-a716-446655440000")

        service = ReprocessingService(
            db_manager=mock_db_manager,
            chunking_service=mock_chunking_service,
            embedding_service=mock_embedding_service,
            config=mock_config,
        )

        # Mock the repositories
        group = Group(
            id=group_id,
            document_id=1,
            name="Test Group",
            context_enabled=False,
            processing_status=ProcessingStatus.COMPLETED,
            total_pages=2,
            total_chunks=5,
            created_at=datetime.now(),
        )

        service.group_repo.get_group_by_id = AsyncMock(return_value=group)
        service.group_repo.update_group = AsyncMock(return_value=True)
        service.page_repo.get_pages_for_group = AsyncMock(
            return_value=[
                _make_mock_page(1, "Page 1 content", "Page 1"),
                _make_mock_page(2, "Page 2 content", "Page 2"),
            ]
        )
        service.chunk_repo.delete_by_group = AsyncMock(return_value=5)
        service.chunk_repo.create = AsyncMock(return_value=10)
        service.chunking_service.smart_chunk_markdown = MagicMock(
            return_value=["Chunk 1", "Chunk 2"]
        )
        service.embedding_service.get_embeddings_batch = AsyncMock(
            return_value=[[0.1] * 768, [0.2] * 768]
        )

        result = await service.reprocess_group(
            group_id=group_id,
            context_model="anthropic:claude-3-5-sonnet-20241022",
            force_delete_chunks=True,
        )

        assert result["status"] == "success"
        assert result["chunks_created"] >= 0
        service.group_repo.get_group_by_id.assert_called()
        service.group_repo.update_group.assert_called()

    @pytest.mark.asyncio
    async def test_reprocess_group_not_found(
        self,
        mock_db_manager,
        mock_chunking_service,
        mock_embedding_service,
        mock_config,
    ):
        """Test reprocessing with group not found"""
        group_id = UUID("550e8400-e29b-41d4-a716-446655440000")

        service = ReprocessingService(
            db_manager=mock_db_manager,
            chunking_service=mock_chunking_service,
            embedding_service=mock_embedding_service,
            config=mock_config,
        )

        service.group_repo.get_group_by_id = AsyncMock(return_value=None)

        with pytest.raises(RuntimeError, match="Group .* not found"):
            await service.reprocess_group(
                group_id=group_id,
                context_model="anthropic:claude-3-5-sonnet-20241022",
            )

    @pytest.mark.asyncio
    async def test_list_reprocessable_groups(
        self,
        mock_db_manager,
        mock_chunking_service,
        mock_embedding_service,
        mock_config,
    ):
        """Test listing reprocessable groups"""
        document_id = 1

        service = ReprocessingService(
            db_manager=mock_db_manager,
            chunking_service=mock_chunking_service,
            embedding_service=mock_embedding_service,
            config=mock_config,
        )

        groups = [
            Group(
                id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                document_id=document_id,
                name="Group 1",
                context_enabled=False,
                processing_status=ProcessingStatus.COMPLETED,
                total_pages=2,
                total_chunks=5,
                created_at=datetime.now(),
            ),
            Group(
                id=UUID("660e8400-e29b-41d4-a716-446655440001"),
                document_id=document_id,
                name="Group 2",
                context_enabled=False,
                processing_status=ProcessingStatus.COMPLETED,
                total_pages=3,
                total_chunks=8,
                created_at=datetime.now(),
            ),
        ]

        service.group_repo.list_groups = AsyncMock(return_value=groups)

        result = await service.list_reprocessable_groups(document_id=document_id)

        assert len(result) == 2
        assert result[0]["name"] == "Group 1"
        assert result[1]["name"] == "Group 2"
        service.group_repo.list_groups.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_reprocessing(
        self,
        mock_db_manager,
        mock_chunking_service,
        mock_embedding_service,
        mock_config,
    ):
        """Test batch reprocessing of multiple groups"""
        service = ReprocessingService(
            db_manager=mock_db_manager,
            chunking_service=mock_chunking_service,
            embedding_service=mock_embedding_service,
            config=mock_config,
        )

        group_ids = [
            UUID("550e8400-e29b-41d4-a716-446655440000"),
            UUID("660e8400-e29b-41d4-a716-446655440001"),
        ]

        groups = {
            group_ids[0]: Group(
                id=group_ids[0],
                document_id=1,
                name="Group 1",
                context_enabled=False,
                processing_status=ProcessingStatus.COMPLETED,
                total_pages=2,
                total_chunks=5,
                created_at=datetime.now(),
            ),
            group_ids[1]: Group(
                id=group_ids[1],
                document_id=1,
                name="Group 2",
                context_enabled=False,
                processing_status=ProcessingStatus.COMPLETED,
                total_pages=2,
                total_chunks=5,
                created_at=datetime.now(),
            ),
        }

        async def get_group_side_effect(gid):
            return groups.get(gid)

        service.group_repo.get_group_by_id = AsyncMock(side_effect=get_group_side_effect)
        service.group_repo.update_group = AsyncMock(return_value=True)
        service.page_repo.get_pages_for_group = AsyncMock(
            return_value=[_make_mock_page(1, "Page 1 content", "Page 1")]
        )
        service.chunk_repo.delete_by_group = AsyncMock(return_value=5)
        service.chunk_repo.create = AsyncMock(return_value=10)
        service.chunking_service.smart_chunk_markdown = MagicMock(
            return_value=["Chunk 1"]
        )
        service.embedding_service.get_embeddings_batch = AsyncMock(
            return_value=[[0.1] * 768]
        )

        results = await service.reprocess_multiple_groups(
            group_ids=group_ids,
            context_model="anthropic:claude-3-5-sonnet-20241022",
            continue_on_error=True,
        )

        assert results["total_groups"] == 2
        assert results["successful"] == 2
        assert len(results["group_results"]) == 2

    @pytest.mark.asyncio
    async def test_filters_context_enabled_groups(
        self,
        mock_db_manager,
        mock_chunking_service,
        mock_embedding_service,
        mock_config,
    ):
        """Test that list_reprocessable_groups filters out context-enabled groups"""
        document_id = 1

        service = ReprocessingService(
            db_manager=mock_db_manager,
            chunking_service=mock_chunking_service,
            embedding_service=mock_embedding_service,
            config=mock_config,
        )

        all_groups = [
            Group(
                id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                document_id=document_id,
                name="No Context",
                context_enabled=False,
                processing_status=ProcessingStatus.COMPLETED,
                total_pages=2,
                total_chunks=5,
                created_at=datetime.now(),
            ),
            Group(
                id=UUID("660e8400-e29b-41d4-a716-446655440001"),
                document_id=document_id,
                name="Has Context",
                context_enabled=True,
                processing_status=ProcessingStatus.COMPLETED,
                total_pages=3,
                total_chunks=8,
                created_at=datetime.now(),
            ),
        ]

        service.group_repo.list_groups = AsyncMock(return_value=all_groups)

        result = await service.list_reprocessable_groups(document_id=document_id)

        assert len(result) == 1
        assert result[0]["name"] == "No Context"
        assert result[0]["context_enabled"] is False
