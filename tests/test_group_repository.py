"""
Tests for GroupRepository.

This module contains unit tests for the GroupRepository class,
testing all CRUD operations with mocked PSQLPy connections following
PSQLPy best practices (dict returns, proper parameter binding).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from context_bridge.database.repositories.group_repository import (
    GroupRepository,
    PageGroup,
    GroupWithPages,
)
from context_bridge.database.postgres_manager import PostgreSQLManager


@pytest.fixture
def sample_page_group():
    """
    Create a sample PageGroup instance for testing.

    Returns:
        PageGroup with test data
    """
    return PageGroup(
        id=1,
        document_id=100,
        name="Test Group",
        total_size=1500,
        page_count=3,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        status="eligible",
    )


@pytest.fixture
def sample_group_with_pages(sample_page_group):
    """
    Create a sample GroupWithPages instance for testing.

    Returns:
        GroupWithPages with test data
    """
    return GroupWithPages(
        group=sample_page_group,
        page_ids=[1, 2, 3],
    )


class TestGroupRepositoryUnit:
    """
    Unit tests for GroupRepository functionality.

    These tests mock all database connections and verify that
    the repository correctly handles PSQLPy result objects
    (dicts, not tuples) and parameter binding ($1, $2, etc.).
    """

    @pytest.fixture
    def mock_db_manager(self):
        """
        Create a mock PostgreSQLManager for testing.

        Returns:
            Mock PostgreSQLManager with connection context manager
        """
        manager = MagicMock(spec=PostgreSQLManager)

        # Mock the connection context manager
        connection_mock = AsyncMock()
        manager.connection.return_value.__aenter__ = AsyncMock(return_value=connection_mock)
        manager.connection.return_value.__aexit__ = AsyncMock(return_value=None)

        return manager

    @pytest.fixture
    def repo(self, mock_db_manager):
        """
        Create a GroupRepository instance with mocked dependencies.

        Returns:
            GroupRepository with mocked database manager
        """
        return GroupRepository(mock_db_manager)

    @pytest.mark.asyncio
    async def test_create_group_success(self, repo, mock_db_manager, sample_page_group):
        """Test successful group creation."""
        # Mock validation query results
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
            {"id": 2, "document_id": 100, "status": "pending", "content_length": 600},
            {"id": 3, "document_id": 100, "status": "pending", "content_length": 400},
        ]

        # Mock group creation result
        group_creation_result = MagicMock()
        group_creation_result.result.return_value = [{"id": 1}]

        # Setup mocks
        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock
        mock_conn.execute.return_value = group_creation_result

        # Mock execute_transaction for member insertions
        mock_db_manager.execute_transaction.return_value = None

        # Execute
        result = await repo.create_group(document_id=100, page_ids=[1, 2, 3], name="Test Group")

        # Verify
        assert result == 1
        assert mock_conn.fetch.call_count == 1
        assert mock_conn.execute.call_count == 1  # group creation
        assert mock_db_manager.execute_transaction.call_count == 1  # member insertions

    @pytest.mark.asyncio
    async def test_create_group_empty_pages(self, repo):
        """Test group creation with empty page list."""
        with pytest.raises(ValueError, match="Cannot create group with empty page list"):
            await repo.create_group(document_id=100, page_ids=[])

    @pytest.mark.asyncio
    async def test_create_group_missing_pages(self, repo, mock_db_manager):
        """Test group creation with missing pages."""
        # Mock validation query returns fewer results
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock

        with pytest.raises(ValueError, match="Pages not found"):
            await repo.create_group(document_id=100, page_ids=[1, 2])

    @pytest.mark.asyncio
    async def test_create_group_wrong_document(self, repo, mock_db_manager):
        """Test group creation with pages from different document."""
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
            {"id": 2, "document_id": 200, "status": "pending", "content_length": 600},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock

        with pytest.raises(ValueError, match="belongs to different document"):
            await repo.create_group(document_id=100, page_ids=[1, 2])

    @pytest.mark.asyncio
    async def test_create_group_wrong_status(self, repo, mock_db_manager):
        """Test group creation with pages having wrong status."""
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
            {"id": 2, "document_id": 100, "status": "grouped", "content_length": 600},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock

        with pytest.raises(ValueError, match="has status 'grouped'"):
            await repo.create_group(document_id=100, page_ids=[1, 2])

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repo, mock_db_manager, sample_page_group):
        """Test successful group retrieval by ID."""
        query_mock = MagicMock()
        query_mock.result.return_value = [
            {
                "id": 1,
                "document_id": 100,
                "name": "Test Group",
                "total_size": 1500,
                "page_count": 3,
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "status": "eligible",
            }
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = query_mock

        result = await repo.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.document_id == 100
        assert result.name == "Test Group"
        assert result.total_size == 1500
        assert result.page_count == 3
        assert result.status == "eligible"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo, mock_db_manager):
        """Test group retrieval when group doesn't exist."""
        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        query_mock = MagicMock()
        query_mock.result.return_value = []
        mock_conn.fetch.return_value = query_mock

        result = await repo.get_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_pages_success(self, repo, mock_db_manager, sample_group_with_pages):
        """Test successful group with pages retrieval."""
        # Mock get_by_id
        group_mock = MagicMock()
        group_mock.result.return_value = [
            {
                "id": 1,
                "document_id": 100,
                "name": "Test Group",
                "total_size": 1500,
                "page_count": 3,
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "status": "eligible",
            }
        ]

        # Mock page IDs query
        pages_mock = MagicMock()
        pages_mock.result.return_value = [{"page_id": 1}, {"page_id": 2}, {"page_id": 3}]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.side_effect = [group_mock, pages_mock]

        result = await repo.get_with_pages(1)

        assert result is not None
        assert result.group.id == 1

    @pytest.mark.asyncio
    async def test_get_with_pages_not_found(self, repo, mock_db_manager):
        """Test group with pages retrieval when group doesn't exist."""
        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        group_mock = MagicMock()
        group_mock.result.return_value = []
        mock_conn.fetch.return_value = group_mock

        result = await repo.get_with_pages(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_document_success(self, repo, mock_db_manager, sample_page_group):
        """Test successful listing of groups by document."""
        query_mock = MagicMock()
        query_mock.result.return_value = [
            {
                "id": 1,
                "document_id": 100,
                "name": "Test Group",
                "total_size": 1500,
                "page_count": 3,
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "status": "eligible",
            }
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = query_mock

        result = await repo.list_by_document(document_id=100, status="eligible", offset=0, limit=10)

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].document_id == 100

    @pytest.mark.asyncio
    async def test_list_by_document_no_status_filter(
        self, repo, mock_db_manager, sample_page_group
    ):
        """Test listing groups without status filter."""
        query_mock = MagicMock()
        query_mock.result.return_value = [
            {
                "id": 1,
                "document_id": 100,
                "name": "Test Group",
                "total_size": 1500,
                "page_count": 3,
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "status": "eligible",
            }
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = query_mock

        result = await repo.list_by_document(document_id=100, offset=0, limit=10)

        assert len(result) == 1
        assert result[0].status == "eligible"

    @pytest.mark.asyncio
    async def test_get_eligible_groups_success(self, repo, mock_db_manager, sample_page_group):
        """Test successful retrieval of eligible groups."""
        query_mock = MagicMock()
        query_mock.result.return_value = [
            {
                "id": 1,
                "document_id": 100,
                "name": "Test Group",
                "total_size": 1500,
                "page_count": 3,
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "status": "eligible",
            }
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = query_mock

        result = await repo.get_eligible_groups(document_id=100, min_size=1000, max_size=2000)

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].status == "eligible"

    @pytest.mark.asyncio
    async def test_get_group_content_success(self, repo, mock_db_manager):
        """Test successful group content retrieval."""
        content_mock = MagicMock()
        content_mock.result.return_value = [
            {"content": "Content 1"},
            {"content": "Content 2"},
            {"content": "Content 3"},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = content_mock

        result = await repo.get_group_content(1)

        expected = "Content 1\n\n---\n\nContent 2\n\n---\n\nContent 3"
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_group_content_no_pages(self, repo, mock_db_manager):
        """Test group content retrieval when no pages found."""
        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        content_mock = MagicMock()
        content_mock.result.return_value = []
        mock_conn.fetch.return_value = content_mock

        with pytest.raises(ValueError, match="No pages found for group"):
            await repo.get_group_content(1)

    @pytest.mark.asyncio
    async def test_update_status_success(self, repo, mock_db_manager):
        """Test successful status update."""
        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.execute.return_value = MagicMock()  # UPDATE returns empty

        result = await repo.update_status(1, "processed")

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_ungroup_success(self, repo, mock_db_manager):
        """Test successful group dissolution."""
        # Mock page query
        pages_mock = MagicMock()
        pages_mock.result.return_value = [{"page_id": 1}, {"page_id": 2}, {"page_id": 3}]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = pages_mock
        mock_conn.execute.return_value = MagicMock()

        result = await repo.ungroup(1)

        assert result is True
        # Should have executed transaction with 2 operations (update pages + delete group)

    @pytest.mark.asyncio
    async def test_ungroup_not_found(self, repo, mock_db_manager):
        """Test ungroup when group has no members."""
        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        pages_mock = MagicMock()
        pages_mock.result.return_value = []  # No pages
        mock_conn.fetch.return_value = pages_mock

        with pytest.raises(ValueError, match="not found or has no members"):
            await repo.ungroup(1)

    @pytest.mark.asyncio
    async def test_delete_success(self, repo, mock_db_manager):
        """Test successful group deletion."""
        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.execute.return_value = MagicMock()  # DELETE returns empty

        result = await repo.delete(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_group_constraints_success(self, repo, mock_db_manager):
        """Test successful constraint validation."""
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
            {"id": 2, "document_id": 100, "status": "pending", "content_length": 600},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock

        is_valid, error, total_size = await repo.validate_group_constraints(
            [1, 2], min_size=500, max_size=2000
        )

        assert is_valid is True
        assert error is None
        assert total_size == 1100

    @pytest.mark.asyncio
    async def test_validate_group_constraints_empty_pages(self, repo):
        """Test constraint validation with empty page list."""
        is_valid, error, total_size = await repo.validate_group_constraints([])

        assert is_valid is False
        assert "empty page list" in error
        assert total_size == 0

    @pytest.mark.asyncio
    async def test_validate_group_constraints_missing_pages(self, repo, mock_db_manager):
        """Test constraint validation with missing pages."""
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock

        is_valid, error, total_size = await repo.validate_group_constraints([1, 2])

        assert is_valid is False
        assert "Pages not found" in error
        assert total_size == 0

    @pytest.mark.asyncio
    async def test_validate_group_constraints_different_documents(self, repo, mock_db_manager):
        """Test constraint validation with pages from different documents."""
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
            {"id": 2, "document_id": 200, "status": "pending", "content_length": 600},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock

        is_valid, error, total_size = await repo.validate_group_constraints([1, 2])

        assert is_valid is False
        assert "different documents" in error
        assert total_size == 0

    @pytest.mark.asyncio
    async def test_validate_group_constraints_wrong_status(self, repo, mock_db_manager):
        """Test constraint validation with pages having wrong status."""
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
            {"id": 2, "document_id": 100, "status": "grouped", "content_length": 600},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock

        is_valid, error, total_size = await repo.validate_group_constraints([1, 2])

        assert is_valid is False
        assert "invalid status" in error
        assert total_size == 0

    @pytest.mark.asyncio
    async def test_validate_group_constraints_size_constraints(self, repo, mock_db_manager):
        """Test constraint validation with size limits."""
        validation_mock = MagicMock()
        validation_mock.result.return_value = [
            {"id": 1, "document_id": 100, "status": "pending", "content_length": 500},
            {"id": 2, "document_id": 100, "status": "pending", "content_length": 600},
        ]

        mock_conn = mock_db_manager.connection.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = validation_mock

        # Test min_size violation
        is_valid, error, total_size = await repo.validate_group_constraints([1, 2], min_size=2000)
        assert is_valid is False
        assert "below minimum" in error
        assert total_size == 1100

        # Test max_size violation
        is_valid, error, total_size = await repo.validate_group_constraints([1, 2], max_size=500)
        assert is_valid is False
        assert "exceeds maximum" in error
        assert total_size == 1100
