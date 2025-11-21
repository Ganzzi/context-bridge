"""
Tests for PageRepository.

This module contains unit tests for the PageRepository class,
testing all CRUD operations with mocked PSQLPy connections following
PSQLPy best practices (dict returns, proper parameter binding).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from context_bridge.database.repositories.page_repository import PageRepository, Page
from context_bridge.database.postgres_manager import PostgreSQLManager


@pytest.fixture
def sample_page():
    """
    Create a sample Page instance for testing.

    Returns:
        Page with test data
    """
    return Page(
        id=1,
        document_id=100,
        url="https://example.com/page1",
        content="# Test Page\n\nThis is test content.",
        content_hash="abc123def456",
        content_length=42,
        crawled_at=datetime(2024, 1, 1, 12, 0, 0),
        status="pending",
        metadata={"source": "test"},
    )


class TestPageRepositoryUnit:
    """
    Unit tests for PageRepository functionality.

    These tests mock all database connections and verify that
    the repository correctly handles PSQLPy result objects
    (dicts, not tuples) and parameter binding ($1, $2, etc.).
    """

    @pytest.fixture
    def mock_db_manager(self):
        """
        Create a mock PostgreSQLManager for testing.

        Returns:
            AsyncMock of PostgreSQLManager
        """
        return AsyncMock(spec=PostgreSQLManager)

    @pytest.fixture
    def repo(self, mock_db_manager):
        """
        Create a PageRepository instance with mocked manager.

        Args:
            mock_db_manager: Mocked PostgreSQLManager

        Returns:
            PageRepository instance for testing
        """
        return PageRepository(mock_db_manager)

    @pytest.mark.asyncio
    async def test_create_success_new_page(self, repo, mock_db_manager):
        """
        Test successful page creation when page doesn't exist.
        """
        # Mock the connection context manager
        mock_conn = AsyncMock()
        mock_result = MagicMock()

        # Mock get_by_url to return None (page doesn't exist)
        with patch.object(repo, "get_by_url", return_value=None):
            # PSQLPy returns dicts with column names as keys
            mock_result.result.return_value = [{"id": 123}]
            mock_conn.execute.return_value = mock_result

            mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
            mock_db_manager.connection.return_value.__aexit__.return_value = None

            result = await repo.create(
                document_id=100,
                url="https://example.com/page1",
                content="# Test Page\n\nContent",
                content_hash="abc123",
                metadata={"source": "test"},
            )

            assert result == 123
            # Verify execute was called with INSERT
            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args
            assert "INSERT INTO pages" in call_args[0][0]
            assert call_args[0][1] == [
                100,
                "https://example.com/page1",
                "# Test Page\n\nContent",
                "abc123",
                {"source": "test"},
            ]

    @pytest.mark.asyncio
    async def test_create_success_existing_page(self, repo, mock_db_manager, sample_page):
        """
        Test page creation when URL already exists - should return existing ID.
        """
        # Mock get_by_url to return existing page
        with patch.object(repo, "get_by_url", return_value=sample_page):
            result = await repo.create(
                document_id=100,
                url="https://example.com/page1",
                content="# Test Page\n\nContent",
                content_hash="abc123",
                metadata={"source": "test"},
            )

            assert result == sample_page.id
            # Verify no INSERT was executed
            mock_db_manager.connection.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repo, mock_db_manager, sample_page):
        """
        Test successful page retrieval by ID.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        # PSQLPy returns dicts with column names as keys
        mock_result.result.return_value = [
            {
                "id": sample_page.id,
                "document_id": sample_page.document_id,
                "url": sample_page.url,
                "content": sample_page.content,
                "content_hash": sample_page.content_hash,
                "content_length": sample_page.content_length,
                "crawled_at": sample_page.crawled_at,
                "status": sample_page.status,
                "metadata": sample_page.metadata,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.get_by_id(1)

        assert result is not None
        assert result.id == sample_page.id
        assert result.url == sample_page.url
        assert result.status == sample_page.status

        # Verify execute was called with correct query
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "SELECT" in call_args[0][0] and "WHERE id = $1" in call_args[0][0]
        assert call_args[0][1] == [1]

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo, mock_db_manager):
        """
        Test page retrieval by ID when page doesn't exist.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = []  # No results
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.get_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_url_success(self, repo, mock_db_manager, sample_page):
        """
        Test successful page retrieval by URL.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": sample_page.id,
                "document_id": sample_page.document_id,
                "url": sample_page.url,
                "content": sample_page.content,
                "content_hash": sample_page.content_hash,
                "content_length": sample_page.content_length,
                "crawled_at": sample_page.crawled_at,
                "status": sample_page.status,
                "metadata": sample_page.metadata,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.get_by_url("https://example.com/page1")

        assert result is not None
        assert result.id == sample_page.id
        assert result.url == sample_page.url

        # Verify execute was called with correct query
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "SELECT" in call_args[0][0] and "WHERE url = $1" in call_args[0][0]
        assert call_args[0][1] == ["https://example.com/page1"]

    @pytest.mark.asyncio
    async def test_list_by_document_no_status_filter(self, repo, mock_db_manager, sample_page):
        """
        Test listing pages by document ID without status filter.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": sample_page.id,
                "document_id": sample_page.document_id,
                "url": sample_page.url,
                "content": sample_page.content,
                "content_hash": sample_page.content_hash,
                "content_length": sample_page.content_length,
                "crawled_at": sample_page.crawled_at,
                "status": sample_page.status,
                "metadata": sample_page.metadata,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.list_by_document(document_id=100, offset=0, limit=10)

        assert len(result) == 1
        assert result[0].id == sample_page.id
        assert result[0].document_id == 100

        # Verify execute was called with correct query (no status filter)
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "WHERE document_id = $1" in call_args[0][0]
        assert "ORDER BY group_id IS NULL DESC, group_id, crawled_at DESC" in call_args[0][0]
        assert call_args[0][1] == [100, 10, 0]

    @pytest.mark.asyncio
    async def test_list_by_document_with_status_filter(self, repo, mock_db_manager, sample_page):
        """
        Test listing pages by document ID with status filter.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": sample_page.id,
                "document_id": sample_page.document_id,
                "url": sample_page.url,
                "content": sample_page.content,
                "content_hash": sample_page.content_hash,
                "content_length": sample_page.content_length,
                "crawled_at": sample_page.crawled_at,
                "status": sample_page.status,
                "metadata": sample_page.metadata,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.list_by_document(document_id=100, status="pending", offset=0, limit=10)

        assert len(result) == 1
        assert result[0].status == "pending"

        # Verify execute was called with correct query (with status filter)
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "WHERE document_id = $1 AND status = $2" in call_args[0][0]
        assert call_args[0][1] == [100, "pending", 10, 0]

    @pytest.mark.asyncio
    async def test_count_by_document_no_status_filter(self, repo, mock_db_manager):
        """
        Test counting pages by document ID without status filter.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [{"count": 5}]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.count_by_document(document_id=100)

        assert result == 5

        # Verify execute was called with correct query
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "COUNT(*)" in call_args[0][0]
        assert "WHERE document_id = $1" in call_args[0][0]
        assert call_args[0][1] == [100]

    @pytest.mark.asyncio
    async def test_count_by_document_with_status_filter(self, repo, mock_db_manager):
        """
        Test counting pages by document ID with status filter.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [{"count": 3}]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.count_by_document(document_id=100, status="pending")

        assert result == 3

        # Verify execute was called with correct query
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "WHERE document_id = $1 AND status = $2" in call_args[0][0]
        assert call_args[0][1] == [100, "pending"]

    @pytest.mark.asyncio
    async def test_update_status_success(self, repo, mock_db_manager):
        """
        Test successful status update.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        # PSQLPy returns string representation like "UPDATE 1"
        mock_result.result.return_value = "UPDATE 1"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.update_status(page_id=1, status="chunked")

        assert result is True

        # Verify execute was called with correct parameters
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "UPDATE pages SET status = $1 WHERE id = $2" in call_args[0][0]
        assert call_args[0][1] == ["chunked", 1]

    @pytest.mark.asyncio
    async def test_update_status_no_rows_affected(self, repo, mock_db_manager):
        """
        Test status update when no rows are affected.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = "UPDATE 0"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.update_status(page_id=999, status="chunked")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_status_invalid_status(self, repo, mock_db_manager):
        """
        Test status update with invalid status value.
        """
        with pytest.raises(ValueError, match="Invalid status 'invalid'"):
            await repo.update_status(page_id=1, status="invalid")

    @pytest.mark.asyncio
    async def test_update_status_bulk_success(self, repo, mock_db_manager):
        """
        Test successful bulk status update.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = "UPDATE 3"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.update_status_bulk(page_ids=[1, 2, 3], status="chunked")

        assert result == 3

        # Verify execute was called with correct parameters
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "UPDATE pages SET status = $1 WHERE id IN" in call_args[0][0]
        assert call_args[0][1] == ["chunked", 1, 2, 3]

    @pytest.mark.asyncio
    async def test_update_status_bulk_empty_list(self, repo, mock_db_manager):
        """
        Test bulk status update with empty page ID list.
        """
        result = await repo.update_status_bulk(page_ids=[], status="chunked")

        assert result == 0
        # Verify no database calls were made
        mock_db_manager.connection.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_success(self, repo, mock_db_manager):
        """
        Test successful page deletion (soft delete).
        """
        # Mock update_status to return True
        with patch.object(repo, "update_status", return_value=True) as mock_update:
            result = await repo.delete(page_id=1)

            assert result is True
            mock_update.assert_called_once_with(1, "deleted")

    @pytest.mark.asyncio
    async def test_delete_bulk_success(self, repo, mock_db_manager):
        """
        Test successful bulk page deletion (soft delete).
        """
        # Mock update_status_bulk to return 3
        with patch.object(repo, "update_status_bulk", return_value=3) as mock_update:
            result = await repo.delete_bulk(page_ids=[1, 2, 3])

            assert result == 3
            mock_update.assert_called_once_with([1, 2, 3], "deleted")

    @pytest.mark.asyncio
    async def test_check_duplicates_success(self, repo, mock_db_manager):
        """
        Test successful duplicate content hash checking.
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [{"content_hash": "hash1"}, {"content_hash": "hash3"}]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.check_duplicates(content_hashes=["hash1", "hash2", "hash3"])

        assert result == {"hash1", "hash3"}

        # Verify execute was called with correct query
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "SELECT DISTINCT content_hash FROM pages WHERE content_hash IN" in call_args[0][0]
        assert call_args[0][1] == ["hash1", "hash2", "hash3"]

    @pytest.mark.asyncio
    async def test_check_duplicates_empty_list(self, repo, mock_db_manager):
        """
        Test duplicate checking with empty hash list.
        """
        result = await repo.check_duplicates(content_hashes=[])

        assert result == set()
        # Verify no database calls were made
        mock_db_manager.connection.assert_not_called()

    @pytest.mark.asyncio
    async def test_row_to_page_conversion(self, repo):
        """
        Test conversion from database row dict to Page model.
        """
        row = {
            "id": 1,
            "document_id": 100,
            "url": "https://example.com/page1",
            "content": "# Test Page\n\nContent",
            "content_hash": "abc123",
            "content_length": 25,
            "crawled_at": datetime(2024, 1, 1, 12, 0, 0),
            "status": "pending",
            "metadata": {"source": "test"},
        }

        page = repo._row_to_page(row)

        assert isinstance(page, Page)
        assert page.id == 1
        assert page.document_id == 100
        assert page.url == "https://example.com/page1"
        assert page.content == "# Test Page\n\nContent"
        assert page.content_hash == "abc123"
        assert page.content_length == 25
        assert page.status == "pending"
        assert page.metadata == {"source": "test"}

    @pytest.mark.asyncio
    async def test_row_to_page_conversion_null_metadata(self, repo):
        """
        Test conversion when metadata is NULL.
        """
        row = {
            "id": 1,
            "document_id": 100,
            "url": "https://example.com/page1",
            "content": "Content",
            "content_hash": "abc123",
            "content_length": 7,
            "crawled_at": datetime(2024, 1, 1, 12, 0, 0),
            "status": "pending",
            "metadata": None,
        }

        page = repo._row_to_page(row)

        assert page.metadata == {}


class TestPageRepositoryGroupMethods:
    """
    Unit tests for group-aware methods added in Phase 2.5.3.
    """

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock PostgreSQLManager for testing."""
        manager = AsyncMock(spec=PostgreSQLManager)
        return manager

    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create a PageRepository with mocked database manager."""
        return PageRepository(mock_db_manager)

    @pytest.fixture
    def sample_group_id(self):
        """Generate a sample group UUID."""
        from uuid import UUID

        return UUID("550e8400-e29b-41d4-a716-446655440000")

    @pytest.fixture
    def sample_pages_with_group(self, sample_group_id):
        """Create sample page rows with group_id for testing."""
        return [
            {
                "id": 1,
                "document_id": 100,
                "url": "https://example.com/page1",
                "content": "Content 1",
                "content_hash": "hash1",
                "content_length": 9,
                "crawled_at": datetime(2024, 1, 1, 12, 0, 0),
                "status": "chunked",
                "group_id": sample_group_id,
                "metadata": {},
            },
            {
                "id": 2,
                "document_id": 100,
                "url": "https://example.com/page2",
                "content": "Content 2",
                "content_hash": "hash2",
                "content_length": 9,
                "crawled_at": datetime(2024, 1, 1, 12, 0, 1),
                "status": "chunked",
                "group_id": sample_group_id,
                "metadata": {},
            },
            {
                "id": 3,
                "document_id": 100,
                "url": "https://example.com/page3",
                "content": "Content 3",
                "content_hash": "hash3",
                "content_length": 9,
                "crawled_at": datetime(2024, 1, 1, 12, 0, 2),
                "status": "pending",
                "group_id": sample_group_id,
                "metadata": {},
            },
        ]

    @pytest.mark.asyncio
    async def test_get_pages_for_group_success(
        self, repo, mock_db_manager, sample_group_id, sample_pages_with_group
    ):
        """
        Test successful retrieval of pages for a group.
        """
        # Mock the connection and execute
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = sample_pages_with_group
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        # Call the method
        pages = await repo.get_pages_for_group(sample_group_id)

        # Assertions
        assert len(pages) == 3
        assert all(page.group_id == sample_group_id for page in pages)
        assert pages[0].url == "https://example.com/page1"
        assert pages[1].url == "https://example.com/page2"
        assert pages[2].url == "https://example.com/page3"

        # Verify the query was called correctly
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "WHERE group_id = $1" in call_args[0][0]
        assert str(sample_group_id) in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_pages_for_group_empty(self, repo, mock_db_manager, sample_group_id):
        """
        Test retrieval when no pages exist for group.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        pages = await repo.get_pages_for_group(sample_group_id)

        assert pages == []
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pages_for_group_db_error(self, repo, mock_db_manager, sample_group_id):
        """
        Test error handling when database query fails.
        """
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB Error"))
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        with pytest.raises(Exception) as exc_info:
            await repo.get_pages_for_group(sample_group_id)

        assert "DB Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_page_group_success(self, repo, mock_db_manager, sample_group_id):
        """
        Test successful update of page group assignment.
        """
        page_id = 1
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        # Simulate one row affected
        mock_result.result.return_value = [{"id": page_id}]
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        result = await repo.update_page_group(page_id, sample_group_id)

        assert result is True
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "UPDATE pages SET group_id = $1 WHERE id = $2" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_page_group_not_found(self, repo, mock_db_manager, sample_group_id):
        """
        Test update when page doesn't exist (no rows affected).
        """
        page_id = 999
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = []  # No rows affected
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        result = await repo.update_page_group(page_id, sample_group_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_page_from_group_success(self, repo, mock_db_manager):
        """
        Test successful removal of page from group.
        """
        page_id = 1
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = [{"id": page_id}]
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        result = await repo.remove_page_from_group(page_id)

        assert result is True
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "UPDATE pages SET group_id = NULL WHERE id = $1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_remove_page_from_group_not_found(self, repo, mock_db_manager):
        """
        Test removal when page doesn't exist.
        """
        page_id = 999
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        result = await repo.remove_page_from_group(page_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_pages_by_group_and_status_chunked(
        self, repo, mock_db_manager, sample_group_id, sample_pages_with_group
    ):
        """
        Test filtering pages by group and chunked status.
        """
        chunked_pages = [sample_pages_with_group[0], sample_pages_with_group[1]]
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = chunked_pages
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        pages = await repo.get_pages_by_group_and_status(sample_group_id, chunked=True)

        assert len(pages) == 2
        assert all(page.status == "chunked" for page in pages)
        call_args = mock_conn.execute.call_args
        assert "status = $2" in call_args[0][0]
        assert "chunked" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_pages_by_group_and_status_pending(
        self, repo, mock_db_manager, sample_group_id, sample_pages_with_group
    ):
        """
        Test filtering pages by group and pending status.
        """
        pending_pages = [sample_pages_with_group[2]]
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = pending_pages
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        pages = await repo.get_pages_by_group_and_status(sample_group_id, chunked=False)

        assert len(pages) == 1
        assert pages[0].status == "pending"
        call_args = mock_conn.execute.call_args
        assert "pending" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_pages_by_group_and_status_no_filter(
        self, repo, mock_db_manager, sample_group_id, sample_pages_with_group
    ):
        """
        Test retrieving all pages in group without status filter.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = sample_pages_with_group
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        pages = await repo.get_pages_by_group_and_status(sample_group_id, chunked=None)

        assert len(pages) == 3
        call_args = mock_conn.execute.call_args
        # Should not have status filter
        assert "status = $2" not in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_pages_by_group_and_status_empty(
        self, repo, mock_db_manager, sample_group_id
    ):
        """
        Test when no pages match the filters.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        pages = await repo.get_pages_by_group_and_status(sample_group_id, chunked=True)

        assert pages == []
