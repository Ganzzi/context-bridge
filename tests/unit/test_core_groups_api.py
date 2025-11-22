"""
Unit tests for ContextBridge group API methods.

Tests the integration of group operations in the main ContextBridge class,
including listing groups, getting group information, and group metadata.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

from context_bridge.core import ContextBridge
from context_bridge.config import Config
from context_bridge.database.models.group_models import Group, ProcessingStatus, GroupStatistics


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
    bridge._group_repository = AsyncMock()
    bridge._search_service = AsyncMock()
    bridge._doc_manager = AsyncMock()
    bridge._tag_repository = AsyncMock()
    bridge._initialized = True

    # Setup async context manager for connection
    mock_conn = AsyncMock()
    bridge._db_manager.connection = MagicMock()
    bridge._db_manager.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    bridge._db_manager.connection.return_value.__aexit__ = AsyncMock(return_value=None)

    return bridge


# Test list_groups()


@pytest.mark.asyncio
async def test_list_groups_for_document(mock_bridge):
    """Test listing groups for a specific document."""
    # Setup
    document_id = 1
    group_id_1 = uuid4()
    group_id_2 = uuid4()
    now = datetime.now(timezone.utc)

    mock_groups = [
        Group(
            id=group_id_1,
            document_id=document_id,
            name="API Docs",
            description="API documentation group",
            context_enabled=False,
            context_model=None,
            combined_content_length=50000,
            total_pages=5,
            total_chunks=25,
            created_at=now,
            processed_at=now,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        ),
        Group(
            id=group_id_2,
            document_id=document_id,
            name="Examples",
            description="Example documentation group",
            context_enabled=True,
            context_model="anthropic:claude-3-5-sonnet-20241022",
            combined_content_length=75000,
            total_pages=8,
            total_chunks=40,
            created_at=now,
            processed_at=now,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        ),
    ]

    mock_bridge._group_repository.list_groups.return_value = mock_groups

    # Execute
    result = await mock_bridge.list_groups(document_id=document_id, limit=100, offset=0)

    # Verify
    assert len(result) == 2
    assert result[0]["id"] == str(group_id_1)
    assert result[0]["name"] == "API Docs"
    assert result[0]["total_pages"] == 5
    assert result[0]["total_chunks"] == 25
    assert result[1]["id"] == str(group_id_2)
    assert result[1]["context_enabled"] is True
    mock_bridge._group_repository.list_groups.assert_called_once_with(
        document_id=document_id, limit=100, offset=0
    )


@pytest.mark.asyncio
async def test_list_groups_all_documents(mock_bridge):
    """Test listing all groups across all documents."""
    # Setup
    group_id_1 = uuid4()
    group_id_2 = uuid4()
    now = datetime.now(timezone.utc)

    mock_groups = [
        Group(
            id=group_id_1,
            document_id=1,
            name="Group1",
            description="First group",
            context_enabled=False,
            context_model=None,
            combined_content_length=50000,
            total_pages=5,
            total_chunks=25,
            created_at=now,
            processed_at=now,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        ),
        Group(
            id=group_id_2,
            document_id=2,
            name="Group2",
            description="Second group",
            context_enabled=False,
            context_model=None,
            combined_content_length=75000,
            total_pages=8,
            total_chunks=40,
            created_at=now,
            processed_at=None,
            processing_status=ProcessingStatus.PENDING,
            metadata={},
        ),
    ]

    mock_bridge._group_repository.list_groups.return_value = mock_groups

    # Execute
    result = await mock_bridge.list_groups(document_id=None, limit=50, offset=0)

    # Verify
    assert len(result) == 2
    assert result[0]["document_id"] == 1
    assert result[1]["document_id"] == 2
    assert result[1]["processing_status"] == "pending"
    mock_bridge._group_repository.list_groups.assert_called_once_with(
        document_id=None, limit=50, offset=0
    )


@pytest.mark.asyncio
async def test_list_groups_empty(mock_bridge):
    """Test listing groups when none exist."""
    # Setup
    mock_bridge._group_repository.list_groups.return_value = []

    # Execute
    result = await mock_bridge.list_groups(document_id=1)

    # Verify
    assert result == []
    mock_bridge._group_repository.list_groups.assert_called_once()


@pytest.mark.asyncio
async def test_list_groups_pagination(mock_bridge):
    """Test group listing with pagination."""
    # Setup
    group_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_groups = [
        Group(
            id=group_id,
            document_id=1,
            name="Group1",
            description="First group",
            context_enabled=False,
            context_model=None,
            combined_content_length=50000,
            total_pages=5,
            total_chunks=25,
            created_at=now,
            processed_at=now,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={},
        ),
    ]

    mock_bridge._group_repository.list_groups.return_value = mock_groups

    # Execute
    result = await mock_bridge.list_groups(document_id=1, limit=10, offset=5)

    # Verify
    assert len(result) == 1
    mock_bridge._group_repository.list_groups.assert_called_once_with(
        document_id=1, limit=10, offset=5
    )


@pytest.mark.asyncio
async def test_list_groups_not_initialized(config):
    """Test that list_groups raises error when not initialized."""
    bridge = ContextBridge(config=config)

    with pytest.raises(RuntimeError, match="not initialized"):
        await bridge.list_groups()


# Test default parameters and return format


@pytest.mark.asyncio
async def test_list_groups_default_parameters(mock_bridge):
    """Test list_groups uses correct default parameters."""
    # Setup
    group_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_group = Group(
        id=group_id,
        document_id=1,
        name="Test Group",
        description="Test",
        context_enabled=False,
        context_model=None,
        combined_content_length=50000,
        total_pages=5,
        total_chunks=25,
        created_at=now,
        processed_at=now,
        processing_status=ProcessingStatus.COMPLETED,
        metadata={},
    )

    mock_bridge._group_repository.list_groups.return_value = [mock_group]

    # Execute without optional parameters
    result = await mock_bridge.list_groups()

    # Verify default parameters
    mock_bridge._group_repository.list_groups.assert_called_once_with(
        document_id=None, limit=100, offset=0
    )


@pytest.mark.asyncio
async def test_list_groups_return_format(mock_bridge):
    """Test that list_groups returns properly formatted dictionaries."""
    # Setup
    group_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_group = Group(
        id=group_id,
        document_id=1,
        name="Test Group",
        description="Test description",
        context_enabled=True,
        context_model="anthropic:claude-3-5-sonnet-20241022",
        combined_content_length=50000,
        total_pages=5,
        total_chunks=25,
        created_at=now,
        processed_at=now,
        processing_status=ProcessingStatus.COMPLETED,
        metadata={},
    )

    mock_bridge._group_repository.list_groups.return_value = [mock_group]

    # Execute
    result = await mock_bridge.list_groups()

    # Verify returned dictionary has all expected keys
    assert len(result) == 1
    group_dict = result[0]
    expected_keys = {
        "id",
        "document_id",
        "name",
        "description",
        "context_enabled",
        "context_model",
        "total_pages",
        "total_chunks",
        "processing_status",
        "created_at",
        "processed_at",
    }
    assert set(group_dict.keys()) == expected_keys
    assert isinstance(group_dict["id"], str)
    assert isinstance(group_dict["created_at"], str)
