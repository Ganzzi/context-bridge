"""
Tests for ChunkRepository.

This module contains unit tests for the ChunkRepository class,
testing all CRUD operations and search functionality with mocked PSQLPy connections.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4
from context_bridge.database.repositories.chunk_repository import (
    ChunkRepository,
    Chunk,
    SearchResult,
)
from context_bridge.database.postgres_manager import PostgreSQLManager


@pytest.fixture
def sample_chunk():
    """
    Create a sample Chunk instance for testing.

    Returns:
        Chunk with test data
    """
    return Chunk(
        id=1,
        document_id=100,
        group_id=None,
        chunk_index=0,
        content="This is a test chunk content.",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def sample_search_result():
    """
    Create a sample SearchResult instance for testing.

    Returns:
        SearchResult with test data
    """
    chunk = Chunk(
        id=1,
        document_id=100,
        group_id=None,
        chunk_index=0,
        content="This is a test chunk content.",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    return SearchResult(
        chunk=chunk,
        score=0.85,
        rank=1,
    )


class TestChunkRepositoryUnit:
    """
    Unit tests for ChunkRepository functionality.

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
        Create a ChunkRepository instance with mocked manager.

        Args:
            mock_db_manager: Mocked PostgreSQLManager

        Returns:
            ChunkRepository instance for testing
        """
        return ChunkRepository(mock_db_manager)

    @pytest.mark.asyncio
    async def test_create_success(self, repo, mock_db_manager, sample_chunk):
        """
        Test successful chunk creation.

        Verifies that:
        - Chunk is created with all parameters
        - ID is extracted from PSQLPy result
        - Correct SQL parameters are passed
        """
        # Mock the connection context manager and execute result
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [{"id": 123}]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.create(
            document_id=100,
            group_id=None,
            chunk_index=0,
            content="Test content",
            embedding=[0.1, 0.2, 0.3],
        )

        assert result == 123
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO chunks" in call_args[0][0]
        assert "document_id" in call_args[0][0]
        assert "chunk_index" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_failure_no_result(self, repo, mock_db_manager):
        """
        Test chunk creation when no result is returned.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = []
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        with pytest.raises(RuntimeError, match="Failed to create chunk"):
            await repo.create(
                document_id=100,
                group_id=None,
                chunk_index=0,
                content="Test content",
                embedding=[0.1, 0.2, 0.3],
            )

    @pytest.mark.asyncio
    async def test_create_database_error(self, repo, mock_db_manager):
        """
        Test chunk creation with database error.
        """
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("Database error")

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        with pytest.raises(Exception, match="Database error"):
            await repo.create(
                document_id=100,
                group_id=None,
                chunk_index=0,
                content="Test content",
                embedding=[0.1, 0.2, 0.3],
            )

    @pytest.mark.asyncio
    async def test_create_batch_success(self, repo, mock_db_manager):
        """
        Test successful batch chunk creation.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        chunks_data = [
            {
                "document_id": 100,
                "group_id": None,
                "chunk_index": 0,
                "content": "Content 1",
                "embedding": [0.1, 0.2, 0.3],
            },
            {
                "document_id": 100,
                "group_id": None,
                "chunk_index": 1,
                "content": "Content 2",
                "embedding": [0.4, 0.5, 0.6],
            },
        ]

        result = await repo.create_batch(chunks_data)

        assert result == [1, 2, 3]
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_batch_empty_list(self, repo, mock_db_manager):
        """
        Test batch creation with empty list.
        """
        result = await repo.create_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repo, mock_db_manager, sample_chunk):
        """
        Test successful chunk retrieval by ID.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": sample_chunk.id,
                "document_id": sample_chunk.document_id,
                "group_id": sample_chunk.group_id,
                "chunk_index": sample_chunk.chunk_index,
                "content": sample_chunk.content,
                "embedding": sample_chunk.embedding,
                "created_at": sample_chunk.created_at,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.get_by_id(1)

        assert result is not None
        assert result.id == sample_chunk.id
        assert result.document_id == sample_chunk.document_id
        assert result.content == sample_chunk.content

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo, mock_db_manager):
        """
        Test chunk retrieval when chunk doesn't exist.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = []
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.get_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_document_success(self, repo, mock_db_manager, sample_chunk):
        """
        Test listing chunks by document ID.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": sample_chunk.id,
                "document_id": sample_chunk.document_id,
                "group_id": sample_chunk.group_id,
                "chunk_index": sample_chunk.chunk_index,
                "content": sample_chunk.content,
                "embedding": sample_chunk.embedding,
                "created_at": sample_chunk.created_at,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.list_by_document(document_id=100, offset=0, limit=10)

        assert len(result) == 1
        assert result[0].id == sample_chunk.id

    @pytest.mark.asyncio
    async def test_count_by_document_success(self, repo, mock_db_manager):
        """
        Test counting chunks by document ID.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [{"count": 5}]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.count_by_document(100)

        assert result == 5

    @pytest.mark.asyncio
    async def test_vector_search_success(self, repo, mock_db_manager, sample_chunk):
        """
        Test vector search functionality.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": sample_chunk.id,
                "document_id": sample_chunk.document_id,
                "group_id": sample_chunk.group_id,
                "chunk_index": sample_chunk.chunk_index,
                "content": sample_chunk.content,
                "embedding": sample_chunk.embedding,
                "created_at": sample_chunk.created_at,
                "similarity_score": 0.85,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = await repo.vector_search(
            query_embedding=query_embedding, document_id=100, limit=10
        )

        assert len(result) == 1
        assert isinstance(result[0], SearchResult)
        assert result[0].score == 0.85
        assert result[0].rank == 1

    @pytest.mark.asyncio
    async def test_bm25_search_success(self, repo, mock_db_manager, sample_chunk):
        """
        Test BM25 search functionality.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": sample_chunk.id,
                "document_id": sample_chunk.document_id,
                "group_id": sample_chunk.group_id,
                "chunk_index": sample_chunk.chunk_index,
                "content": sample_chunk.content,
                "embedding": sample_chunk.embedding,
                "created_at": sample_chunk.created_at,
                "bm25_score": 2.5,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.bm25_search(query="test query", document_id=100, limit=10)

        assert len(result) == 1
        assert isinstance(result[0], SearchResult)
        assert result[0].score == 2.5

    @pytest.mark.asyncio
    async def test_hybrid_search_success(self, repo, mock_db_manager, sample_chunk):
        """
        Test hybrid search functionality.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [
            {
                "id": sample_chunk.id,
                "document_id": sample_chunk.document_id,
                "group_id": sample_chunk.group_id,
                "chunk_index": sample_chunk.chunk_index,
                "content": sample_chunk.content,
                "embedding": sample_chunk.embedding,
                "created_at": sample_chunk.created_at,
                "combined_score": 0.75,
            }
        ]
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = await repo.hybrid_search(
            query="test query", query_embedding=query_embedding, document_id=100, limit=10
        )

        assert len(result) == 1
        assert isinstance(result[0], SearchResult)
        assert result[0].score == 0.75

    @pytest.mark.asyncio
    async def test_delete_by_document_success(self, repo, mock_db_manager):
        """
        Test deleting chunks by document ID.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = "DELETE 5"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        result = await repo.delete_by_document(100)

        assert result == 5

    @pytest.mark.asyncio
    async def test_delete_by_group_success(self, repo, mock_db_manager):
        """
        Test deleting chunks by group ID.
        """
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = "DELETE 3"
        mock_conn.execute.return_value = mock_result

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        group_id = uuid4()
        result = await repo.delete_by_group(group_id)

        assert result == 3

    @pytest.mark.asyncio
    async def test_all_methods_handle_exceptions(self, repo, mock_db_manager):
        """
        Test that all methods properly handle and re-raise exceptions.
        """
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("Database connection failed")

        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.connection.return_value.__aexit__.return_value = None

        # Test create
        with pytest.raises(Exception, match="Database connection failed"):
            await repo.create(
                document_id=100,
                group_id=None,
                chunk_index=0,
                content="Test",
                embedding=[0.1, 0.2, 0.3],
            )

        # Test get_by_id
        with pytest.raises(Exception, match="Database connection failed"):
            await repo.get_by_id(1)


class TestChunkRepositoryIntegration:
    """
    Integration tests for ChunkRepository.

    These tests verify the repository instantiation and method existence.
    """

    @pytest.fixture
    def repo(self, mock_db_manager):
        """
        Create a ChunkRepository instance for integration testing.
        """
        return ChunkRepository(mock_db_manager)

    def test_repository_instantiation(self, mock_db_manager):
        """
        Test that ChunkRepository can be instantiated.
        """
        repo = ChunkRepository(mock_db_manager)
        assert repo is not None
        assert repo.db_manager == mock_db_manager

    def test_dataclass(self, sample_chunk):
        """
        Test Chunk dataclass functionality.
        """
        assert sample_chunk.id == 1
        assert sample_chunk.document_id == 100
        assert sample_chunk.chunk_index == 0
        assert sample_chunk.content == "This is a test chunk content."
        assert len(sample_chunk.embedding) == 5

    def test_search_result_dataclass(self, sample_search_result):
        """
        Test SearchResult dataclass functionality.
        """
        assert sample_search_result.score == 0.85
        assert sample_search_result.rank == 1
        assert isinstance(sample_search_result.chunk, Chunk)

    def test_all_methods_exist(self, repo):
        """
        Test that all expected methods exist on the repository.
        """
        expected_methods = [
            "create",
            "create_batch",
            "get_by_id",
            "list_by_document",
            "count_by_document",
            "vector_search",
            "bm25_search",
            "hybrid_search",
            "delete_by_document",
            "delete_by_group",
        ]

        for method_name in expected_methods:
            assert hasattr(repo, method_name), f"Method {method_name} should exist"
            assert callable(getattr(repo, method_name)), f"Method {method_name} should be callable"
