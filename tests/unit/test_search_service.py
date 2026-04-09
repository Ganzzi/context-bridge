"""
Unit tests for SearchService.

Tests document search, content search, and cross-version search functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from context_bridge.service.search_service import (
    SearchService,
    DocumentSearchResult,
    ContentSearchResult,
)
from context_bridge.database.repositories.document_repository import Document
from context_bridge.database.repositories.chunk_repository import Chunk, SearchResult
from context_bridge.service.embedding import EmbeddingService
from datetime import datetime


@pytest.fixture
def mock_document_repo():
    """Create a mock document repository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_chunk_repo():
    """Create a mock chunk repository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = MagicMock(spec=EmbeddingService)
    return service


@pytest.fixture
def search_service(mock_document_repo, mock_chunk_repo, mock_embedding_service):
    """Create a search service instance for testing."""
    return SearchService(
        document_repo=mock_document_repo,
        chunk_repo=mock_chunk_repo,
        embedding_service=mock_embedding_service,
        default_vector_weight=0.7,
        default_bm25_weight=0.3,
    )


class TestSearchService:
    """Test cases for SearchService."""

    def test_initialization(self, mock_document_repo, mock_chunk_repo, mock_embedding_service):
        """Test service initialization."""
        service = SearchService(
            document_repo=mock_document_repo,
            chunk_repo=mock_chunk_repo,
            embedding_service=mock_embedding_service,
        )
        assert service.document_repo == mock_document_repo
        assert service.chunk_repo == mock_chunk_repo
        assert service.embedding_service == mock_embedding_service
        assert service.default_vector_weight == 0.7
        assert service.default_bm25_weight == 0.3

    @pytest.mark.asyncio
    async def test_find_documents(self, search_service, mock_document_repo):
        """Test document search functionality."""
        # Mock document data
        mock_docs = [
            Document(
                id=1,
                name="Python Guide",
                version="1.0.0",
                description="A comprehensive Python guide",
                source_url="https://example.com/python",
                metadata={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            Document(
                id=2,
                name="Java Guide",
                version="1.0.0",
                description="A Java tutorial",
                source_url="https://example.com/java",
                metadata={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

        # Mock repository method
        mock_document_repo.find_by_query = AsyncMock(return_value=mock_docs)

        # Test search
        results = await search_service.find_documents("Python", limit=10)

        # Verify results
        assert len(results) == 2
        assert isinstance(results[0], DocumentSearchResult)
        assert results[0].document.name == "Python Guide"
        assert results[0].relevance_score > results[1].relevance_score  # Python should score higher

        # Verify repository was called correctly
        mock_document_repo.find_by_query.assert_called_once_with(
            query="Python", limit=10, search_fields=["name", "description", "source_url"]
        )

    @pytest.mark.asyncio
    async def test_search_content(
        self, search_service, mock_chunk_repo, mock_document_repo, mock_embedding_service
    ):
        """Test content search functionality."""
        # Mock data
        mock_embedding = [0.1, 0.2, 0.3]
        mock_document = Document(
            id=1,
            name="Test Doc",
            version="1.0.0",
            description="Test document",
            source_url="https://example.com/test",
            metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        mock_chunk = Chunk(
            id=1,
            document_id=1,
            group_id=None,
            chunk_index=0,
            content="Test content",
            embedding=mock_embedding,
            created_at=datetime.now(),
        )
        mock_chunk_result = SearchResult(chunk=mock_chunk, score=0.8, rank=1)

        # Mock service methods
        mock_embedding_service.get_embedding = AsyncMock(return_value=mock_embedding)
        mock_document_repo.get_by_id = AsyncMock(return_value=mock_document)
        mock_chunk_repo.hybrid_search = AsyncMock(return_value=[mock_chunk_result])

        # Test search
        results = await search_service.search_content("test query", document_id=1, limit=5)

        # Verify results
        assert len(results) == 1
        assert isinstance(results[0], ContentSearchResult)
        assert results[0].document_name == "Test Doc"
        assert results[0].document_version == "1.0.0"
        assert results[0].score == 0.8
        assert results[0].rank == 1

        # Verify method calls
        mock_embedding_service.get_embedding.assert_called_once_with("test query")
        mock_document_repo.get_by_id.assert_called_once_with(1)
        mock_chunk_repo.hybrid_search.assert_called_once_with(
            document_id=1,
            query="test query",
            query_embedding=mock_embedding,
            vector_weight=0.7,
            bm25_weight=0.3,
            limit=5,
        )

    @pytest.mark.asyncio
    async def test_search_across_versions(
        self, search_service, mock_document_repo, mock_chunk_repo, mock_embedding_service
    ):
        """Test cross-version search functionality."""
        # Mock data
        mock_embedding = [0.1, 0.2, 0.3]
        versions = ["2.0.0", "1.0.0"]

        mock_doc_v2 = Document(
            id=1,
            name="Test Doc",
            version="2.0.0",
            description="Test document v2",
            source_url="https://example.com/doc-v2",
            metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        mock_doc_v1 = Document(
            id=2,
            name="Test Doc",
            version="1.0.0",
            description="Test document v1",
            source_url="https://example.com/doc-v1",
            metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_chunk = Chunk(
            id=1,
            document_id=1,
            group_id=None,
            chunk_index=0,
            content="Test content",
            embedding=mock_embedding,
            created_at=datetime.now(),
        )
        mock_chunk_result = SearchResult(chunk=mock_chunk, score=0.9, rank=1)

        # Mock service methods
        mock_embedding_service.get_embedding = AsyncMock(return_value=mock_embedding)
        mock_document_repo.list_versions = AsyncMock(return_value=versions)
        mock_document_repo.get_by_name_version = AsyncMock(side_effect=[mock_doc_v2, mock_doc_v1])
        mock_chunk_repo.hybrid_search = AsyncMock(return_value=[mock_chunk_result])

        # Test search
        results = await search_service.search_across_versions(
            "test query", "Test Doc", limit_per_version=3
        )

        # Verify results
        assert len(results) == 2  # Both versions should have results
        assert "2.0.0" in results
        assert "1.0.0" in results
        assert len(results["2.0.0"]) == 1
        assert len(results["1.0.0"]) == 1

        # Verify method calls
        mock_document_repo.list_versions.assert_called_once_with("Test Doc")
        assert mock_document_repo.get_by_name_version.call_count == 2
        assert mock_chunk_repo.hybrid_search.call_count == 2

    def test_calculate_document_relevance(self, search_service):
        """Test document relevance calculation."""
        doc = Document(
            id=1,
            name="Python Programming",
            version="1.0.0",
            description="Learn Python programming language",
            source_url="https://python.org/guide",
            metadata={"tags": ["python", "programming"]},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Test exact name match
        score = search_service._calculate_document_relevance("Python Programming", doc)
        assert score == 1.0  # Exact match capped at 1.0

        # Test partial name match
        score = search_service._calculate_document_relevance("Python", doc)
        assert score == 1.0  # 0.7 name + 0.4 description + 0.1 metadata = 1.2, capped at 1.0

        # Test description match
        score = search_service._calculate_document_relevance("programming language", doc)
        assert score == 0.4

        # Test URL match
        score = search_service._calculate_document_relevance("python.org", doc)
        assert score == 0.2

        # Test no match
        score = search_service._calculate_document_relevance("javascript", doc)
        assert score == 0.0
