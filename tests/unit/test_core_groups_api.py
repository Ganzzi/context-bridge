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


# Test get_group_info()


@pytest.mark.asyncio
async def test_get_group_info_success(mock_bridge):
    """Test retrieving detailed group information."""
    # Setup
    group_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_group = Group(
        id=group_id,
        document_id=1,
        name="API Documentation",
        description="Complete API docs",
        context_enabled=True,
        context_model="anthropic:claude-3-5-sonnet-20241022",
        combined_content_length=125000,
        total_pages=10,
        total_chunks=75,
        created_at=now,
        processed_at=now,
        processing_status=ProcessingStatus.COMPLETED,
        metadata={"tags": ["api", "reference"]},
    )

    mock_statistics = {
        "total_chunks": 75,
        "total_content_length": 125000,
        "avg_chunk_size": 1666.67,
    }

    mock_bridge._group_repository.get_group_by_id.return_value = mock_group
    mock_bridge._group_repository.get_group_statistics.return_value = mock_statistics

    # Execute
    result = await mock_bridge.get_group_info(str(group_id))

    # Verify
    assert result["id"] == str(group_id)
    assert result["name"] == "API Documentation"
    assert result["context_enabled"] is True
    assert result["total_chunks"] == 75
    assert result["statistics"]["total_chunks"] == 75
    mock_bridge._group_repository.get_group_by_id.assert_called_once_with(group_id)
    mock_bridge._group_repository.get_group_statistics.assert_called_once_with(group_id)


@pytest.mark.asyncio
async def test_get_group_info_not_found(mock_bridge):
    """Test getting group info when group doesn't exist."""
    # Setup
    group_id = uuid4()
    mock_bridge._group_repository.get_group_by_id.return_value = None

    # Execute and verify
    with pytest.raises(ValueError, match="Group not found"):
        await mock_bridge.get_group_info(str(group_id))


@pytest.mark.asyncio
async def test_get_group_info_invalid_uuid(mock_bridge):
    """Test getting group info with invalid UUID format."""
    # Setup
    invalid_id = "not-a-valid-uuid"

    # Execute and verify
    with pytest.raises(ValueError, match="Invalid group ID format"):
        await mock_bridge.get_group_info(invalid_id)


@pytest.mark.asyncio
async def test_get_group_info_with_no_processed_at(mock_bridge):
    """Test group info when processing hasn't completed."""
    # Setup
    group_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_group = Group(
        id=group_id,
        document_id=1,
        name="Pending Group",
        description="Still processing",
        context_enabled=False,
        context_model=None,
        combined_content_length=None,
        total_pages=5,
        total_chunks=0,
        created_at=now,
        processed_at=None,
        processing_status=ProcessingStatus.PROCESSING,
        metadata={},
    )

    mock_statistics = {"total_chunks": 0, "total_content_length": 0, "avg_chunk_size": 0}

    mock_bridge._group_repository.get_group_by_id.return_value = mock_group
    mock_bridge._group_repository.get_group_statistics.return_value = mock_statistics

    # Execute
    result = await mock_bridge.get_group_info(str(group_id))

    # Verify
    assert result["processing_status"] == "processing"
    assert result["processed_at"] is None
    assert result["total_chunks"] == 0


@pytest.mark.asyncio
async def test_get_group_info_context_enabled(mock_bridge):
    """Test group info for a context-enabled group."""
    # Setup
    group_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_group = Group(
        id=group_id,
        document_id=1,
        name="Context-Enabled Group",
        description="Group with AI context",
        context_enabled=True,
        context_model="anthropic:claude-3-5-sonnet-20241022",
        combined_content_length=200000,
        total_pages=15,
        total_chunks=150,
        created_at=now,
        processed_at=now,
        processing_status=ProcessingStatus.COMPLETED,
        metadata={"context_version": "v1"},
    )

    mock_statistics = {
        "total_chunks": 150,
        "total_content_length": 200000,
        "avg_chunk_size": 1333.33,
    }

    mock_bridge._group_repository.get_group_by_id.return_value = mock_group
    mock_bridge._group_repository.get_group_statistics.return_value = mock_statistics

    # Execute
    result = await mock_bridge.get_group_info(str(group_id))

    # Verify
    assert result["context_enabled"] is True
    assert result["context_model"] == "anthropic:claude-3-5-sonnet-20241022"
    assert result["statistics"]["total_chunks"] == 150
    assert result["statistics"]["avg_chunk_size"] == 1333.33


@pytest.mark.asyncio
async def test_list_groups_not_initialized(config):
    """Test that list_groups raises error when not initialized."""
    bridge = ContextBridge(config=config)

    with pytest.raises(RuntimeError, match="not initialized"):
        await bridge.list_groups()


@pytest.mark.asyncio
async def test_get_group_info_not_initialized(config):
    """Test that get_group_info raises error when not initialized."""
    bridge = ContextBridge(config=config)
    group_id = uuid4()

    with pytest.raises(RuntimeError, match="not initialized"):
        await bridge.get_group_info(str(group_id))


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
