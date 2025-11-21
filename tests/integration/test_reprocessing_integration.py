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
from context_bridge.services.reprocessing_service import ReprocessingService
from context_bridge.database.models.group_models import Group, ProcessingStatus


@pytest.fixture
def mock_db_manager():
    """Mock PostgreSQLManager"""
    manager = MagicMock()
    manager.connection.return_value.__aenter__ = AsyncMock()
    manager.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def mock_chunking_service():
    """Mock ChunkingService"""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService"""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 768
    return service


@pytest.fixture
def mock_context_agent():
    """Mock ContextGenerationAgent"""
    agent = AsyncMock()
    agent.generate_context.return_value = "Generated context"
    return agent


@pytest.fixture
def mock_config():
    """Mock Config"""
    config = MagicMock()
    config.anthropic_api_key = "test-key"
    config.openai_api_key = "test-key"
    config.embedding_dimension = 768
    return config


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

        # Create service with mocks
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
        service.page_repo.list_pages = AsyncMock(
            return_value=[
                {"id": 1, "content": "Page 1"},
                {"id": 2, "content": "Page 2"},
            ]
        )
        service.chunk_repo.delete_by_group = AsyncMock(return_value=5)
        service.chunk_repo.create_batch = AsyncMock(return_value=[10, 11])
        service.chunking_service.chunk_markdown = AsyncMock(
            return_value=[
                {"index": 0, "content": "Chunk 1"},
                {"index": 1, "content": "Chunk 2"},
            ]
        )
        service.embedding_service.embed = AsyncMock(return_value=[0.1] * 768)

        # Perform reprocessing
        result = await service.reprocess_group(
            group_id=group_id,
            context_model="anthropic:claude-3-5-sonnet-20241022",
            force_delete_chunks=True,
        )

        # Assertions
        assert result["success"] is True
        assert result["chunks_stored"] >= 0
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

        # Attempt reprocessing
        result = await service.reprocess_group(
            group_id=group_id,
            context_model="anthropic:claude-3-5-sonnet-20241022",
        )

        # Should fail
        assert result["success"] is False

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

        # Mock groups
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

        service.group_repo.list_groups_by_document = AsyncMock(return_value=groups)

        # List reprocessable groups
        result = await service.list_reprocessable_groups(document_id=document_id)

        # Assertions
        assert len(result) == 2
        assert result[0].name == "Group 1"
        assert result[1].name == "Group 2"
        service.group_repo.list_groups_by_document.assert_called_once()

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

        # Mock groups
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
        service.page_repo.list_pages = AsyncMock(
            return_value=[
                {"id": 1, "content": "Page 1"},
            ]
        )
        service.chunk_repo.delete_by_group = AsyncMock(return_value=5)
        service.chunk_repo.create_batch = AsyncMock(return_value=[10])
        service.chunking_service.chunk_markdown = AsyncMock(
            return_value=[
                {"index": 0, "content": "Chunk 1"},
            ]
        )
        service.embedding_service.embed = AsyncMock(return_value=[0.1] * 768)

        # Perform batch reprocessing
        results = await service.reprocess_multiple_groups(
            group_ids=group_ids,
            context_model="anthropic:claude-3-5-sonnet-20241022",
            continue_on_error=True,
        )

        # Assertions
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is True

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

        # Mix of context-enabled and non-context-enabled groups
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

        service.group_repo.list_groups_by_document = AsyncMock(return_value=all_groups)

        # List reprocessable groups
        result = await service.list_reprocessable_groups(document_id=document_id)

        # Only non-context-enabled groups should be returned
        assert len(result) == 1
        assert result[0].name == "No Context"
        assert result[0].context_enabled is False
