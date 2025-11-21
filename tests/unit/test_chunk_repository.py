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


class TestChunkRepositoryGroupMethods:
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
        """Create a ChunkRepository with mocked database manager."""
        return ChunkRepository(mock_db_manager)

    @pytest.fixture
    def sample_group_id(self):
        """Generate a sample group UUID."""
        return uuid4()

    @pytest.fixture
    def sample_chunks_with_group(self, sample_group_id):
        """Create sample chunk rows with group_id for testing."""
        return [
            {
                "id": 1,
                "document_id": 100,
                "group_id": sample_group_id,
                "chunk_index": 0,
                "content": "Chunk 1 content",
                "embedding": [0.1, 0.2, 0.3],
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
            },
            {
                "id": 2,
                "document_id": 100,
                "group_id": sample_group_id,
                "chunk_index": 1,
                "content": "Chunk 2 content",
                "embedding": [0.4, 0.5, 0.6],
                "created_at": datetime(2024, 1, 1, 12, 0, 1),
            },
            {
                "id": 3,
                "document_id": 100,
                "group_id": sample_group_id,
                "chunk_index": 2,
                "content": "Chunk 3 content",
                "embedding": [0.7, 0.8, 0.9],
                "created_at": datetime(2024, 1, 1, 12, 0, 2),
            },
        ]

    @pytest.mark.asyncio
    async def test_get_chunks_for_group_success(
        self, repo, mock_db_manager, sample_group_id, sample_chunks_with_group
    ):
        """
        Test successful retrieval of chunks for a group.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = sample_chunks_with_group
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        chunks = await repo.get_chunks_for_group(sample_group_id, limit=1000)

        assert len(chunks) == 3
        assert all(chunk.group_id == sample_group_id for chunk in chunks)
        assert chunks[0].content == "Chunk 1 content"
        assert chunks[1].content == "Chunk 2 content"
        assert chunks[2].content == "Chunk 3 content"

        # Verify query was called correctly
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "WHERE group_id = $1" in call_args[0][0]
        assert "LIMIT $2" in call_args[0][0]
        assert str(sample_group_id) in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_chunks_for_group_with_limit(
        self, repo, mock_db_manager, sample_group_id, sample_chunks_with_group
    ):
        """
        Test that limit parameter is passed correctly.
        """
        limited_chunks = sample_chunks_with_group[:2]
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = limited_chunks
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        chunks = await repo.get_chunks_for_group(sample_group_id, limit=2)

        assert len(chunks) == 2
        call_args = mock_conn.execute.call_args
        assert call_args[0][1][1] == 2  # Second parameter should be limit

    @pytest.mark.asyncio
    async def test_get_chunks_for_group_empty(self, repo, mock_db_manager, sample_group_id):
        """
        Test retrieval when no chunks exist for group.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        chunks = await repo.get_chunks_for_group(sample_group_id)

        assert chunks == []

    @pytest.mark.asyncio
    async def test_get_chunks_for_group_db_error(self, repo, mock_db_manager, sample_group_id):
        """
        Test error handling when database query fails.
        """
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB Error"))
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        with pytest.raises(Exception) as exc_info:
            await repo.get_chunks_for_group(sample_group_id)

        assert "DB Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_group_chunk_statistics_success(self, repo, mock_db_manager, sample_group_id):
        """
        Test successful retrieval of group chunk statistics.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = [
            {
                "total_chunks": 10,
                "total_length": 5000,
                "avg_size": 500.0,
            }
        ]
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        stats = await repo.get_group_chunk_statistics(sample_group_id)

        assert stats["total_chunks"] == 10
        assert stats["total_content_length"] == 5000
        assert stats["avg_chunk_size"] == 500.0

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "WHERE group_id = $1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_group_chunk_statistics_empty_group(
        self, repo, mock_db_manager, sample_group_id
    ):
        """
        Test statistics when group has no chunks.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = [
            {
                "total_chunks": None,
                "total_length": None,
                "avg_size": None,
            }
        ]
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        stats = await repo.get_group_chunk_statistics(sample_group_id)

        assert stats["total_chunks"] == 0
        assert stats["total_content_length"] == 0
        assert stats["avg_chunk_size"] == 0.0

    @pytest.mark.asyncio
    async def test_get_group_chunk_statistics_db_error(
        self, repo, mock_db_manager, sample_group_id
    ):
        """
        Test error handling for statistics query.
        """
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB Error"))
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        with pytest.raises(Exception) as exc_info:
            await repo.get_group_chunk_statistics(sample_group_id)

        assert "DB Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_chunks_in_group_hybrid(
        self, repo, mock_db_manager, sample_group_id, sample_chunks_with_group
    ):
        """
        Test hybrid search within a group.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        # Add relevance score to results
        result_with_score = [{**chunk, "relevance": 0.85} for chunk in sample_chunks_with_group]
        mock_result.result.return_value = result_with_score
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        embedding = [0.5, 0.5, 0.5]
        results = await repo.search_chunks_in_group(
            query_text="test query",
            embedding=embedding,
            group_id=sample_group_id,
            hybrid=True,
            limit=10,
        )

        assert len(results) == 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(r.chunk.group_id == sample_group_id for r in results)
        assert results[0].rank == 1
        assert results[1].rank == 2

        call_args = mock_conn.execute.call_args
        assert "0.7 *" in call_args[0][0]  # Hybrid weighting
        assert "0.3 *" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_search_chunks_in_group_bm25_only(
        self, repo, mock_db_manager, sample_group_id, sample_chunks_with_group
    ):
        """
        Test BM25-only search within a group.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        result_with_score = [{**chunk, "relevance": 0.75} for chunk in sample_chunks_with_group[:2]]
        mock_result.result.return_value = result_with_score
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        embedding = [0.5, 0.5, 0.5]
        results = await repo.search_chunks_in_group(
            query_text="test query",
            embedding=embedding,
            group_id=sample_group_id,
            hybrid=False,
            limit=10,
        )

        assert len(results) == 2
        call_args = mock_conn.execute.call_args
        assert "0.7 *" not in call_args[0][0]  # No hybrid weighting
        assert "@@ to_tsquery" in call_args[0][0]  # BM25 search

    @pytest.mark.asyncio
    async def test_search_chunks_in_group_no_results(self, repo, mock_db_manager, sample_group_id):
        """
        Test search with no matching results.
        """
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        embedding = [0.5, 0.5, 0.5]
        results = await repo.search_chunks_in_group(
            query_text="nonexistent query",
            embedding=embedding,
            group_id=sample_group_id,
            hybrid=True,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_chunks_in_group_db_error(self, repo, mock_db_manager, sample_group_id):
        """
        Test error handling for search query.
        """
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB Error"))
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        embedding = [0.5, 0.5, 0.5]
        with pytest.raises(Exception) as exc_info:
            await repo.search_chunks_in_group(
                query_text="test",
                embedding=embedding,
                group_id=sample_group_id,
            )

        assert "DB Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_chunks_group_reference_success(
        self, repo, mock_db_manager, sample_group_id
    ):
        """
        Test successful bulk update of chunks group reference.
        """
        page_id = 1
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        # Simulate 5 chunks updated
        mock_result.result.return_value = [
            {"id": 1},
            {"id": 2},
            {"id": 3},
            {"id": 4},
            {"id": 5},
        ]
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        count = await repo.update_chunks_group_reference(page_id, sample_group_id)

        assert count == 5
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "$2 = ANY(source_page_ids)" in call_args[0][0]  # Array containment check
        assert page_id in call_args[0][1]

    @pytest.mark.asyncio
    async def test_update_chunks_group_reference_no_matches(
        self, repo, mock_db_manager, sample_group_id
    ):
        """
        Test update when no chunks contain the page.
        """
        page_id = 999
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.result.return_value = []  # No chunks updated
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        count = await repo.update_chunks_group_reference(page_id, sample_group_id)

        assert count == 0

    @pytest.mark.asyncio
    async def test_update_chunks_group_reference_db_error(
        self, repo, mock_db_manager, sample_group_id
    ):
        """
        Test error handling for bulk update.
        """
        page_id = 1
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB Error"))
        mock_db_manager.connection.return_value.__aenter__.return_value = mock_conn

        with pytest.raises(Exception) as exc_info:
            await repo.update_chunks_group_reference(page_id, sample_group_id)

        assert "DB Error" in str(exc_info.value)
