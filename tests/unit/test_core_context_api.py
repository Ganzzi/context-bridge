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



