"""
Integration tests for context generation with DocManager.

Tests cover:
- Context generation workflow integration with DocManager
- Batch processing with context generation
- Error handling during context generation
- Chunk updates with prepended context
- End-to-end processing with context enabled/disabled
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from uuid import uuid4, UUID
from datetime import datetime

from pydantic import BaseModel

from context_bridge.config import Config
from context_bridge.service.doc_manager import DocManager
from context_bridge.database.models.group_models import Group, ProcessingStatus


@pytest.fixture
def mock_config():
    """Fixture providing a test configuration."""
    return Config(
        context_agent_model="anthropic:claude-3-5-sonnet-20241022",
        context_agent_temperature=0.3,
        context_agent_max_tokens=500,
        context_batch_size=10,
        anthropic_api_key="test-key",
    )


@pytest.fixture
def mock_db_manager():
    """Fixture providing a mocked PostgreSQL manager."""
    return MagicMock()


@pytest.fixture
def mock_crawling_service():
    """Fixture providing a mocked crawling service."""
    return AsyncMock()


@pytest.fixture
def mock_chunking_service():
    """Fixture providing a mocked chunking service."""
    return MagicMock()


@pytest.fixture
def mock_embedding_service():
    """Fixture providing a mocked embedding service."""
    return AsyncMock()


@pytest.fixture
def mock_repositories(mock_db_manager):
    """Fixture providing mocked repositories."""
    repos = {
        "page_repo": AsyncMock(),
        "chunk_repo": AsyncMock(),
        "doc_repo": AsyncMock(),
    }
    return repos


@pytest.fixture
def doc_manager(
    mock_db_manager,
    mock_crawling_service,
    mock_chunking_service,
    mock_embedding_service,
    mock_config,
):
    """Fixture providing a DocManager instance with mocked dependencies."""
    manager = DocManager(
        db_manager=mock_db_manager,
        crawling_service=mock_crawling_service,
        chunking_service=mock_chunking_service,
        embedding_service=mock_embedding_service,
        config=mock_config,
    )

    # Replace repositories with mocks
    manager.page_repo = AsyncMock()
    manager.chunk_repo = AsyncMock()
    manager.doc_repo = AsyncMock()

    return manager


class TestProcessGroupWithContext:
    """Tests for process_group method with context generation."""

    @pytest.mark.asyncio
    async def test_process_group_without_context(self, doc_manager):
        """Test process_group works normally without context generation."""
        group_id = uuid4()

        # Mock pages
        mock_page1 = MagicMock()
        mock_page1.id = 1
        mock_page1.document_id = 1
        mock_page1.content = "# Page 1\n\nContent here"

        doc_manager.page_repo.get_pages_for_group.return_value = [mock_page1]
        doc_manager.chunking_service.smart_chunk_markdown.return_value = ["Chunk 1", "Chunk 2"]
        doc_manager.embedding_service.get_embeddings_batch.return_value = [
            [0.1, 0.2],
            [0.3, 0.4],
        ]
        doc_manager.chunk_repo.create_batch.return_value = [1, 2]

        result = await doc_manager.process_group(group_id, context_enabled=False)

        assert result["status"] == "success"
        assert result["total_pages"] == 1
        assert result["pages_processed"] == 1
        assert result["chunks_created"] == 2
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_process_group_with_context_generation(self, doc_manager):
        """Test process_group with context generation enabled."""
        group_id = uuid4()

        # Mock pages
        mock_page1 = MagicMock()
        mock_page1.id = 1
        mock_page1.document_id = 1
        mock_page1.content = "# API Documentation\n\nAuthentication section"

        doc_manager.page_repo.get_pages_for_group.return_value = [mock_page1]
        doc_manager.chunking_service.smart_chunk_markdown.return_value = [
            "Chunk 1 about auth",
            "Chunk 2 about tokens",
        ]
        doc_manager.embedding_service.get_embeddings_batch.return_value = [
            [0.1, 0.2],
            [0.3, 0.4],
        ]
        doc_manager.chunk_repo.create_batch.return_value = [1, 2]
        doc_manager.chunk_repo.prepend_context_to_chunk.return_value = True

        with patch("context_bridge.service.doc_manager.ContextGenerationAgent") as mock_agent_class:
            mock_agent = AsyncMock()
            mock_agent.generate_contexts_batch.return_value = [
                "Context for chunk 1",
                "Context for chunk 2",
            ]
            mock_agent_class.return_value = mock_agent

            result = await doc_manager.process_group(
                group_id,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
            )

            assert result["status"] == "success"
            assert result["chunks_created"] == 2

            # Verify context agent was created
            mock_agent_class.assert_called_once_with(doc_manager.config)

            # Verify context generation was called
            mock_agent.generate_contexts_batch.assert_called_once()
            call_args = mock_agent.generate_contexts_batch.call_args
            assert "Chunk 1 about auth" in call_args[0][0]

            # Verify contexts were prepended
            assert doc_manager.chunk_repo.prepend_context_to_chunk.call_count == 2

    @pytest.mark.asyncio
    async def test_process_group_context_generation_partial_failure(self, doc_manager):
        """Test process_group continues even with partial context generation failures."""
        group_id = uuid4()

        mock_page = MagicMock()
        mock_page.id = 1
        mock_page.document_id = 1
        mock_page.content = "Test content"

        doc_manager.page_repo.get_pages_for_group.return_value = [mock_page]
        doc_manager.chunking_service.smart_chunk_markdown.return_value = [
            "Chunk 1",
            "Chunk 2",
            "Chunk 3",
        ]
        doc_manager.embedding_service.get_embeddings_batch.return_value = [
            [0.1, 0.2],
            [0.3, 0.4],
            [0.5, 0.6],
        ]
        doc_manager.chunk_repo.create_batch.return_value = [1, 2, 3]

        with patch("context_bridge.service.doc_manager.ContextGenerationAgent") as mock_agent_class:
            mock_agent = AsyncMock()
            # Some contexts succeed, one fails (empty)
            mock_agent.generate_contexts_batch.return_value = [
                "Context 1",
                "",  # Failed
                "Context 3",
            ]
            mock_agent_class.return_value = mock_agent

            # Track which chunks get updated
            update_calls = []

            async def track_updates(chunk_idx, context):
                if context:  # Only update non-empty contexts
                    update_calls.append((chunk_idx, context))
                return True

            doc_manager.chunk_repo.prepend_context_to_chunk.side_effect = track_updates

            result = await doc_manager.process_group(
                group_id,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
            )

            assert result["status"] == "success"
            # Only 2 contexts were updated (skipped empty one)
            assert len(update_calls) == 2

    @pytest.mark.asyncio
    async def test_process_group_multiple_pages_with_context(self, doc_manager):
        """Test process_group combines content from multiple pages for context."""
        group_id = uuid4()

        # Mock multiple pages
        mock_page1 = MagicMock()
        mock_page1.id = 1
        mock_page1.document_id = 1
        mock_page1.content = "# Section 1\n\nFirst section content"

        mock_page2 = MagicMock()
        mock_page2.id = 2
        mock_page2.document_id = 1
        mock_page2.content = "# Section 2\n\nSecond section content"

        doc_manager.page_repo.get_pages_for_group.return_value = [mock_page1, mock_page2]
        doc_manager.chunking_service.smart_chunk_markdown.return_value = ["Chunk"]
        doc_manager.embedding_service.get_embeddings_batch.return_value = [[0.1]]
        doc_manager.chunk_repo.create_batch.return_value = [1]
        doc_manager.chunk_repo.prepend_context_to_chunk.return_value = True

        with patch("context_bridge.service.doc_manager.ContextGenerationAgent") as mock_agent_class:
            mock_agent = AsyncMock()
            mock_agent.generate_contexts_batch.return_value = ["Context"]
            mock_agent_class.return_value = mock_agent

            result = await doc_manager.process_group(
                group_id,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
            )

            # Verify context generation was called with combined content
            mock_agent.generate_contexts_batch.assert_called_once()
            combined_content = mock_agent.generate_contexts_batch.call_args[0][1]

            # Combined content should include both pages
            assert "Section 1" in combined_content
            assert "Section 2" in combined_content

    @pytest.mark.asyncio
    async def test_process_group_empty_pages(self, doc_manager):
        """Test process_group handles empty page list gracefully."""
        group_id = uuid4()

        doc_manager.page_repo.get_pages_for_group.return_value = []

        result = await doc_manager.process_group(group_id, context_enabled=True)

        assert result["status"] == "success"
        assert result["total_pages"] == 0
        assert result["chunks_created"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_process_group_context_generation_error_handling(self, doc_manager):
        """Test process_group continues processing on context generation error."""
        group_id = uuid4()

        mock_page = MagicMock()
        mock_page.id = 1
        mock_page.document_id = 1
        mock_page.content = "Content"

        doc_manager.page_repo.get_pages_for_group.return_value = [mock_page]
        doc_manager.chunking_service.smart_chunk_markdown.return_value = ["Chunk"]
        doc_manager.embedding_service.get_embeddings_batch.return_value = [[0.1]]
        doc_manager.chunk_repo.create_batch.return_value = [1]

        with patch("context_bridge.service.doc_manager.ContextGenerationAgent") as mock_agent_class:
            mock_agent = AsyncMock()
            # Simulate LLM error
            mock_agent.generate_contexts_batch.side_effect = Exception("LLM API Error")
            mock_agent_class.return_value = mock_agent

            # Should not raise exception, just log and continue
            result = await doc_manager.process_group(
                group_id,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
            )

            assert result["status"] == "success"
            assert result["chunks_created"] == 1


class TestChunkRepositoryContextUpdate:
    """Tests for chunk repository context update methods."""

    @pytest.mark.asyncio
    async def test_prepend_context_to_chunk_success(self):
        """Test successfully prepending context to chunk content."""
        from context_bridge.database.repositories.chunk_repository import ChunkRepository
        from contextlib import asynccontextmanager

        # Create proper async context manager mock
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [{"id": 1}]
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_db_manager = MagicMock()

        @asynccontextmanager
        async def mock_connection():
            yield mock_conn

        mock_db_manager.connection = mock_connection

        repo = ChunkRepository(mock_db_manager)
        result = await repo.prepend_context_to_chunk(0, "Generated context")

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_prepend_context_empty_context(self):
        """Test that empty context is handled gracefully."""
        mock_db_manager = AsyncMock()

        from context_bridge.database.repositories.chunk_repository import ChunkRepository

        repo = ChunkRepository(mock_db_manager)

        result = await repo.prepend_context_to_chunk(0, "")

        assert result is False
        # Database should not be called for empty context

    @pytest.mark.asyncio
    async def test_prepend_context_not_found(self):
        """Test handling when chunk is not found."""
        from context_bridge.database.repositories.chunk_repository import ChunkRepository
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = []  # No rows
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_db_manager = MagicMock()

        @asynccontextmanager
        async def mock_connection():
            yield mock_conn

        mock_db_manager.connection = mock_connection

        repo = ChunkRepository(mock_db_manager)
        result = await repo.prepend_context_to_chunk(999, "Context")

        assert result is False


class TestContextGenerationIntegration:
    """Integration tests combining DocManager and context generation."""

    @pytest.mark.asyncio
    async def test_full_workflow_crawl_to_context(self, doc_manager):
        """Test full workflow from page creation to context generation."""
        group_id = uuid4()

        mock_page = MagicMock()
        mock_page.id = 1
        mock_page.document_id = 1
        mock_page.content = "# Complete Documentation\n\n## Introduction\n\nAPI documentation"

        doc_manager.page_repo.get_pages_for_group.return_value = [mock_page]
        doc_manager.chunking_service.smart_chunk_markdown.return_value = [
            "Introduction section",
            "API Reference section",
        ]
        doc_manager.embedding_service.get_embeddings_batch.return_value = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]
        doc_manager.chunk_repo.create_batch.return_value = [1, 2]
        doc_manager.chunk_repo.prepend_context_to_chunk.return_value = True

        with patch("context_bridge.service.doc_manager.ContextGenerationAgent") as mock_agent_class:
            mock_agent = AsyncMock()
            mock_agent.generate_contexts_batch.return_value = [
                "This section introduces the API",
                "This section provides API endpoints",
            ]
            mock_agent_class.return_value = mock_agent

            result = await doc_manager.process_group(
                group_id,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
            )

            # Verify full workflow
            assert result["status"] == "success"
            assert result["chunks_created"] == 2
            assert doc_manager.chunk_repo.create_batch.called
            assert mock_agent.generate_contexts_batch.called
            assert doc_manager.chunk_repo.prepend_context_to_chunk.called
