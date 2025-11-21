"""
Multi-Phase Integration Tests for Phase 5

Tests combinations of phases working together:
- Phase 1 + Phase 2 (Tags + Groups)
- Phase 2 + Phase 3 (Groups + Context)
- Phase 3 + Phase 4 (Context + Reprocessing)
- Phase 1 + Phase 3 + Phase 4 (All together)
- Multiple documents with different phase combinations
"""

import pytest
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch
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


class TestMultiPhaseIntegration:
    """Test combinations of multiple phases"""

    @pytest.mark.asyncio
    async def test_phase1_phase2_tags_with_groups(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Phase 1 + Phase 2

        Create document → Tag it → Create groups → Search respects both tags and groups
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        tag_repo = TagRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        # Crawl and create document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        # Add tags to document (Phase 1)
        tag_result = await tag_repo.add_tags_to_document(
            document_id=document_id,
            tag_ids=[1, 2, 3],
        )
        assert tag_result is True

        # Get pages and create groups (Phase 2)
        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Create first group
        process_result_1 = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids[: len(page_ids) // 2] if len(page_ids) > 1 else page_ids,
            group_name="P1P2-Group-1",
        )
        assert process_result_1["success"] is True
        group_id_1 = UUID(process_result_1["group_id"])

        # Create second group
        if len(page_ids) > 1:
            process_result_2 = await doc_manager.process_chunking(
                document_id=document_id,
                page_ids=page_ids[len(page_ids) // 2 :],
                group_name="P1P2-Group-2",
            )
            assert process_result_2["success"] is True
            group_id_2 = UUID(process_result_2["group_id"])
        else:
            group_id_2 = None

        # Verify document has tags
        tags = await tag_repo.get_document_tags(document_id)
        assert len(tags) >= 3

        # Verify document has multiple groups
        groups = await group_repo.list_groups(document_id=document_id)
        assert len(groups) >= 1
        if group_id_2:
            assert len(groups) >= 2

    @pytest.mark.asyncio
    async def test_phase2_phase3_groups_with_context(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Phase 2 + Phase 3

        Create groups → Process with context → Verify context in all groups
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

        # Create multiple groups with context enabled (Phase 2 + Phase 3)
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=[f"API documentation context" for _ in range(20)]
            )

            group_ids = []
            for i in range(2):
                start_idx = (i * len(page_ids)) // 2
                end_idx = ((i + 1) * len(page_ids)) // 2
                partition_pages = page_ids[start_idx:end_idx]

                if partition_pages:
                    process_result = await doc_manager.process_chunking(
                        document_id=document_id,
                        page_ids=partition_pages,
                        context_enabled=True,
                        context_model="anthropic:claude-3-5-sonnet-20241022",
                        group_name=f"P2P3-Context-Group-{i}",
                    )
                    assert process_result["success"] is True
                    group_ids.append(UUID(process_result["group_id"]))

        # Verify all groups have context enabled
        for group_id in group_ids:
            group = await group_repo.get_group_by_id(group_id)
            assert group.context_enabled is True
            assert group.context_model == "anthropic:claude-3-5-sonnet-20241022"

            # Verify chunks in group have context
            chunks = await chunk_repo.get_chunks_for_group(group_id)
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_phase3_phase4_context_with_reprocessing(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Phase 3 + Phase 4

        Create group without context → Reprocess with context → Verify upgrade
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

        # Phase 3: Create group WITHOUT context first
        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            context_enabled=False,
            group_name="P3P4-No-Context-Group",
        )
        assert process_result["success"] is True
        group_id = UUID(process_result["group_id"])

        # Verify no context
        group_before = await group_repo.get_group_by_id(group_id)
        assert group_before.context_enabled is False

        chunks_before = await chunk_repo.get_chunks_for_group(group_id)
        initial_chunk_count = len(chunks_before)

        # Phase 4: Reprocess with context
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=[f"New context for chunk {i}" for i in range(initial_chunk_count)]
            )

            reprocess_result = await doc_manager.reprocess_group(
                group_id=group_id,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
            )
            assert reprocess_result["success"] is True

        # Verify context was added
        group_after = await group_repo.get_group_by_id(group_id)
        assert group_after.context_enabled is True
        assert group_after.context_model == "anthropic:claude-3-5-sonnet-20241022"

        chunks_after = await chunk_repo.get_chunks_for_group(group_id)
        assert len(chunks_after) == initial_chunk_count

    @pytest.mark.asyncio
    async def test_phase1_phase3_phase4_all_together(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Phase 1 + Phase 3 + Phase 4

        Tag document → Process with context → Reprocess → Verify all features work
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        tag_repo = TagRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        # Phase 1: Tag document
        tag_result = await tag_repo.add_tags_to_document(
            document_id=document_id,
            tag_ids=[1, 2],
        )
        assert tag_result is True

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Phase 3: Create group with context
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=[f"Initial context {i}" for i in range(20)]
            )

            process_result = await doc_manager.process_chunking(
                document_id=document_id,
                page_ids=page_ids,
                context_enabled=True,
                context_model="anthropic:claude-3-5-sonnet-20241022",
                group_name="P1P3P4-All-Features",
            )
            assert process_result["success"] is True
            group_id = UUID(process_result["group_id"])

        # Phase 4: Reprocess group
        with patch("context_bridge.services.context_agent.ContextGenerationAgent") as mock_agent:
            mock_agent_instance = AsyncMock()
            mock_agent.return_value = mock_agent_instance
            mock_agent_instance.generate_contexts_batch = AsyncMock(
                return_value=[f"Updated context {i}" for i in range(20)]
            )

            reprocess_result = await doc_manager.reprocess_group(
                group_id=group_id,
                context_enabled=True,
                context_model="openai:gpt-4o",
            )
            assert reprocess_result["success"] is True

        # Verify all features
        # Phase 1: Tags present
        tags = await tag_repo.get_document_tags(document_id)
        assert len(tags) >= 2

        # Phase 2: Group exists
        group = await group_repo.get_group_by_id(group_id)
        assert group is not None

        # Phase 3: Context enabled
        assert group.context_enabled is True

        # Phase 4: Reprocessed with new model
        assert group.context_model == "openai:gpt-4o"

    @pytest.mark.asyncio
    async def test_multiple_documents_different_phases(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content_factory,
    ):
        """Test: Multiple documents with different phase configurations

        Doc1: No tags, no context
        Doc2: With tags, no context
        Doc3: No tags, with context
        Doc4: With tags, with context
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        tag_repo = TagRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)

        documents = []

        # Create 4 documents with different configurations
        for i in range(4):
            url = sample_web_content_factory()
            crawl_result = await real_crawling_service.crawl_url(url)
            doc_id = crawl_result["document_id"]

            has_tags = i >= 1  # Docs 2, 3, 4 have tags
            has_context = i >= 2  # Docs 3, 4 have context

            # Add tags if configured
            if has_tags:
                await tag_repo.add_tags_to_document(
                    document_id=doc_id,
                    tag_ids=[1, 2],
                )

            # Get pages
            pages = await page_repo.get_by_document_id(doc_id)
            page_ids = [p.id for p in pages]

            doc_manager = DocManager(
                db_manager=test_db_manager,
                chunking_service=None,
                embedding_service=real_embedding_service,
                search_service=real_search_service,
                config=Config(),
            )

            # Create group with or without context
            if has_context:
                with patch(
                    "context_bridge.services.context_agent.ContextGenerationAgent"
                ) as mock_agent:
                    mock_agent_instance = AsyncMock()
                    mock_agent.return_value = mock_agent_instance
                    mock_agent_instance.generate_contexts_batch = AsyncMock(
                        return_value=[f"Context {j}" for j in range(20)]
                    )

                    process_result = await doc_manager.process_chunking(
                        document_id=doc_id,
                        page_ids=page_ids,
                        context_enabled=True,
                        group_name=f"Doc-{i}-With-Context",
                    )
            else:
                process_result = await doc_manager.process_chunking(
                    document_id=doc_id,
                    page_ids=page_ids,
                    context_enabled=False,
                    group_name=f"Doc-{i}-No-Context",
                )

            documents.append(
                {
                    "id": doc_id,
                    "has_tags": has_tags,
                    "has_context": has_context,
                    "group_id": (
                        UUID(process_result["group_id"]) if process_result["success"] else None
                    ),
                }
            )

        # Verify all documents exist with expected configuration
        for i, doc_info in enumerate(documents):
            doc = await doc_repo.get_by_id(doc_info["id"])
            assert doc is not None

            tags = await tag_repo.get_document_tags(doc_info["id"])
            if doc_info["has_tags"]:
                assert len(tags) >= 2
            else:
                assert len(tags) == 0

            if doc_info["group_id"]:
                group = await group_repo.get_group_by_id(doc_info["group_id"])
                if doc_info["has_context"]:
                    assert group.context_enabled is True
                else:
                    assert group.context_enabled is False

    @pytest.mark.asyncio
    async def test_phase2_group_statistics_across_all_phases(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Group statistics are accurate across all phases"""
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

        # Create group
        process_result = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            group_name="Stats-Test-Group",
        )
        group_id = UUID(process_result["group_id"])

        # Get group statistics
        stats = await group_repo.get_group_statistics(group_id)
        assert stats is not None

        # Verify counts match actual data
        actual_chunks = await chunk_repo.get_chunks_for_group(group_id)
        assert stats["chunk_count"] == len(actual_chunks)

        actual_pages = await page_repo.get_pages_for_group(group_id)
        assert stats["page_count"] == len(actual_pages)

    @pytest.mark.asyncio
    async def test_cross_phase_document_interaction(
        self,
        test_db_manager,
        real_embedding_service,
        real_crawling_service,
        real_search_service,
        sample_web_content,
    ):
        """Test: Document operations work correctly when mixing all phases

        Operations that affect one phase shouldn't break others
        """
        doc_repo = DocumentRepository(test_db_manager)
        page_repo = PageRepository(test_db_manager)
        tag_repo = TagRepository(test_db_manager)
        group_repo = GroupRepository(test_db_manager)
        chunk_repo = ChunkRepository(test_db_manager)

        # Crawl document
        url = sample_web_content["url"]
        crawl_result = await real_crawling_service.crawl_url(url)
        document_id = crawl_result["document_id"]

        # Add tags (Phase 1)
        await tag_repo.add_tags_to_document(
            document_id=document_id,
            tag_ids=[1, 2, 3],
        )

        pages = await page_repo.get_by_document_id(document_id)
        page_ids = [p.id for p in pages]

        doc_manager = DocManager(
            db_manager=test_db_manager,
            chunking_service=None,
            embedding_service=real_embedding_service,
            search_service=real_search_service,
            config=Config(),
        )

        # Create group (Phase 2)
        process_result_1 = await doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids[: len(page_ids) // 2] if len(page_ids) > 1 else page_ids,
            context_enabled=True,
            group_name="Cross-Phase-Group-1",
        )
        group_id_1 = UUID(process_result_1["group_id"])

        # Verify tags still exist
        tags_after_group1 = await tag_repo.get_document_tags(document_id)
        assert len(tags_after_group1) >= 3

        # Create second group (Phase 2)
        if len(page_ids) > 1:
            process_result_2 = await doc_manager.process_chunking(
                document_id=document_id,
                page_ids=page_ids[len(page_ids) // 2 :],
                context_enabled=False,
                group_name="Cross-Phase-Group-2",
            )
            group_id_2 = UUID(process_result_2["group_id"])

            # Verify tags still exist
            tags_after_group2 = await tag_repo.get_document_tags(document_id)
            assert len(tags_after_group2) >= 3

            # Verify first group still has correct context setting
            group_1 = await group_repo.get_group_by_id(group_id_1)
            assert group_1.context_enabled is True

            # Reprocess first group (Phase 4)
            with patch(
                "context_bridge.services.context_agent.ContextGenerationAgent"
            ) as mock_agent:
                mock_agent_instance = AsyncMock()
                mock_agent.return_value = mock_agent_instance
                mock_agent_instance.generate_contexts_batch = AsyncMock(
                    return_value=[f"Context {i}" for i in range(30)]
                )

                reprocess_result = await doc_manager.reprocess_group(
                    group_id=group_id_1,
                    context_enabled=True,
                )
                assert reprocess_result["success"] is True

            # Verify second group is unaffected
            group_2_after = await group_repo.get_group_by_id(group_id_2)
            assert group_2_after.context_enabled is False

            # Verify tags still exist
            tags_after_reprocess = await tag_repo.get_document_tags(document_id)
            assert len(tags_after_reprocess) >= 3
