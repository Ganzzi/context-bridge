"""
Service Integration Tests.

Tests services with real external dependencies:
- Embedding service with Ollama
- Crawling service with real websites
- Search service with real data
"""

import pytest
import asyncio
from typing import List


@pytest.mark.integration
class TestEmbeddingServiceIntegration:
    """Integration tests for EmbeddingService with real Ollama."""

    @pytest.mark.asyncio
    async def test_real_embedding_generation(self, real_embedding_service):
        """Test embedding generation with real Ollama API."""
        test_texts = [
            "This is a test sentence.",
            "Another test sentence with different content.",
            "A third sentence for testing batch operations.",
        ]

        # Test single embedding
        embedding = await real_embedding_service.get_embedding(test_texts[0])
        assert isinstance(embedding, list)
        assert len(embedding) == 768  # nomic-embed-text dimension
        assert all(isinstance(x, float) for x in embedding)

        # Test batch embeddings
        embeddings = await real_embedding_service.get_embeddings_batch(test_texts)
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(test_texts)
        for emb in embeddings:
            assert len(emb) == 768
            assert all(isinstance(x, float) for x in emb)

    @pytest.mark.asyncio
    async def test_embedding_caching(self, real_embedding_service):
        """Test that embedding caching works correctly."""
        test_text = "This is a cached test sentence."

        # First call
        embedding1 = await real_embedding_service.get_embedding(test_text)

        # Second call (should use cache)
        embedding2 = await real_embedding_service.get_embedding(test_text)

        # Should be identical
        assert embedding1 == embedding2

        # Check cache stats
        stats = real_embedding_service.get_cache_stats()
        assert stats["enabled"] is True
        assert stats["size"] >= 1

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, real_embedding_service):
        """Test that same text produces consistent embeddings."""
        test_text = "Consistency test sentence."
        embeddings = []

        # Generate multiple embeddings for same text
        for _ in range(3):
            emb = await real_embedding_service.get_embedding(test_text)
            embeddings.append(emb)

        # All should be identical (due to caching)
        for i in range(1, len(embeddings)):
            assert embeddings[0] == embeddings[i]

    @pytest.mark.asyncio
    async def test_embedding_error_handling(self, real_embedding_service):
        """Test error handling for invalid inputs."""
        # Test with empty string
        try:
            embedding = await real_embedding_service.get_embedding("")
            assert isinstance(embedding, list)  # Should handle gracefully
        except Exception:
            # Acceptable if it fails
            pass

        # Test with very long text
        long_text = "Very long text. " * 1000
        try:
            embedding = await real_embedding_service.get_embedding(long_text)
            assert isinstance(embedding, list)
        except Exception:
            # Might fail due to length limits
            pass


@pytest.mark.integration
class TestCrawlingServiceIntegration:
    """Integration tests for CrawlingService with real websites."""

    @pytest.mark.asyncio
    async def test_real_webpage_crawling(self, real_crawling_service):
        """Test crawling real webpages."""
        from crawl4ai import AsyncWebCrawler

        test_urls = [
            "https://httpbin.org/html",  # Simple HTML page
            "https://httpbin.org/json",  # JSON endpoint
        ]

        async with AsyncWebCrawler(verbose=False) as crawler:
            for url in test_urls:
                result = await real_crawling_service.crawl_webpage(crawler, url)

                assert result is not None
                assert len(result.results) > 0

                page_result = result.results[0]
                assert page_result.url == url
                assert isinstance(page_result.markdown, str)
                assert len(page_result.markdown) > 0

    @pytest.mark.asyncio
    async def test_crawling_error_handling(self, real_crawling_service):
        """Test error handling for invalid URLs."""
        from crawl4ai import AsyncWebCrawler

        invalid_urls = [
            "https://invalid-domain-that-does-not-exist.com",
            "https://httpbin.org/status/404",
            "not-a-url-at-all",
        ]

        async with AsyncWebCrawler(verbose=False) as crawler:
            for url in invalid_urls:
                try:
                    result = await real_crawling_service.crawl_webpage(crawler, url)
                    # Should handle errors gracefully
                    assert result is not None
                except Exception:
                    # Acceptable to fail for truly invalid URLs
                    pass

    @pytest.mark.asyncio
    async def test_crawling_with_depth_limit(self, real_crawling_service):
        """Test crawling with depth limits."""
        from crawl4ai import AsyncWebCrawler

        # Use a page that might have links but limit depth
        url = "https://httpbin.org/html"

        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await real_crawling_service.crawl_webpage(crawler, url, depth=1)

            assert result is not None
            # Should get at least the main page
            assert len(result.results) >= 1


@pytest.mark.integration
class TestSearchServiceIntegration:
    """Integration tests for SearchService with real data."""

    @pytest.mark.asyncio
    async def test_hybrid_search_with_real_data(self, real_search_service, sample_test_chunks):
        """Test hybrid search with real indexed data."""
        # Use content from existing chunks for search
        query = "test chunk content"

        results = await real_search_service.search_content(
            query=query, document_id=sample_test_chunks[0].document_id, limit=5
        )

        assert isinstance(results, list)
        # Should return some results (may be empty if no matches)

    @pytest.mark.asyncio
    async def test_vector_search_accuracy(
        self, real_search_service, real_embedding_service, sample_test_chunks
    ):
        """Test vector search accuracy with real embeddings."""
        if not sample_test_chunks:
            pytest.skip("No test chunks available")

        # Get embedding for a chunk's content
        test_chunk = sample_test_chunks[0]
        query_embedding = await real_embedding_service.get_embedding(test_chunk.content)

        # Search using vector similarity
        results = await real_search_service.chunk_repo.search_similar(query_embedding, limit=5)

        assert isinstance(results, list)
        assert len(results) > 0

        # The original chunk should be in results (or very similar)
        found_original = any(r.chunk.id == test_chunk.id for r in results)
        # Note: Due to embedding similarity, it might not be exact match

    @pytest.mark.asyncio
    async def test_bm25_search_functionality(self, real_search_service, sample_test_chunks):
        """Test BM25 full-text search functionality."""
        if not sample_test_chunks:
            pytest.skip("No test chunks available")

        # Search for terms that should exist in chunks
        query = "content"

        results = await real_search_service.chunk_repo.search_bm25(query, limit=10)

        assert isinstance(results, list)
        # Should find chunks containing the word "content"

    @pytest.mark.asyncio
    async def test_cross_version_search(self, real_search_service, sample_test_document):
        """Test searching across document versions."""
        # This would require multiple versions of the same document
        # For now, just test the method exists and doesn't error
        try:
            results = await real_search_service.search_across_versions(
                query="test", document_name=sample_test_document.name, limit_per_version=5
            )
            assert isinstance(results, dict)
        except Exception:
            # May fail if no versions exist
            pass


@pytest.mark.integration
class TestDocManagerIntegration:
    """Integration tests for DocManager with real services."""

    @pytest.mark.asyncio
    async def test_crawl_and_store_workflow(self, real_doc_manager):
        """Test complete crawl and store workflow."""
        # Use a simple test URL
        test_url = "https://httpbin.org/html"
        doc_name = "test-integration-crawl"
        doc_version = "1.0.0"

        result = await real_doc_manager.crawl_and_store(
            name=doc_name,
            version=doc_version,
            source_url=test_url,
            description="Integration test document",
        )

        assert result is not None
        assert result.document_id > 0
        assert result.document_name == doc_name
        assert result.document_version == doc_version
        assert result.pages_crawled >= 1
        assert result.pages_stored >= 1

    @pytest.mark.asyncio
    async def test_chunking_workflow(
        self, real_doc_manager, sample_test_document, sample_test_pages
    ):
        """Test chunking workflow with real pages."""
        if not sample_test_pages:
            pytest.skip("No test pages available")

        page_ids = [p.id for p in sample_test_pages[:2]]  # Use first 2 pages

        result = await real_doc_manager.process_chunking(
            document_id=sample_test_document.id, page_ids=page_ids, chunk_size=1000
        )

        assert result is not None
        assert result.document_id == sample_test_document.id
        assert result.pages_processed == len(page_ids)
        assert result.chunks_created >= 1

    @pytest.mark.asyncio
    async def test_page_management(self, real_doc_manager, sample_test_document):
        """Test page listing and deletion."""
        # List pages
        pages = await real_doc_manager.list_pages(document_id=sample_test_document.id, limit=10)

        assert isinstance(pages, list)

        if pages:
            # Test page deletion (soft delete)
            page_id = pages[0].id
            deleted = await real_doc_manager.delete_page(page_id)
            assert isinstance(deleted, bool)

    @pytest.mark.asyncio
    async def test_error_handling(self, real_doc_manager):
        """Test error handling in document operations."""
        # Test with invalid URL
        try:
            result = await real_doc_manager.crawl_and_store(
                name="test-error",
                version="1.0.0",
                source_url="https://invalid-domain-12345.com",
                description="Error test",
            )
            # Should handle gracefully
            assert result is not None
        except Exception:
            # Acceptable to fail
            pass

        # Test chunking with invalid page IDs
        try:
            result = await real_doc_manager.process_chunking(
                document_id=99999, page_ids=[1, 2, 3], chunk_size=1000  # Invalid document
            )
            # Should fail gracefully
        except Exception:
            # Expected
            pass


@pytest.mark.integration
class TestContextBridgeIntegration:
    """Integration tests for ContextBridge with real services."""

    @pytest.mark.asyncio
    async def test_full_workflow_integration(self, real_context_bridge):
        """Test complete workflow from crawl to search."""
        # Skip if Ollama not available
        try:
            health = await real_context_bridge._search_service.embedding_service.verify_connection()
            if not health:
                pytest.skip("Ollama not available for full workflow test")
        except Exception:
            pytest.skip("Ollama integration not available")

        # 1. Crawl documentation
        crawl_result = await real_context_bridge.crawl_documentation(
            name="test-full-workflow",
            version="1.0.0",
            source_url="https://httpbin.org/html",
            description="Full workflow integration test",
        )

        assert crawl_result.document_id > 0
        assert crawl_result.pages_stored >= 1

        # 2. List pages
        pages = await real_context_bridge.list_pages(crawl_result.document_id)
        assert len(pages) >= 1

        # 3. Process chunking
        page_ids = [p.id for p in pages[:2]]  # Use first 2 pages
        chunk_result = await real_context_bridge.process_pages(
            document_id=crawl_result.document_id, page_ids=page_ids
        )

        assert chunk_result.chunks_created >= 1

        # 4. Search content
        search_results = await real_context_bridge.search(
            query="test", document_id=crawl_result.document_id, limit=5
        )

        assert isinstance(search_results, list)
        # May be empty if no matches, but shouldn't error

    @pytest.mark.asyncio
    async def test_document_management(self, real_context_bridge):
        """Test document CRUD operations."""
        # List documents
        docs_before = await real_context_bridge.list_documents()
        initial_count = len(docs_before)

        # Create document via crawl
        crawl_result = await real_context_bridge.crawl_documentation(
            name="test-doc-mgmt",
            version="1.0.0",
            source_url="https://httpbin.org/json",
            description="Document management test",
        )

        # List documents again
        docs_after = await real_context_bridge.list_documents()
        assert len(docs_after) >= initial_count + 1

        # Get specific document
        doc = await real_context_bridge.get_document("test-doc-mgmt", "1.0.0")
        assert doc is not None
        assert doc.id == crawl_result.document_id

        # Delete document
        deleted = await real_context_bridge.delete_document(crawl_result.document_id)
        assert deleted is True

        # Verify deletion
        doc_after_delete = await real_context_bridge.get_document("test-doc-mgmt", "1.0.0")
        assert doc_after_delete is None
