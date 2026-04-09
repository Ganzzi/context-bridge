"""
Unit tests for ContextBridge tag management methods.

Tests cover all 5 new public tag methods:
- add_tag_to_document()
- add_tags_to_document()
- remove_tag_from_document()
- remove_all_tags_from_document()
- create_tag()
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from context_bridge.core import ContextBridge
from context_bridge.config import Config
from context_bridge.database.models.tag_models import Tag, TagCategory, TagCreate


# Fixtures


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock(spec=Config)
    config.postgres_host = "localhost"
    config.postgres_password = "test"
    config.embedding_model = "test-model"
    config.context_agent_model = None
    config.google_api_key = None
    return config


@pytest.fixture
def mock_tag_repository():
    """Create a mock tag repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
async def bridge_with_mocks(mock_config, mock_tag_repository):
    """Create ContextBridge instance with mocked dependencies."""
    bridge = ContextBridge(config=mock_config)

    # Mock the database manager and other services
    bridge._db_manager = AsyncMock()
    bridge._db_manager.__aenter__ = AsyncMock(return_value=bridge._db_manager)
    bridge._db_manager.__aexit__ = AsyncMock(return_value=None)

    bridge._doc_manager = AsyncMock()
    bridge._search_service = AsyncMock()
    bridge._tag_repository = mock_tag_repository
    bridge._group_repository = AsyncMock()
    bridge._initialized = True

    return bridge


@pytest.fixture
def sample_tag():
    """Create a sample Tag object."""
    return Tag(
        id=1,
        name="database",
        category=TagCategory.TECHNOLOGY,
        description="Database-related content",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_tags():
    """Create sample Tag objects."""
    return [
        Tag(
            id=1,
            name="database",
            category=TagCategory.TECHNOLOGY,
            description="Database-related",
            created_at=datetime.now(timezone.utc),
        ),
        Tag(
            id=2,
            name="async",
            category=TagCategory.TECHNOLOGY,
            description="Async programming",
            created_at=datetime.now(timezone.utc),
        ),
        Tag(
            id=3,
            name="Python",
            category=TagCategory.TECHNOLOGY,
            description="Python language",
            created_at=datetime.now(timezone.utc),
        ),
    ]


# Tests for add_tag_to_document


@pytest.mark.asyncio
async def test_add_tag_to_document_success(bridge_with_mocks):
    """Test successfully adding a tag to a document."""
    bridge_with_mocks._tag_repository.add_tag_to_document = AsyncMock(return_value=True)

    result = await bridge_with_mocks.add_tag_to_document(
        document_id=42,
        tag_id=5,
    )

    assert result is True
    bridge_with_mocks._tag_repository.add_tag_to_document.assert_called_once_with(42, 5)


@pytest.mark.asyncio
async def test_add_tag_to_document_already_exists(bridge_with_mocks):
    """Test adding a tag that's already assigned (idempotent)."""
    bridge_with_mocks._tag_repository.add_tag_to_document = AsyncMock(return_value=False)

    result = await bridge_with_mocks.add_tag_to_document(
        document_id=42,
        tag_id=5,
    )

    assert result is False
    bridge_with_mocks._tag_repository.add_tag_to_document.assert_called_once_with(42, 5)


@pytest.mark.asyncio
async def test_add_tag_to_document_not_initialized(mock_config, mock_tag_repository):
    """Test that add_tag_to_document checks initialization."""
    bridge = ContextBridge(config=mock_config)
    bridge._initialized = False

    with pytest.raises(RuntimeError, match="not initialized"):
        await bridge.add_tag_to_document(42, 5)


# Tests for add_tags_to_document


@pytest.mark.asyncio
async def test_add_tags_to_document_multiple(bridge_with_mocks):
    """Test adding multiple tags to a document."""
    bridge_with_mocks._tag_repository.add_tags_to_document = AsyncMock(return_value=3)

    result = await bridge_with_mocks.add_tags_to_document(
        document_id=42,
        tag_ids=[1, 5, 12],
    )

    assert result == 3
    bridge_with_mocks._tag_repository.add_tags_to_document.assert_called_once_with(42, [1, 5, 12])


@pytest.mark.asyncio
async def test_add_tags_to_document_partial_success(bridge_with_mocks):
    """Test adding tags when some already exist."""
    bridge_with_mocks._tag_repository.add_tags_to_document = AsyncMock(return_value=2)

    result = await bridge_with_mocks.add_tags_to_document(
        document_id=42,
        tag_ids=[1, 5, 12],  # Maybe 1 already exists
    )

    assert result == 2


@pytest.mark.asyncio
async def test_add_tags_to_document_empty_list(bridge_with_mocks):
    """Test adding empty list of tags."""
    bridge_with_mocks._tag_repository.add_tags_to_document = AsyncMock(return_value=0)

    result = await bridge_with_mocks.add_tags_to_document(
        document_id=42,
        tag_ids=[],
    )

    assert result == 0
    bridge_with_mocks._tag_repository.add_tags_to_document.assert_called_once_with(42, [])


@pytest.mark.asyncio
async def test_add_tags_to_document_not_initialized(mock_config):
    """Test that add_tags_to_document checks initialization."""
    bridge = ContextBridge(config=mock_config)
    bridge._initialized = False

    with pytest.raises(RuntimeError, match="not initialized"):
        await bridge.add_tags_to_document(42, [1, 2, 3])


# Tests for remove_tag_from_document


@pytest.mark.asyncio
async def test_remove_tag_from_document_success(bridge_with_mocks):
    """Test successfully removing a tag from a document."""
    bridge_with_mocks._tag_repository.remove_tag_from_document = AsyncMock(return_value=True)

    result = await bridge_with_mocks.remove_tag_from_document(
        document_id=42,
        tag_id=5,
    )

    assert result is True
    bridge_with_mocks._tag_repository.remove_tag_from_document.assert_called_once_with(42, 5)


@pytest.mark.asyncio
async def test_remove_tag_from_document_not_assigned(bridge_with_mocks):
    """Test removing a tag that isn't assigned."""
    bridge_with_mocks._tag_repository.remove_tag_from_document = AsyncMock(return_value=False)

    result = await bridge_with_mocks.remove_tag_from_document(
        document_id=42,
        tag_id=5,
    )

    assert result is False


@pytest.mark.asyncio
async def test_remove_tag_from_document_not_initialized(mock_config):
    """Test that remove_tag_from_document checks initialization."""
    bridge = ContextBridge(config=mock_config)
    bridge._initialized = False

    with pytest.raises(RuntimeError, match="not initialized"):
        await bridge.remove_tag_from_document(42, 5)


# Tests for remove_all_tags_from_document


@pytest.mark.asyncio
async def test_remove_all_tags_from_document_success(bridge_with_mocks):
    """Test successfully removing all tags from a document."""
    bridge_with_mocks._tag_repository.remove_all_tags_from_document = AsyncMock(return_value=5)

    result = await bridge_with_mocks.remove_all_tags_from_document(document_id=42)

    assert result == 5
    bridge_with_mocks._tag_repository.remove_all_tags_from_document.assert_called_once_with(42)


@pytest.mark.asyncio
async def test_remove_all_tags_from_document_no_tags(bridge_with_mocks):
    """Test removing all tags when document has no tags."""
    bridge_with_mocks._tag_repository.remove_all_tags_from_document = AsyncMock(return_value=0)

    result = await bridge_with_mocks.remove_all_tags_from_document(document_id=42)

    assert result == 0


@pytest.mark.asyncio
async def test_remove_all_tags_from_document_not_initialized(mock_config):
    """Test that remove_all_tags_from_document checks initialization."""
    bridge = ContextBridge(config=mock_config)
    bridge._initialized = False

    with pytest.raises(RuntimeError, match="not initialized"):
        await bridge.remove_all_tags_from_document(42)


# Tests for create_tag


@pytest.mark.asyncio
async def test_create_tag_success(bridge_with_mocks, sample_tag):
    """Test successfully creating a new tag."""
    bridge_with_mocks._tag_repository.create_tag = AsyncMock(return_value=sample_tag)

    result = await bridge_with_mocks.create_tag(
        name="database",
        category=TagCategory.TECHNOLOGY,
        description="Database-related content",
    )

    assert result.id == 1
    assert result.name == "database"
    assert result.category == TagCategory.TECHNOLOGY
    assert result.description == "Database-related content"

    # Verify create_tag was called with TagCreate object
    bridge_with_mocks._tag_repository.create_tag.assert_called_once()
    call_args = bridge_with_mocks._tag_repository.create_tag.call_args[0][0]
    assert isinstance(call_args, TagCreate)
    assert call_args.name == "database"
    assert call_args.category == TagCategory.TECHNOLOGY


@pytest.mark.asyncio
async def test_create_tag_without_description(bridge_with_mocks):
    """Test creating a tag without description."""
    new_tag = Tag(
        id=10,
        name="custom-tag",
        category=TagCategory.CUSTOM,
        description=None,
        created_at=datetime.now(timezone.utc),
    )
    bridge_with_mocks._tag_repository.create_tag = AsyncMock(return_value=new_tag)

    result = await bridge_with_mocks.create_tag(
        name="custom-tag",
        category=TagCategory.CUSTOM,
    )

    assert result.name == "custom-tag"
    assert result.description is None


@pytest.mark.asyncio
async def test_create_tag_duplicate_name(bridge_with_mocks):
    """Test creating a tag with a duplicate name."""
    bridge_with_mocks._tag_repository.create_tag = AsyncMock(
        side_effect=ValueError("Tag name already exists")
    )

    with pytest.raises(ValueError, match="already exists"):
        await bridge_with_mocks.create_tag(
            name="existing",
            category=TagCategory.TECHNOLOGY,
        )


@pytest.mark.asyncio
async def test_create_tag_not_initialized(mock_config):
    """Test that create_tag checks initialization."""
    bridge = ContextBridge(config=mock_config)
    bridge._initialized = False

    with pytest.raises(RuntimeError, match="not initialized"):
        await bridge.create_tag(
            name="test",
            category=TagCategory.TECHNOLOGY,
        )


# Integration tests (mocked dependencies)


@pytest.mark.asyncio
async def test_complete_tag_workflow(bridge_with_mocks, sample_tags):
    """Test a complete tag workflow: add, verify, and remove."""
    doc_id = 42

    # Setup mocks
    bridge_with_mocks._tag_repository.add_tags_to_document = AsyncMock(return_value=3)
    bridge_with_mocks._tag_repository.get_document_tags = AsyncMock(return_value=sample_tags)
    bridge_with_mocks._tag_repository.remove_all_tags_from_document = AsyncMock(return_value=3)

    # Step 1: Add tags
    added = await bridge_with_mocks.add_tags_to_document(doc_id, [1, 2, 3])
    assert added == 3

    # Step 2: Verify tags
    tags = await bridge_with_mocks.get_document_tags(doc_id)
    assert len(tags) == 3
    assert tags[0].name == "database"

    # Step 3: Remove all tags
    removed = await bridge_with_mocks.remove_all_tags_from_document(doc_id)
    assert removed == 3


@pytest.mark.asyncio
async def test_tag_creation_and_assignment(bridge_with_mocks, sample_tag):
    """Test creating a tag and then assigning it to a document."""
    # Setup mocks
    bridge_with_mocks._tag_repository.create_tag = AsyncMock(return_value=sample_tag)
    bridge_with_mocks._tag_repository.add_tag_to_document = AsyncMock(return_value=True)

    # Step 1: Create custom tag
    new_tag = await bridge_with_mocks.create_tag(
        name="database",
        category=TagCategory.TECHNOLOGY,
        description="Database-related content",
    )
    assert new_tag.id == 1

    # Step 2: Assign to document
    assigned = await bridge_with_mocks.add_tag_to_document(42, new_tag.id)
    assert assigned is True


# Error handling tests


@pytest.mark.asyncio
async def test_add_tag_repository_error(bridge_with_mocks):
    """Test handling of repository errors."""
    bridge_with_mocks._tag_repository.add_tag_to_document = AsyncMock(
        side_effect=Exception("Database error")
    )

    with pytest.raises(Exception, match="Database error"):
        await bridge_with_mocks.add_tag_to_document(42, 5)


@pytest.mark.asyncio
async def test_remove_tag_repository_error(bridge_with_mocks):
    """Test handling of repository errors during removal."""
    bridge_with_mocks._tag_repository.remove_tag_from_document = AsyncMock(
        side_effect=Exception("Database error")
    )

    with pytest.raises(Exception, match="Database error"):
        await bridge_with_mocks.remove_tag_from_document(42, 5)
