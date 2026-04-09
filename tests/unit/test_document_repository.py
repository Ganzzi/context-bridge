"""
Tests for DocumentRepository.

This module contains unit tests for the DocumentRepository class,
testing all CRUD operations with mocked PSQLPy connections following
PSQLPy best practices (dict returns, proper parameter binding).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from context_bridge.database.postgres_manager import PostgreSQLManager


@pytest.fixture
def sample_document():
    """
    Create a sample Document instance for testing.

    Returns:
        Document with test data
    """
    return Document(
        id=1,
        name="Test Doc",
        version="1.0.0",
        source_url="https://example.com",
        description="A test document",
        metadata={"key": "value"},
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
    )


class TestDocumentRepositoryUnit:
    """
    Unit tests for DocumentRepository functionality.

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
        Create a DocumentRepository instance with mocked manager.

        Args:
            mock_db_manager: Mocked PostgreSQLManager

        Returns:
            DocumentRepository instance for testing
        """
        return DocumentRepository(mock_db_manager)

    @pytest.mark.asyncio
    async def test_create_success(self, repo, mock_db_manager):
        """
        Test successful document creation.

        Verifies that:
        - Document is created with all parameters
        - ID is extracted from PSQLPy result tuple [0][0]
        - Correct SQL parameters are passed
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        # PSQLPy returns dicts with column names as keys
        mock_result.result.return_value = [{"id": 123}]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.create(
            name="Test Doc",
            version="1.0.0",
            source_url="https://example.com",
            description="A test document",
            metadata={"key": "value"},
        )

        assert result == 123
        # Verify execute was called with correct parameters
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO documents" in call_args[0][0]
        assert call_args[0][1] == [
            "Test Doc",
            "1.0.0",
            "https://example.com",
            "A test document",
            {"key": "value"},
        ]

    @pytest.mark.asyncio
    async def test_create_failure_no_result(self, repo, mock_db_manager):
        """Test document creation failure when no result returned."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = []
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        with pytest.raises(RuntimeError, match="Failed to create document"):
            await repo.create(name="Test Doc", version="1.0.0")

    @pytest.mark.asyncio
    async def test_create_database_error(self, repo, mock_db_manager):
        """Test document creation with database error."""
        # Mock the connection context manager to raise an exception
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("Database error")

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        with pytest.raises(Exception, match="Database error"):
            await repo.create(name="Test Doc", version="1.0.0")

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repo, mock_db_manager, sample_document):
        """Test successful document retrieval by ID."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": 1,
                "name": "Test Doc",
                "version": "1.0.0",
                "source_url": "https://example.com",
                "description": "A test document",
                "metadata": {"key": "value"},
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "updated_at": datetime(2024, 1, 1, 12, 0, 0),
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.get_by_id(1)

        assert result == sample_document

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo, mock_db_manager):
        """Test document retrieval when document not found."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = []
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.get_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name_version_success(self, repo, mock_db_manager, sample_document):
        """Test successful document retrieval by name and version."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": 1,
                "name": "Test Doc",
                "version": "1.0.0",
                "source_url": "https://example.com",
                "description": "A test document",
                "metadata": {"key": "value"},
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "updated_at": datetime(2024, 1, 1, 12, 0, 0),
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.get_by_name_version("Test Doc", "1.0.0")

        assert result == sample_document

    @pytest.mark.asyncio
    async def test_find_by_query_default_fields(self, repo, mock_db_manager, sample_document):
        """Test document search with default fields."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": 1,
                "name": "Test Doc",
                "version": "1.0.0",
                "source_url": "https://example.com",
                "description": "A test document",
                "metadata": {"key": "value"},
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "updated_at": datetime(2024, 1, 1, 12, 0, 0),
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        results = await repo.find_by_query("test", limit=5)

        assert len(results) == 1
        assert results[0] == sample_document

    @pytest.mark.asyncio
    async def test_find_by_query_custom_fields(self, repo, mock_db_manager):
        """Test document search with custom fields."""
        # Mock the connection context manager and execute result with empty rows
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = []
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        results = await repo.find_by_query("test", search_fields=["name", "source_url"])

        assert results == []

    @pytest.mark.asyncio
    async def test_find_by_query_empty_fields(self, repo, mock_db_manager):
        """Test document search with empty search fields."""
        results = await repo.find_by_query("test", search_fields=[])

        assert results == []

    @pytest.mark.asyncio
    async def test_list_all_success(self, repo, mock_db_manager, sample_document):
        """Test listing all documents."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": 1,
                "name": "Test Doc",
                "version": "1.0.0",
                "source_url": "https://example.com",
                "description": "A test document",
                "metadata": {"key": "value"},
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "updated_at": datetime(2024, 1, 1, 12, 0, 0),
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        results = await repo.list_all(offset=10, limit=20)

        assert len(results) == 1
        assert results[0] == sample_document

    @pytest.mark.asyncio
    async def test_list_versions_success(self, repo, mock_db_manager):
        """Test listing document versions."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {"version": "1.0.0"},
            {"version": "1.1.0"},
            {"version": "2.0.0"},
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        results = await repo.list_versions("Test Doc")

        assert results == ["1.0.0", "1.1.0", "2.0.0"]

    @pytest.mark.asyncio
    async def test_update_success(self, repo, mock_db_manager):
        """Test successful document update."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        # PSQLPy returns "UPDATE 1" for successful update
        mock_result.result.return_value = "UPDATE 1"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.update(1, name="Updated Name", description="Updated desc")

        assert result is True

    @pytest.mark.asyncio
    async def test_update_no_fields(self, repo, mock_db_manager):
        """Test update with no fields provided."""
        result = await repo.update(1)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_invalid_fields(self, repo, mock_db_manager):
        """Test update with invalid field names."""
        result = await repo.update(1, invalid_field="value")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_no_rows_affected(self, repo, mock_db_manager):
        """Test update when no rows are affected."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        # PSQLPy returns "UPDATE 0" when no rows affected
        mock_result.result.return_value = "UPDATE 0"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.update(1, name="New Name")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self, repo, mock_db_manager):
        """Test successful document deletion."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        # PSQLPy returns "DELETE 1" for successful delete
        mock_result.result.return_value = "DELETE 1"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.delete(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_no_rows_affected(self, repo, mock_db_manager):
        """Test delete when no rows are affected."""
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        # PSQLPy returns "DELETE 0" when no rows affected
        mock_result.result.return_value = "DELETE 0"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.delete(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_all_methods_handle_exceptions(self, repo, mock_db_manager):
        """Test that all methods properly handle and re-raise exceptions."""
        # Mock the connection context manager to raise an exception
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("DB Error")

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        methods_to_test = [
            (repo.create, ["name", "version"], {}),
            (repo.get_by_id, [1], {}),
            (repo.get_by_name_version, ["name", "version"], {}),
            (repo.find_by_query, ["query"], {}),
            (repo.list_all, [], {}),
            (repo.list_versions, ["name"], {}),
            (repo.update, [1], {"name": "test"}),
            (repo.delete, [1], {}),
        ]

        for method, args, kwargs in methods_to_test:
            with pytest.raises(Exception, match="DB Error"):
                await method(*args, **kwargs)


class TestDocumentRepositoryIntegration:
    """Integration tests for DocumentRepository (basic validation)."""

    @pytest.fixture
    def repo(self):
        """Create a DocumentRepository instance for integration tests."""
        mock_conn = MagicMock()
        return DocumentRepository(mock_conn)

    def test_repository_instantiation(self):
        """Test that DocumentRepository can be instantiated."""
        mock_conn = MagicMock()
        repo = DocumentRepository(mock_conn)
        assert repo.db_manager == mock_conn

    def test_document_dataclass(self, sample_document):
        """Test that Document BaseModel works correctly."""
        assert sample_document.id == 1
        assert sample_document.name == "Test Doc"
        assert sample_document.version == "1.0.0"
        assert sample_document.source_url == "https://example.com"
        assert sample_document.description == "A test document"
        assert sample_document.metadata == {"key": "value"}
        assert sample_document.created_at == datetime(2024, 1, 1, 12, 0, 0)
        assert sample_document.updated_at == datetime(2024, 1, 1, 12, 0, 0)

    def test_all_methods_exist(self):
        """Test that all expected methods exist on the repository."""
        mock_conn = MagicMock()
        repo = DocumentRepository(mock_conn)

        expected_methods = [
            "create",
            "get_by_id",
            "get_by_name_version",
            "find_by_query",
            "list_all",
            "list_versions",
            "update",
            "delete",
        ]

        for method_name in expected_methods:
            assert hasattr(repo, method_name), f"Method {method_name} should exist"
            assert callable(getattr(repo, method_name)), f"Method {method_name} should be callable"
