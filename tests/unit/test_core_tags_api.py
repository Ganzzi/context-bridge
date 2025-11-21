"""
Unit tests for ContextBridge tag API methods.

Tests the integration of tag operations in the main ContextBridge class,
including adding/removing tags, filtering documents by tags, and retrieving tags.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from context_bridge.core import ContextBridge
from context_bridge.config import Config
from context_bridge.database.models.tag_models import Tag, TagCategory


@pytest.fixture
def config():
    """Provide a test configuration."""
    return Config(
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="test_user",
        postgres_password="test_pass",
        postgres_db="test_db",
    )


@pytest.fixture
def mock_bridge(config):
    """Provide a mocked ContextBridge instance."""
    bridge = ContextBridge(config=config)

    # Mock the internal components
    bridge._db_manager = AsyncMock()
    bridge._tag_repository = AsyncMock()
    bridge._search_service = AsyncMock()
    bridge._doc_manager = AsyncMock()
    bridge._initialized = True

    # Setup async context manager for connection
    mock_conn = AsyncMock()
    bridge._db_manager.connection = MagicMock()
    bridge._db_manager.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    bridge._db_manager.connection.return_value.__aexit__ = AsyncMock(return_value=None)

    return bridge


@pytest.mark.asyncio
async def test_list_tags_all(mock_bridge):
    """Test listing all tags without category filter."""
    # Mock tags
    now = datetime.now(timezone.utc)
    mock_tags = [
        Tag(
            id=1,
            name="API Reference",
            category=TagCategory.DOCUMENTATION_TYPE,
            description="API docs",
            created_at=now,
        ),
        Tag(
            id=2,
            name="Python",
            category=TagCategory.TECHNOLOGY,
            description="Python related",
            created_at=now,
        ),
    ]
    mock_bridge._tag_repository.list_tags.return_value = mock_tags

    # Execute
    result = await mock_bridge.list_tags()

    # Verify
    assert result == mock_tags
    mock_bridge._tag_repository.list_tags.assert_called_once_with(category=None)


@pytest.mark.asyncio
async def test_list_tags_by_category(mock_bridge):
    """Test listing tags filtered by category."""
    # Mock tags
    now = datetime.now(timezone.utc)
    mock_tags = [
        Tag(
            id=1,
            name="API Reference",
            category=TagCategory.DOCUMENTATION_TYPE,
            description="API docs",
            created_at=now,
        ),
        Tag(
            id=3,
            name="Tutorial",
            category=TagCategory.DOCUMENTATION_TYPE,
            description="Tutorial docs",
            created_at=now,
        ),
    ]
    mock_bridge._tag_repository.list_tags.return_value = mock_tags

    # Execute
    result = await mock_bridge.list_tags(category=TagCategory.DOCUMENTATION_TYPE)

    # Verify
    assert result == mock_tags
    mock_bridge._tag_repository.list_tags.assert_called_once_with(
        category=TagCategory.DOCUMENTATION_TYPE
    )


@pytest.mark.asyncio
async def test_add_tags_to_document(mock_bridge):
    """Test adding tags to a document."""
    mock_bridge._tag_repository.add_tags_to_document.return_value = 3

    # Execute
    result = await mock_bridge.add_tags_to_document(document_id=1, tag_ids=[2, 5, 10])

    # Verify
    assert result == 3
    mock_bridge._tag_repository.add_tags_to_document.assert_called_once_with(1, [2, 5, 10])


@pytest.mark.asyncio
async def test_remove_tag_from_document(mock_bridge):
    """Test removing a tag from a document."""
    mock_bridge._tag_repository.remove_tag_from_document.return_value = True

    # Execute
    result = await mock_bridge.remove_tag_from_document(document_id=1, tag_id=2)

    # Verify
    assert result is True
    mock_bridge._tag_repository.remove_tag_from_document.assert_called_once_with(1, 2)


@pytest.mark.asyncio
async def test_get_document_tags(mock_bridge):
    """Test retrieving tags for a document."""
    now = datetime.now(timezone.utc)
    mock_tags = [
        Tag(
            id=2,
            name="Python",
            category=TagCategory.TECHNOLOGY,
            description="Python related",
            created_at=now,
        ),
        Tag(
            id=5,
            name="Backend",
            category=TagCategory.DOMAIN,
            description="Backend development",
            created_at=now,
        ),
    ]
    mock_bridge._tag_repository.get_document_tags.return_value = mock_tags

    # Execute
    result = await mock_bridge.get_document_tags(document_id=1)

    # Verify
    assert result == mock_tags
    mock_bridge._tag_repository.get_document_tags.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_remove_all_tags_from_document(mock_bridge):
    """Test removing all tags from a document."""
    mock_bridge._tag_repository.remove_all_tags_from_document.return_value = 5

    # Execute
    result = await mock_bridge.remove_all_tags_from_document(document_id=1)

    # Verify
    assert result == 5
    mock_bridge._tag_repository.remove_all_tags_from_document.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_core_api_not_initialized_raises_error(mock_bridge):
    """Test that calling tag methods without initialization raises error."""
    mock_bridge._initialized = False

    # Execute and verify
    with pytest.raises(RuntimeError, match="ContextBridge not initialized"):
        await mock_bridge.list_tags()

    with pytest.raises(RuntimeError, match="ContextBridge not initialized"):
        await mock_bridge.add_tags_to_document(1, [2])

    with pytest.raises(RuntimeError, match="ContextBridge not initialized"):
        await mock_bridge.get_document_tags(1)
