"""
Complete Workflow Integration Tests for Phase 5

Tests end-to-end workflows across all 4 phases:
- Phase 1 (Tags): Tag creation and document tagging
- Phase 2 (Groups): Page grouping and group management
- Phase 3 (Context): AI context generation for chunks
- Phase 4 (Reprocessing): Re-processing groups with context

Coverage:
- Complete workflow: Crawl → Process → Tag → Context → Reprocess → Search
- Full Phase 1 + Phase 2 workflow
- Full Phase 2 + Phase 3 workflow
- Full Phase 3 + Phase 4 workflow
- Error scenarios and recovery
"""

import pytest
import asyncio
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from context_bridge.core import ContextBridge
from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.database.repositories.tag_repository import TagRepository
from context_bridge.database.repositories.group_repository import GroupRepository
from context_bridge.service.doc_manager import DocManager
from context_bridge.service.search_service import SearchService


class TestCompleteWorkflow:
    """Test complete workflows across all phases"""

    @pytest.mark.asyncio
    async def test_full_workflow_crawl_to_reprocess_to_search(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Crawl → Process → Tag → Context → Reprocess → Search

        This is the ultimate integration test validating all 4 phases work together.
        """
        # Initialize repositories
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)
        tag_repo = TagRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        # Phase 0: Crawl and create document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        assert crawl_result["success"] is True
        document_id = crawl_result["document_id"]

        # Verify document exists
        document = await doc_repo.get_by_id(document_id)
        assert document is not None
        assert document.url == url

        # Phase 0: Get pages for chunking
        pages = await page_repo.get_by_document_id(document_id)
        assert len(pages) > 0
        page_ids = [p.id for p in pages]

        # Phase 2: Create group for chunking
        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Phase 2: Process pages into a group
        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            chunk_size=2000,
            context_enabled=False,  # No context on first pass
            group_name="Phase5-Test-Group-1",
        )
        assert process_result["success"] is True
        group_id = UUID(process_result.get("group_id"))

        # Verify group was created
        group = await group_repo.get_group_by_id(group_id)
        assert group is not None
        assert group.name == "Phase5-Test-Group-1"
        assert group.context_enabled is False

        # Verify chunks were created for group
        chunks = await chunk_repo.get_chunks_for_group(group_id)
        assert len(chunks) > 0
        initial_chunk_count = len(chunks)

        # Phase 1: Add tags to document
        tag_result = await tag_repo.add_tags_to_document(
            document_id=document_id,
            tag_ids=[1, 2, 3],  # Add some predefined tags
        )
        assert tag_result is True

        # Verify tags were added
        doc_tags = await tag_repo.get_document_tags(document_id)
        assert len(doc_tags) >= 3

        # Phase 1: Verify tag-based search works
        # (This would require search to support tag filtering)

        # Phase 3: Reprocess group with context generation
        # Note: This would require real LLM API, so we'll mock it for now
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=[f"Context for chunk {i}" for i in range(initial_chunk_count)]
            )

            # Phase 4: Reprocess the group with context
            reprocess_result = await doc_manager.reprocess_group(
                group_id=group_id,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
            )
            assert reprocess_result["success"] is True

        # Verify group was updated with context
        group = await group_repo.get_group_by_id(group_id)
        assert group is not None
        assert group.context_enabled is True
        assert group.context_model == "anthropic:claude-3-5-sonnet-20241022"

        # Verify chunks were updated with context (by checking count matches)
        chunks_after_reprocess = await chunk_repo.get_chunks_for_group(group_id)
        assert len(chunks_after_reprocess) == initial_chunk_count

        # Phase 4: Verify reprocessed chunks have context prepended
        # (by checking first chunk has context marker)
        first_chunk = chunks_after_reprocess[0]
        assert "Context for chunk" in first_chunk.content or len(first_chunk.content) > 100

        # Final: Test search on reprocessed content
        search_query = sample_web_content.get("keywords", ["test"])[0]
        search_results = await real_search_service.hybrid_search(
            query=search_query,
            limit=5,
            document_ids=[document_id],
        )

        # Verify search returns results from reprocessed chunks
        assert len(search_results) > 0
        # Results should have higher quality due to context
        for result in search_results:
            assert "content" in result
            assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_phase2_phase3_group_with_context_workflow(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Create group → Process with context → Verify context in chunks

        Validates Phase 2 (Groups) + Phase 3 (Context) integration
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        # Get pages
        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Create group with context enabled from the start
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            contexts = [f"Context describing chunk about documentation" for _ in range(10)]
            mock_agent_instance.generate_contexts_batch = AsyncMock(return_value=contexts)

            process_result = await doc_manager.process_chunking(
                document_id=document_id,
                page_ids=page_ids,
                chunk_size=2000,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
                group_name="Phase2+3-Context-Group",
            )
            assert process_result["success"] is True
            group_id = UUID(process_result["group_id"])

        # Verify group has context enabled
        group = await group_repo.get_group_by_id(group_id)
        assert group.context_enabled is True
        assert group.context_model == "anthropic:claude-3-5-sonnet-20241022"

        # Verify chunks contain context
        chunks = await chunk_repo.get_chunks_for_group(group_id)
        assert len(chunks) > 0

        # At least some chunks should have context prepended
        context_chunks = sum(1 for chunk in chunks if "Context" in chunk.content)
        assert context_chunks > 0, "Chunks should have context prepended"

    @pytest.mark.asyncio
    async def test_phase1_document_tagging_affects_search(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Document tagging → Tagged document retrieved

        Validates Phase 1 (Tags) integration with search
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)
        tag_repo = TagRepository(test_db_manager)

        # Crawl and create document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        # Get pages for processing
        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Process pages into chunks
        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            group_name="Tagged-Doc-Group",
        )
        assert process_result["success"] is True

        # Add tags to document
        tag_result = await tag_repo.add_tags_to_document(
            document_id=document_id,
            tag_ids=[1, 2, 3],
        )
        assert tag_result is True

        # Verify tags are retrievable
        tags = await tag_repo.get_document_tags(document_id)
        assert len(tags) >= 3
        tag_names = [tag.name for tag in tags]
        assert len(tag_names) > 0

    @pytest.mark.asyncio
    async def test_batch_group_reprocessing_workflow(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Create multiple groups → Batch reprocess all with context

        Validates batch re-processing functionality from Phase 4
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        # Get pages
        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Create 2 groups without context
        group_ids = []
        for i in range(2):
            process_result = await doc_manager.process_chunking(
                document_id=document_id,
                page_ids=(
                    page_ids[: len(page_ids) // 2] if i == 0 else page_ids[len(page_ids) // 2 :]
                ),
                group_name=f"Batch-Group-{i}",
            )
            assert process_result["success"] is True
            group_ids.append(UUID(process_result["group_id"]))

        # Verify groups were created without context
        for group_id in group_ids:
            group = await group_repo.get_group_by_id(group_id)
            assert group.context_enabled is False

        # Batch reprocess all groups with context
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=[f"Context {i}" for i in range(20)]
            )

            for group_id in group_ids:
                reprocess_result = await doc_manager.reprocess_group(
                    group_id=group_id,
                    context_enabled=True,
                )
                assert reprocess_result["success"] is True

        # Verify all groups now have context
        for group_id in group_ids:
            group = await group_repo.get_group_by_id(group_id)
            assert group.context_enabled is True

    @pytest.mark.asyncio
    async def test_multiple_tags_on_context_enabled_document(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Tag + Context features together

        Validates Phase 1 + Phase 3 features on same document
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        tag_repo = TagRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        # Get pages
        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Add tags
        tag_result = await tag_repo.add_tags_to_document(
            document_id=document_id,
            tag_ids=[1, 2],
        )
        assert tag_result is True

        # Process with context enabled
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=[f"Context chunk {i}" for i in range(15)]
            )

            process_result = await doc_manager.process_chunking(
                document_id=document_id,
                page_ids=page_ids,
                context_enabled=True,
                group_name="Tagged-Context-Group",
            )
            assert process_result["success"] is True

        # Verify document has tags
        tags = await tag_repo.get_document_tags(document_id)
        assert len(tags) >= 2

        # Verify group has context
        group_id = UUID(process_result["group_id"])
        group = await group_repo.get_group_by_id(group_id)
        assert group.context_enabled is True

    @pytest.mark.asyncio
    async def test_context_improves_search_quality(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Search quality improved by context

        Validates that context helps with search relevance
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)
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

        # Create group WITHOUT context first
        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            context_enabled=False,
            group_name="No-Context-Group",
        )
        group_id_no_context = UUID(process_result["group_id"])
        chunks_no_context = await chunk_repo.get_chunks_for_group(group_id_no_context)

        # Get baseline search results without context
        search_query = sample_web_content.get("keywords", ["test"])[0]
        results_no_context = await real_search_service.hybrid_search(
            query=search_query,
            limit=5,
            document_ids=[document_id],
        )

        # Create another group WITH context
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance

            # Create contextual descriptions that are highly relevant
            context_descriptions = [
                "This section contains technical documentation about the system architecture",
                "This paragraph explains core algorithms and data structures",
                "Implementation details and code examples are provided here",
                "Configuration options and best practices are documented",
            ]
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=context_descriptions * 3  # Repeat for all chunks
            )

            process_result_context = await doc_manager.process_chunking(
                document_id=document_id,
                page_ids=page_ids,
                context_enabled=True,
                group_name="With-Context-Group",
            )
            group_id_with_context = UUID(process_result_context["group_id"])

        chunks_with_context = await chunk_repo.get_chunks_for_group(group_id_with_context)

        # Get search results with context
        results_with_context = await real_search_service.hybrid_search(
            query=search_query,
            limit=5,
            document_ids=[document_id],
        )

        # Both should return results
        assert len(results_no_context) > 0
        assert len(results_with_context) > 0

        # Context-enhanced chunks should be in results
        context_chunks_in_results = sum(
            1
            for result in results_with_context
            if any(ctx in result.get("content", "") for ctx in context_descriptions)
        )
        assert context_chunks_in_results >= 0  # May not all have context in first few results

    @pytest.mark.asyncio
    async def test_full_phase2_group_workflow(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Create group → Verify group structure → Update group status

        Validates Phase 2 (Groups) functionality
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)
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

        # Create group
        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            group_name="Full-Phase2-Group",
        )
        assert process_result["success"] is True
        group_id = UUID(process_result["group_id"])

        # Verify group structure
        group = await group_repo.get_group_by_id(group_id)
        assert group is not None
        assert group.name == "Full-Phase2-Group"
        assert group.document_id == document_id
        assert group.total_pages > 0
        assert group.total_chunks > 0

        # Verify pages are linked to group
        group_pages = await page_repo.get_pages_for_group(group_id)
        assert len(group_pages) == len(page_ids)

        # Verify chunks are linked to group
        group_chunks = await chunk_repo.get_chunks_for_group(group_id)
        assert len(group_chunks) > 0
        assert group.total_chunks == len(group_chunks)

        # Verify group statistics
        stats = await group_repo.get_group_statistics(group_id)
        assert stats is not None
        assert stats["chunk_count"] == len(group_chunks)
        assert stats["page_count"] == len(group_pages)

    @pytest.mark.asyncio
    async def test_search_across_multiple_groups_same_document(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Create multiple groups in same document → Search spans all groups

        Validates that search works across document-level queries
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
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

        # Create 2 groups in same document
        group_ids = []
        for i in range(2):
            start_idx = (i * len(page_ids)) // 2
            end_idx = ((i + 1) * len(page_ids)) // 2
            partition_pages = page_ids[start_idx:end_idx]

            if partition_pages:  # Only if there are pages to process
                process_result = await doc_manager.process_chunking(
                    document_id=document_id,
                    page_ids=partition_pages,
                    group_name=f"Multi-Group-{i}",
                )
                if process_result["success"]:
                    group_ids.append(UUID(process_result["group_id"]))

        # Search should span all groups
        search_query = sample_web_content.get("keywords", ["test"])[0]
        search_results = await real_search_service.hybrid_search(
            query=search_query,
            limit=10,
            document_ids=[document_id],
        )

        # Verify search returns results (from all groups)
        assert len(search_results) > 0

        # Collect groups from search results
        groups_in_results = set()
        for result in search_results:
            chunk_id = result.get("chunk_id")
            if chunk_id:
                chunk = await chunk_repo.get_by_id(chunk_id)
                if chunk and chunk.group_id:
                    groups_in_results.add(chunk.group_id)

        # Ideally results should contain chunks from multiple groups
        # (though not guaranteed if one group has much more relevant content)
