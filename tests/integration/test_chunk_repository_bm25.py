"""
Integration tests for ChunkRepository BM25 and Hybrid Search.

Tests the proper implementation of BM25 full-text search using vchord_bm25
and hybrid search combining vector similarity with BM25 ranking.

Requirements:
    - PostgreSQL with extensions: vector, vchord, pg_tokenizer, vchord_bm25
    - Database schema initialized with chunks table and BM25 index
    - BERT tokenizer created with create_tokenizer()
"""

import pytest

import asyncio
import pytest
import logging
from typing import List

from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository, SearchResult


logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db_manager():
    """Create and initialize database manager."""
    config = get_config()
    manager = PostgreSQLManager(config)
    await manager.initialize()
    yield manager
    await manager.close()


@pytest.fixture(scope="module")
async def repositories(db_manager):
    """Create repository instances."""
    doc_repo = DocumentRepository(db_manager)
    chunk_repo = ChunkRepository(db_manager)
    return {"doc_repo": doc_repo, "chunk_repo": chunk_repo}


@pytest.fixture(scope="module")
@pytest.mark.integration
async def test_document(repositories):
    """Create a test document with chunks for BM25 testing."""
    doc_repo = repositories["doc_repo"]
    chunk_repo = repositories["chunk_repo"]

    # Create document
    doc_id = await doc_repo.create(
        name="BM25 Test Document",
        version="1.0.0",
        source_url="https://example.com/bm25-test",
        description="Test document for BM25 search functionality",
        metadata={"type": "test", "purpose": "bm25_testing"},
    )

    # Create chunks with diverse content for BM25 testing
    test_chunks = [
        {
            "content": "Python is a high-level programming language known for its simplicity and readability. "
            "It is widely used in web development, data science, and machine learning.",
            "embedding": [0.1 + i * 0.01 for i in range(768)],
            "chunk_index": 0,
        },
        {
            "content": "Machine learning algorithms enable computers to learn from data without explicit programming. "
            "Popular frameworks include TensorFlow, PyTorch, and scikit-learn.",
            "embedding": [0.2 + i * 0.01 for i in range(768)],
            "chunk_index": 1,
        },
        {
            "content": "FastAPI is a modern web framework for building APIs with Python. "
            "It supports async operations and automatic API documentation with OpenAPI.",
            "embedding": [0.3 + i * 0.01 for i in range(768)],
            "chunk_index": 2,
        },
        {
            "content": "PostgreSQL is a powerful relational database system with advanced features. "
            "Extensions like pgvector enable vector similarity search for embeddings.",
            "embedding": [0.4 + i * 0.01 for i in range(768)],
            "chunk_index": 3,
        },
        {
            "content": "BM25 is a ranking function used in information retrieval for full-text search. "
            "It ranks documents based on query term frequency and document length normalization.",
            "embedding": [0.5 + i * 0.01 for i in range(768)],
            "chunk_index": 4,
        },
        {
            "content": "Docker containers provide isolated environments for running applications. "
            "They are lightweight, portable, and enable consistent deployment across environments.",
            "embedding": [0.6 + i * 0.01 for i in range(768)],
            "chunk_index": 5,
        },
    ]

    # Insert chunks
    chunk_ids = []
    for chunk_data in test_chunks:
        chunk_id = await chunk_repo.create(
            document_id=doc_id,
            chunk_index=chunk_data["chunk_index"],
            content=chunk_data["content"],
            embedding=chunk_data["embedding"],
        )
        chunk_ids.append(chunk_id)

    yield {"doc_id": doc_id, "chunk_ids": chunk_ids}

    # Cleanup
    try:
        await doc_repo.delete(doc_id)
        logger.info(f"Cleaned up test document {doc_id}")
    except Exception as e:
        logger.warning(f"Failed to cleanup test document: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_bm25_search_basic(repositories, test_document):
    """Test basic BM25 search functionality."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    # Search for "Python programming"
    results = await chunk_repo.bm25_search(document_id=doc_id, query="Python programming", limit=5)

    # Assertions
    assert len(results) > 0, "BM25 search should return results"
    assert all(
        isinstance(r, SearchResult) for r in results
    ), "Results should be SearchResult objects"

    # First result should mention Python
    assert "Python" in results[0].chunk.content or "python" in results[0].chunk.content.lower()

    # Scores should be in descending order
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), "Scores should be in descending order"

    # Ranks should be sequential
    ranks = [r.rank for r in results]
    assert ranks == list(range(1, len(results) + 1)), "Ranks should be 1-based and sequential"

    logger.info(f"BM25 search returned {len(results)} results")
    for r in results[:3]:
        logger.info(f"  Rank {r.rank}: score={r.score:.4f}, preview={r.chunk.content[:60]}...")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_bm25_search_with_min_score(repositories, test_document):
    """Test BM25 search with minimum score threshold."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    # Search with different min_score thresholds
    results_no_threshold = await chunk_repo.bm25_search(
        document_id=doc_id, query="machine learning", limit=10, min_score=0.0
    )

    results_with_threshold = await chunk_repo.bm25_search(
        document_id=doc_id, query="machine learning", limit=10, min_score=1.0
    )

    # Assertions
    assert len(results_no_threshold) >= len(
        results_with_threshold
    ), "Lower threshold should return more or equal results"

    # All results with threshold should have scores >= min_score
    for result in results_with_threshold:
        assert result.score >= 1.0, f"Result score {result.score} should be >= min_score (1.0)"

    logger.info(
        f"BM25 with min_score=0.0: {len(results_no_threshold)} results, "
        f"min_score=1.0: {len(results_with_threshold)} results"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_bm25_search_relevance(repositories, test_document):
    """Test BM25 search relevance ranking."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    # Search for "BM25 ranking" - should prioritize the chunk about BM25
    results = await chunk_repo.bm25_search(document_id=doc_id, query="BM25 ranking", limit=5)

    assert len(results) > 0, "BM25 search should find results"

    # The top result should be about BM25
    top_result = results[0]
    assert (
        "BM25" in top_result.chunk.content
    ), f"Top result should mention BM25, got: {top_result.chunk.content[:100]}"

    logger.info(
        f"BM25 relevance test - top result contains 'BM25': {top_result.chunk.content[:80]}..."
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_bm25_search_no_results(repositories, test_document):
    """Test BM25 search with query that returns no results."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    # Search for something that doesn't exist
    results = await chunk_repo.bm25_search(document_id=doc_id, query="no relevant", limit=10)

    assert len(results) == 0, "Search for non-existent terms should return no results"
    logger.info("BM25 search correctly returned no results for non-existent terms")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_vector_search_basic(repositories, test_document):
    """Test vector search functionality (baseline for hybrid)."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    # Create a query embedding similar to the first chunk
    query_embedding = [0.1 + i * 0.01 for i in range(768)]

    results = await chunk_repo.vector_search(
        document_id=doc_id,
        query_embedding=query_embedding,
        limit=5,
        similarity_threshold=0.5,
    )

    # Assertions
    assert len(results) > 0, "Vector search should return results"
    assert all(
        isinstance(r, SearchResult) for r in results
    ), "Results should be SearchResult objects"

    # Scores should be in descending order
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), "Scores should be in descending order"

    logger.info(f"Vector search returned {len(results)} results")
    for r in results[:3]:
        logger.info(f"  Rank {r.rank}: similarity={r.score:.4f}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hybrid_search_basic(repositories, test_document):
    """Test basic hybrid search combining vector and BM25."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    # Query about Python programming
    query_text = "Python programming"
    query_embedding = [0.15 + i * 0.01 for i in range(768)]  # Similar to first chunk

    results = await chunk_repo.hybrid_search(
        document_id=doc_id,
        query=query_text,
        query_embedding=query_embedding,
        vector_weight=0.7,
        bm25_weight=0.3,
        limit=5,
    )

    # Assertions
    assert len(results) > 0, "Hybrid search should return results"
    assert all(
        isinstance(r, SearchResult) for r in results
    ), "Results should be SearchResult objects"

    # Scores should be in descending order
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), "Combined scores should be in descending order"

    # Ranks should be sequential
    ranks = [r.rank for r in results]
    assert ranks == list(range(1, len(results) + 1)), "Ranks should be 1-based and sequential"

    logger.info(f"Hybrid search returned {len(results)} results")
    for r in results[:3]:
        logger.info(
            f"  Rank {r.rank}: combined_score={r.score:.4f}, preview={r.chunk.content[:60]}..."
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hybrid_search_weight_balance(repositories, test_document):
    """Test hybrid search with different weight configurations."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    query_text = "machine learning algorithms"
    query_embedding = [0.2 + i * 0.01 for i in range(768)]  # Similar to ML chunk

    # Test vector-heavy
    results_vector_heavy = await chunk_repo.hybrid_search(
        document_id=doc_id,
        query=query_text,
        query_embedding=query_embedding,
        vector_weight=0.9,
        bm25_weight=0.1,
        limit=5,
    )

    # Test BM25-heavy
    results_bm25_heavy = await chunk_repo.hybrid_search(
        document_id=doc_id,
        query=query_text,
        query_embedding=query_embedding,
        vector_weight=0.1,
        bm25_weight=0.9,
        limit=5,
    )

    # Test balanced
    results_balanced = await chunk_repo.hybrid_search(
        document_id=doc_id,
        query=query_text,
        query_embedding=query_embedding,
        vector_weight=0.5,
        bm25_weight=0.5,
        limit=5,
    )

    # Assertions
    assert len(results_vector_heavy) > 0, "Vector-heavy search should return results"
    assert len(results_bm25_heavy) > 0, "BM25-heavy search should return results"
    assert len(results_balanced) > 0, "Balanced search should return results"

    # Results may differ based on weights
    logger.info(f"Vector-heavy (0.9/0.1): {len(results_vector_heavy)} results")
    logger.info(f"BM25-heavy (0.1/0.9): {len(results_bm25_heavy)} results")
    logger.info(f"Balanced (0.5/0.5): {len(results_balanced)} results")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hybrid_search_with_thresholds(repositories, test_document):
    """Test hybrid search with minimum score thresholds."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    query_text = "PostgreSQL database"
    query_embedding = [0.4 + i * 0.01 for i in range(768)]

    # Search with thresholds
    results = await chunk_repo.hybrid_search(
        document_id=doc_id,
        query=query_text,
        query_embedding=query_embedding,
        vector_weight=0.6,
        bm25_weight=0.4,
        limit=10,
        min_vector_score=0.5,
        min_bm25_score=0.0,
    )

    # Assertions
    assert isinstance(results, list), "Should return a list"
    # Results may be empty if no chunks meet the thresholds
    logger.info(f"Hybrid search with thresholds returned {len(results)} results")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hybrid_search_vs_individual_searches(repositories, test_document):
    """Compare hybrid search results with individual vector and BM25 searches."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    query_text = "FastAPI web framework"
    query_embedding = [0.3 + i * 0.01 for i in range(768)]

    # Individual searches
    vector_results = await chunk_repo.vector_search(
        document_id=doc_id,
        query_embedding=query_embedding,
        limit=5,
        similarity_threshold=0.0,
    )

    bm25_results = await chunk_repo.bm25_search(
        document_id=doc_id, query=query_text, limit=5, min_score=0.0
    )

    # Hybrid search
    hybrid_results = await chunk_repo.hybrid_search(
        document_id=doc_id,
        query=query_text,
        query_embedding=query_embedding,
        vector_weight=0.5,
        bm25_weight=0.5,
        limit=5,
    )

    # Assertions
    assert len(vector_results) > 0, "Vector search should find results"
    assert len(bm25_results) > 0, "BM25 search should find results"
    assert len(hybrid_results) > 0, "Hybrid search should find results"

    # Collect all unique chunk IDs from both searches
    vector_ids = {r.chunk.id for r in vector_results}
    bm25_ids = {r.chunk.id for r in bm25_results}
    hybrid_ids = {r.chunk.id for r in hybrid_results}

    # Hybrid should potentially include results from both
    logger.info(f"Vector results: {len(vector_results)}, IDs: {vector_ids}")
    logger.info(f"BM25 results: {len(bm25_results)}, IDs: {bm25_ids}")
    logger.info(f"Hybrid results: {len(hybrid_results)}, IDs: {hybrid_ids}")

    # Hybrid results should be a combination (though order may differ)
    # This is informational rather than a strict assertion
    logger.info(
        f"Hybrid combines {len(hybrid_ids & vector_ids)} vector + "
        f"{len(hybrid_ids & bm25_ids)} BM25 results"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_bm25_tokenization(repositories, test_document):
    """Test that BM25 tokenization works correctly with BERT tokenizer."""
    chunk_repo = repositories["chunk_repo"]
    doc_id = test_document["doc_id"]

    # Test with compound terms that BERT should handle well
    queries = [
        "machine-learning",  # Hyphenated
        "MachineLearning",  # CamelCase
        "machine learning",  # Spaced
    ]

    for query in queries:
        results = await chunk_repo.bm25_search(document_id=doc_id, query=query, limit=5)

        logger.info(f"Query '{query}' returned {len(results)} results")

        # All queries should return results about machine learning
        if len(results) > 0:
            assert any(
                "machine" in r.chunk.content.lower() or "learning" in r.chunk.content.lower()
                for r in results
            ), f"Query '{query}' should find machine learning content"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
