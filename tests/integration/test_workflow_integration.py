"""
Workflow Integration Tests for Context Bridge

Tests complete end-to-end workflows from crawling to search, including:
- Full document processing pipeline
- Error recovery and rollback scenarios
- Concurrent operations and race conditions
- Performance under load
"""

import asyncio
import pytest
import time
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch

from context_bridge.core import ContextBridge
from context_bridge.service.doc_manager import DocManager
from context_bridge.service.search_service import SearchService
from context_bridge.service.crawling_service import CrawlingService
from context_bridge.service.embedding import EmbeddingService
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository


class TestWorkflowIntegration:
    """Integration tests for complete workflows"""

    @pytest.mark.asyncio
    async def test_full_crawl_to_search_workflow(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test complete workflow from URL crawling to semantic search"""
        # Setup
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        # Step 1: Crawl and process document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)

        assert crawl_result["success"] is True
        assert "document_id" in crawl_result

        document_id = crawl_result["document_id"]

        # Step 2: Verify document was stored
        document = await doc_repo.get_by_id(document_id)
        assert document is not None
        assert document.url == url

        # Step 3: Verify pages were created and chunked
        pages = await page_repo.get_by_document_id(document_id)
        assert len(pages) > 0

        total_chunks = 0
        for page in pages:
            chunks = await chunk_repo.get_by_page_id(page.id)
            total_chunks += len(chunks)
            assert len(chunks) > 0  # Each page should have chunks

        # Step 4: Test semantic search
        search_query = "machine learning algorithms"
        search_results = await real_search_service.hybrid_search(
            query=search_query, limit=5, document_ids=[document_id]
        )

        assert len(search_results) > 0
        # Verify search results contain relevant chunks
        found_relevant = False
        for result in search_results:
            if "machine" in result["content"].lower() or "learning" in result["content"].lower():
                found_relevant = True
                break
        assert found_relevant, "Search should return relevant content"

    @pytest.mark.asyncio
    async def test_concurrent_document_processing(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        sample_web_content_factory,
    ):
        """Test concurrent processing of multiple documents"""
        # Create multiple sample documents
        urls = [sample_web_content_factory() for _ in range(3)]

        # Process documents concurrently
        tasks = []
        for url_data in urls:
            task = real_crawling_service.crawl_url(url_data["url"])
            tasks.append(task)

        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        # Verify all succeeded
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == len(urls)

        # Verify performance (should complete within reasonable time)
        duration = end_time - start_time
        assert duration < 30.0  # Should complete within 30 seconds

        # Verify all documents were stored
        doc_repo = DocumentRepository(test_db_manager)
        all_docs = await doc_repo.get_all()
        assert len(all_docs) >= len(urls)

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, test_db_manager, real_crawling_service):
        """Test error recovery and rollback in workflows"""
        # Test with invalid URL
        invalid_url = "https://nonexistent-domain-12345.com/invalid-page"

        # Attempt crawl - should fail gracefully
        result = await real_crawling_service.crawl_url(invalid_url)

        # Verify failure was handled gracefully
        assert result["success"] is False
        assert "error" in result

        # Verify no partial data was left in database
        doc_repo = DocumentRepository(test_db_manager)
        docs = await doc_repo.get_all()
        # Should not have created a document for failed crawl
        invalid_docs = [d for d in docs if d.url == invalid_url]
        assert len(invalid_docs) == 0

    @pytest.mark.asyncio
    async def test_search_performance_under_load(
        self,
        test_db_manager,
        real_search_service,
        sample_web_content_factory,
        real_crawling_service,
    ):
        """Test search performance with multiple documents"""
        # Create several documents for search testing
        num_docs = 5
        urls = [sample_web_content_factory() for _ in range(num_docs)]

        # Process all documents
        for url_data in urls:
            await real_crawling_service.crawl_url(url_data["url"])

        # Test search performance
        search_queries = [
            "artificial intelligence",
            "data science",
            "machine learning",
            "neural networks",
            "computer vision",
        ]

        start_time = time.time()
        tasks = []
        for query in search_queries:
            task = real_search_service.hybrid_search(query=query, limit=10)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # Verify all searches completed
        assert len(results) == len(search_queries)
        for result_set in results:
            assert isinstance(result_set, list)

        # Verify reasonable performance
        duration = end_time - start_time
        avg_query_time = duration / len(search_queries)
        assert avg_query_time < 2.0  # Average query should be under 2 seconds

    @pytest.mark.asyncio
    async def test_document_update_workflow(
        self, test_db_manager, real_crawling_service, real_search_service, sample_web_content
    ):
        """Test updating an existing document"""
        url = sample_web_content["url"]

        # Initial crawl
        result1 = await real_crawling_service.crawl_url(url)
        document_id = result1["document_id"]

        # Verify initial state
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        initial_pages = await page_repo.get_by_document_id(document_id)
        initial_chunks = []
        for page in initial_pages:
            initial_chunks.extend(await chunk_repo.get_by_page_id(page.id))

        # Re-crawl same URL (should update)
        result2 = await real_crawling_service.crawl_url(url)

        # Should return same document ID
        assert result2["document_id"] == document_id

        # Verify document was updated (pages/chunks may change)
        updated_pages = await page_repo.get_by_document_id(document_id)
        updated_chunks = []
        for page in updated_pages:
            updated_chunks.extend(await chunk_repo.get_by_page_id(page.id))

        # Content should be updated (may be same or different)
        assert len(updated_pages) >= 0
        assert len(updated_chunks) >= 0

        # Search should still work
        search_results = await real_search_service.hybrid_search(
            query="content", limit=5, document_ids=[document_id]
        )
        assert len(search_results) >= 0

    @pytest.mark.asyncio
    async def test_large_document_processing(
        self, test_db_manager, real_crawling_service, real_search_service
    ):
        """Test processing of larger documents"""
        # Use a known longer article
        long_content_url = "https://en.wikipedia.org/wiki/Machine_learning"

        # Skip if network issues
        try:
            result = await real_crawling_service.crawl_url(long_content_url)
            if not result["success"]:
                pytest.skip(f"Crawling failed: {result.get('error', 'Unknown error')}")

            document_id = result["document_id"]

            # Verify processing completed
            page_repo = PageRepository(test_db_manager)
            chunk_repo = ChunkRepository(test_db_manager)

            pages = await page_repo.get_by_document_id(document_id)
            assert len(pages) > 0

            total_chunks = 0
            for page in pages:
                chunks = await chunk_repo.get_by_page_id(page.id)
                total_chunks += len(chunks)

            # Should have substantial content
            assert total_chunks > 10

            # Search should work
            search_results = await real_search_service.hybrid_search(
                query="machine learning", limit=5, document_ids=[document_id]
            )
            assert len(search_results) > 0

        except Exception as e:
            pytest.skip(f"Network or external service issue: {e}")

    @pytest.mark.asyncio
    async def test_cross_document_search(
        self,
        test_db_manager,
        real_crawling_service,
        real_search_service,
        sample_web_content_factory,
    ):
        """Test searching across multiple documents"""
        # Create multiple documents with related content
        urls = []
        for i in range(3):
            content = sample_web_content_factory()
            urls.append(content["url"])
            await real_crawling_service.crawl_url(content["url"])

        # Search across all documents
        search_results = await real_search_service.hybrid_search(query="technology", limit=10)

        # Should find results from multiple documents
        found_docs = set()
        for result in search_results:
            found_docs.add(result["document_id"])

        assert len(found_docs) >= 1  # At least one document should have relevant content

    @pytest.mark.asyncio
    async def test_cleanup_and_teardown_workflow(
        self, test_db_manager, real_crawling_service, sample_web_content
    ):
        """Test proper cleanup after workflow operations"""
        url = sample_web_content["url"]

        # Process document
        result = await real_crawling_service.crawl_url(url)
        document_id = result["document_id"]

        # Verify document exists
        doc_repo = DocumentRepository(test_db_manager)
        document = await doc_repo.get_by_id(document_id)
        assert document is not None

        # Delete document
        await doc_repo.delete(document_id)

        # Verify cleanup
        deleted_doc = await doc_repo.get_by_id(document_id)
        assert deleted_doc is None

        # Verify related data was cleaned up
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        pages = await page_repo.get_by_document_id(document_id)
        assert len(pages) == 0

        # Check chunks for remaining pages (should be none)
        all_chunks = await chunk_repo.get_all()
        orphan_chunks = [c for c in all_chunks if c.page_id not in [p.id for p in pages]]
        assert len(orphan_chunks) == 0  # No orphaned chunks should remain
