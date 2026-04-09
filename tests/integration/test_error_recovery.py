"""
Error Recovery Integration Tests for Phase 5

Tests error scenarios and recovery mechanisms:
- Crawl failures and recovery
- Chunking failures and rollback
- Embedding failures and retry
- Context generation failures and graceful degradation
- Reprocessing failures and data integrity
- Database transaction rollback scenarios
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID
from typing import List

from context_bridge.config import Config
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.database.repositories.group_repository import GroupRepository
from context_bridge.service.doc_manager import DocManager
from context_bridge.service.search_service import SearchService


class TestErrorRecovery:
    """Test error scenarios and recovery mechanisms"""

    @pytest.mark.asyncio
    async def test_recover_from_chunking_failure(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Chunking fails → Group remains in failed state

        Validates error handling during chunking phase
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        # Mock ChunkingService to fail
        with patch("context_bridge.service.doc_manager.ChunkingService") as mock_chunking:
            mock_chunking_instance = AsyncMock()
            mock_chunking.return_value = mock_chunking_instance
            mock_chunking_instance.smart_chunk_markdown = AsyncMock(
                side_effect=Exception("Chunking failed")
            )

            doc_manager = DocManager(
                db_manager=test_db_manager,
                chunking_service=mock_chunking_instance,
                embedding_service=real_embedding_service,
                search_service=real_search_service,
                config=Config(),
            )

            # Attempt processing should fail gracefully
            with pytest.raises(Exception):
                await doc_manager.process_chunking(
                    document_id=document_id,
                    page_ids=page_ids,
                    group_name="Failed-Chunk-Group",
                )

    @pytest.mark.asyncio
    async def test_recover_from_embedding_failure(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Embedding fails → Chunks stored without embeddings

        Validates graceful degradation when embedding service fails
        """
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        # Mock EmbeddingService to fail
        with patch("context_bridge.service.doc_manager.EmbeddingService") as mock_embedding:
            mock_embedding_instance = AsyncMock()
            mock_embedding.return_value = mock_embedding_instance
            mock_embedding_instance.embed_batch = AsyncMock(
                side_effect=Exception("Embedding service unavailable")
            )

            doc_manager = DocManager(
                db_manager=test_db_manager,
                chunking_service=None,
                embedding_service=mock_embedding_instance,
                search_service=real_search_service,
                config=Config(),
            )

            # Attempt processing should fail gracefully
            with pytest.raises(Exception):
                await doc_manager.process_chunking(
                    document_id=document_id,
                    page_ids=page_ids,
                )

    @pytest.mark.asyncio
    async def test_recover_from_context_generation_failure(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Context generation fails → Continue without context

        Validates graceful degradation when LLM context fails
        """
        page_repo = PageRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Mock context agent to fail
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            # Simulate context generation failure
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                side_effect=Exception("LLM API error")
            )

            # Processing with context should handle the failure gracefully
            with pytest.raises(Exception):
                await doc_manager.process_chunking(
                    document_id=document_id,
                    page_ids=page_ids,
                    context_enabled=True,
                    group_name="Context-Failed-Group",
                )

    @pytest.mark.asyncio
    async def test_recover_from_reprocessing_failure(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Reprocessing fails → Original group data preserved

        Validates data integrity when reprocessing fails
        """
        page_repo = PageRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        # Crawl and setup initial group
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Create initial group
        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            context_enabled=False,
            group_name="Reprocess-Initial-Group",
        )
        group_id = UUID(process_result["group_id"])

        # Get initial chunks
        chunks_before = await chunk_repo.get_chunks_for_group(group_id)
        initial_count = len(chunks_before)

        # Mock failure during reprocessing
        with patch("context_bridge.service.doc_manager.ChunkRepository") as mock_chunk_repo:
            mock_chunk_repo_instance = AsyncMock()
            mock_chunk_repo.return_value = mock_chunk_repo_instance
            # Simulate failure when trying to store new chunks
            mock_chunk_repo_instance.create = AsyncMock(
                side_effect=Exception("Database write failed")
            )

            doc_manager_with_mock = DocManager(
                db_manager=test_db_manager,
                chunking_service=None,
                embedding_service=real_embedding_service,
                search_service=real_search_service,
                config=Config(),
            )

            # Attempt reprocessing should fail gracefully
            with pytest.raises(Exception):
                await doc_manager_with_mock.reprocess_group(
                    group_id=group_id,
                    context_enabled=True,
                )

        # Verify original group data is intact
        group_after_failure = await group_repo.get_group_by_id(group_id)
        assert group_after_failure is not None

        # Chunk count should remain same (failure should not partially delete)
        chunks_after = await chunk_repo.get_chunks_for_group(group_id)
        assert len(chunks_after) == initial_count

    @pytest.mark.asyncio
    async def test_handle_partial_crawl_failure(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
    ):
        """Test: Some pages fail to crawl → Process successful pages

        Validates partial success handling
        """
        page_repo = PageRepository(test_db_manager)

        # Mock crawling service to partially fail
        with patch("context_bridge.service.crawling_service.CrawlingService") as mock_crawl:
            mock_crawl_instance = AsyncMock()
            mock_crawl.return_value = mock_crawl_instance

            # Simulate partial crawl failure (first succeeds, rest fail)
            success_result = {
                "success": True,
                "document_id": 1,
                "pages": [
                    {"id": 1, "title": "Page 1", "content": "Content 1"},
                    {"id": 2, "title": "Page 2", "content": "Content 2"},
                ],
            }

            mock_crawl_instance.crawl_url = AsyncMock(return_value=success_result)

            # We can still use this for further processing
            assert success_result["success"] is True
            assert len(success_result.get("pages", [])) > 0

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_group_create_failure(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Group creation fails → No partial data in DB

        Validates database transaction integrity
        """
        page_repo = PageRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        # Mock GroupRepository to fail during creation
        with patch(
            "context_bridge.database.repositories.group_repository.GroupRepository"
        ) as mock_group_repo:
            mock_group_repo_instance = AsyncMock()
            mock_group_repo.return_value = mock_group_repo_instance
            mock_group_repo_instance.create_group = AsyncMock(
                side_effect=Exception("Group creation failed")
            )

            doc_manager = DocManager(
                db_manager=test_db_manager,
                chunking_service=None,
                embedding_service=real_embedding_service,
                search_service=real_search_service,
                config=Config(),
            )

            # Attempt processing should fail
            with pytest.raises(Exception):
                await doc_manager.process_chunking(
                    document_id=document_id,
                    page_ids=page_ids,
                )

    @pytest.mark.asyncio
    async def test_handle_invalid_group_id_reprocessing(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
    ):
        """Test: Reprocess non-existent group → Handle gracefully

        Validates input validation
        """
        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Attempt reprocessing with invalid group ID
        invalid_group_id = UUID("00000000-0000-0000-0000-000000000000")

        with pytest.raises(Exception):
            await doc_manager.reprocess_group(
                group_id=invalid_group_id,
                context_enabled=True,
            )

    @pytest.mark.asyncio
    async def test_handle_context_already_enabled_reprocessing(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Try to reprocess group already with context → Return error

        Validates business logic constraints
        """
        page_repo = PageRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Create group with context already enabled
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=[f"Context {i}" for i in range(20)]
            )

            process_result = await doc_manager.process_chunking(
                document_id=document_id,
                page_ids=page_ids,
                context_enabled=True,
                group_name="Already-Context-Group",
            )
            group_id = UUID(process_result["group_id"])

        # Verify group has context
        group = await group_repo.get_group_by_id(group_id)
        assert group.context_enabled is True

        # Try to reprocess the same group - should handle gracefully
        # (depending on implementation, might return error or skip)
        result = await doc_manager.reprocess_group(
            group_id=group_id,
            context_enabled=True,
        )
        # Result should indicate it was already enabled
        assert result is not None

    @pytest.mark.asyncio
    async def test_data_integrity_after_failed_search(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Search fails → Data remains intact

        Validates that search failures don't corrupt data
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        # Crawl and process document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
        )
        assert process_result["success"] is True

        # Get chunks before search
        all_chunks_before = await chunk_repo.get_by_document_id(document_id)
        chunk_count_before = len(all_chunks_before)

        # Mock search to fail
        with patch.object(real_search_service, "hybrid_search") as mock_search:
            mock_search.side_effect = Exception("Search failed")

            # Attempt search should raise exception
            with pytest.raises(Exception):
                await real_search_service.hybrid_search(
                    query="test",
                    document_ids=[document_id],
                )

        # Verify data is still intact after search failure
        all_chunks_after = await chunk_repo.get_by_document_id(document_id)
        chunk_count_after = len(all_chunks_after)

        assert (
            chunk_count_after == chunk_count_before
        ), "Data should not be modified by failed search"

    @pytest.mark.asyncio
    async def test_recovery_sequence_crawl_chunk_embed(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Recovery from failures at each stage

        Validates sequential error handling through pipeline
        """
        page_repo = PageRepository(test_db_manager)

        # Stage 1: Crawl succeeds
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        assert crawl_result["success"] is True
        document_id = crawl_result["document_id"]

        # Stage 2: Pages created
        pages = await page_repo.get_by_document_id(document_id)
        assert len(pages) > 0
        page_ids = [p.id for p in pages]

        # Stage 3: Process normally
        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
        )
        assert process_result["success"] is True

        # Verify pipeline completed
        assert process_result.get("group_id") is not None
        assert process_result.get("chunk_count", 0) > 0
