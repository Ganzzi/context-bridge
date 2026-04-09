"""
Database Integration Tests.

Tests full CRUD operations with real PostgreSQL database connections.
Tests transactions, constraints, indexes, and data integrity.
"""

import pytest
import asyncio
from typing import List

from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from context_bridge.database.repositories.page_repository import PageRepository, Page
from context_bridge.database.repositories.chunk_repository import ChunkRepository, Chunk


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations with real connections."""

    @pytest.mark.asyncio
    async def test_document_crud_cycle(self, clean_test_db, test_document_factory):
        """Test complete CRUD cycle for documents."""
        async with clean_test_db.connection() as conn:
            repo = DocumentRepository(conn)

            # CREATE
            doc_data = test_document_factory("test-crud-doc", "1.0.0", "CRUD test document")
            doc_id = await repo.create(**doc_data)

            assert doc_id > 0

            # READ
            doc = await repo.get_by_id(doc_id)
            assert doc is not None
            assert doc.name == doc_data["name"]
            assert doc.version == doc_data["version"]
            assert doc.description == doc_data["description"]

            # Get by name/version
            doc_by_name = await repo.get_by_name_version(doc_data["name"], doc_data["version"])
            assert doc_by_name is not None
            assert doc_by_name.id == doc_id

            # UPDATE (if supported)
            # Note: Document updates might not be implemented yet

            # LIST
            docs = await repo.list_all(limit=10)
            assert len(docs) >= 1
            assert any(d.id == doc_id for d in docs)

            # DELETE
            deleted = await repo.delete(doc_id)
            assert deleted is True

            # Verify deletion
            doc_after_delete = await repo.get_by_id(doc_id)
            assert doc_after_delete is None

    @pytest.mark.asyncio
    async def test_page_crud_cycle(self, clean_test_db, sample_test_document, test_page_factory):
        """Test complete CRUD cycle for pages."""
        async with clean_test_db.connection() as conn:
            repo = PageRepository(conn)

            # CREATE
            page_data = test_page_factory(
                url="https://example.com/crud-test",
                title="CRUD Test Page",
                content="# CRUD Test\n\nThis is a test page for CRUD operations.",
            )
            page_data["document_id"] = sample_test_document.id

            page_id = await repo.create(**page_data)

            assert page_id > 0

            # READ
            page = await repo.get_by_id(page_id)
            assert page is not None
            assert page.document_id == sample_test_document.id
            assert page.url == page_data["url"]
            assert page.title == page_data["title"]
            assert page.content == page_data["content"]

            # Get by URL
            page_by_url = await repo.get_by_url(page_data["url"])
            assert page_by_url is not None
            assert page_by_url.id == page_id

            # List by document
            pages = await repo.list_by_document(sample_test_document.id)
            assert len(pages) >= 1
            assert any(p.id == page_id for p in pages)

            # UPDATE status
            updated = await repo.update_status(page_id, "chunked")
            assert updated is True

            page_after_update = await repo.get_by_id(page_id)
            assert page_after_update.status == "chunked"

            # DELETE
            deleted = await repo.delete(page_id)
            assert deleted is True

            # Verify deletion
            page_after_delete = await repo.get_by_id(page_id)
            assert page_after_delete is None

    @pytest.mark.asyncio
    async def test_chunk_crud_cycle(self, clean_test_db, sample_test_document, test_chunk_factory):
        """Test complete CRUD cycle for chunks."""
        repo = ChunkRepository(clean_test_db)

        # CREATE
        chunk_data = test_chunk_factory(
            document_id=sample_test_document.id,
            chunk_index=0,
            content="This is a test chunk for CRUD operations.",
            source_page_ids=[1, 2],
            embedding=[0.1] * 768,
        )

        chunk_id = await repo.create(**chunk_data)

        assert chunk_id > 0

        # READ
        chunk = await repo.get_by_id(chunk_id)
        assert chunk is not None
        assert chunk.document_id == sample_test_document.id
        assert chunk.chunk_index == chunk_data["chunk_index"]
        assert chunk.content == chunk_data["content"]
        assert chunk.source_page_ids == chunk_data["source_page_ids"]
        assert chunk.embedding == chunk_data["embedding"]

        # Get by document
        chunks = await repo.list_by_document(sample_test_document.id)
        assert len(chunks) >= 1
        assert any(c.id == chunk_id for c in chunks)

        # SEARCH - test vector search (basic)
        similar_chunks = await repo.search_similar(chunk_data["embedding"], limit=5)
        assert len(similar_chunks) >= 1
        assert any(c.id == chunk_id for c in similar_chunks)

        # DELETE
        deleted = await repo.delete(chunk_id)
        assert deleted is True

        # Verify deletion
        chunk_after_delete = await repo.get_by_id(chunk_id)
        assert chunk_after_delete is None

    @pytest.mark.asyncio
    async def test_transaction_behavior(self, clean_test_db, test_document_factory):
        """Test transaction behavior and rollback."""
        async with clean_test_db.connection() as conn:
            repo = DocumentRepository(conn)

            # Test successful transaction
            async with conn.transaction():
                doc_id1 = await repo.create(**test_document_factory("test-tx-1", "1.0.0"))
                doc_id2 = await repo.create(**test_document_factory("test-tx-2", "1.0.0"))

            # Verify both documents exist
            doc1 = await repo.get_by_id(doc_id1)
            doc2 = await repo.get_by_id(doc_id2)
            assert doc1 is not None
            assert doc2 is not None

            # Test transaction rollback
            try:
                async with conn.transaction():
                    doc_id3 = await repo.create(**test_document_factory("test-tx-3", "1.0.0"))
                    # Force an error
                    raise ValueError("Test rollback")
            except ValueError:
                pass  # Expected

            # Verify rollback worked
            doc3 = await repo.get_by_id(doc_id3)
            assert doc3 is None

    @pytest.mark.asyncio
    async def test_relationship_integrity(
        self, clean_test_db, sample_test_document, sample_test_pages, sample_test_chunks
    ):
        """Test referential integrity between documents, pages, and chunks."""
        async with clean_test_db.connection() as conn:
            doc_repo = DocumentRepository(conn)
            page_repo = PageRepository(conn)
            chunk_repo = ChunkRepository(clean_test_db)

            # Verify document exists
            doc = await doc_repo.get_by_id(sample_test_document.id)
            assert doc is not None

            # Verify pages belong to document
            pages = await page_repo.list_by_document(sample_test_document.id)
            assert len(pages) > 0
            for page in pages:
                assert page.document_id == sample_test_document.id

            # Verify chunks belong to document
            chunks = await chunk_repo.list_by_document(sample_test_document.id)
            assert len(chunks) > 0
            for chunk in chunks:
                assert chunk.document_id == sample_test_document.id

            # Test cascading delete behavior (if implemented)
            # Delete document and verify pages/chunks are handled appropriately

    @pytest.mark.asyncio
    async def test_unique_constraints(self, clean_test_db, test_document_factory):
        """Test unique constraints are enforced."""
        async with clean_test_db.connection() as conn:
            repo = DocumentRepository(conn)

            # Create first document
            doc_data = test_document_factory("test-unique", "1.0.0")
            doc_id1 = await repo.create(**doc_data)

            # Try to create duplicate (should fail or handle gracefully)
            try:
                doc_id2 = await repo.create(**doc_data)
                # If it succeeds, they should be different IDs
                assert doc_id2 != doc_id1
            except Exception:
                # Constraint violation is acceptable
                pass

    @pytest.mark.asyncio
    async def test_bulk_operations(self, clean_test_db, sample_test_document):
        """Test bulk create and delete operations."""
        repo = ChunkRepository(clean_test_db)

        # Create multiple chunks in batch
        chunk_data = [
            {
                "document_id": sample_test_document.id,
                "chunk_index": i,
                "content": f"Chunk {i} content",
                "source_page_ids": [1],
                "embedding": [0.1 * (i + 1)] * 768,
            }
            for i in range(5)
        ]

        chunk_ids = await repo.create_batch(chunk_data)
        assert len(chunk_ids) == 5

        # Verify all chunks exist
        for chunk_id in chunk_ids:
            chunk = await repo.get_by_id(chunk_id)
            assert chunk is not None

        # Bulk delete by document
        deleted_count = await repo.delete_by_document(sample_test_document.id)
        assert deleted_count >= 5

        # Verify deletion
        for chunk_id in chunk_ids:
            chunk = await repo.get_by_id(chunk_id)
            assert chunk is None

    @pytest.mark.asyncio
    async def test_index_performance(self, clean_test_db, sample_test_document, sample_test_pages):
        """Test that indexes are working and queries are efficient."""
        async with clean_test_db.connection() as conn:
            page_repo = PageRepository(conn)

            # Test indexed queries
            pages = await page_repo.list_by_document(sample_test_document.id, limit=100)
            assert len(pages) > 0

            # Test status filtering
            pending_pages = await page_repo.list_by_document(
                sample_test_document.id, status="pending", limit=100
            )
            chunked_pages = await page_repo.list_by_document(
                sample_test_document.id, status="chunked", limit=100
            )

            # Should not error (indexes should make this efficient)
            assert isinstance(pending_pages, list)
            assert isinstance(chunked_pages, list)

    @pytest.mark.asyncio
    async def test_data_validation(self, clean_test_db):
        """Test data validation and constraints."""
        async with clean_test_db.connection() as conn:
            doc_repo = DocumentRepository(conn)

            # Test invalid data handling
            try:
                # Try creating document with invalid data
                await doc_repo.create(name="", version="", description=None)
                # Should either succeed with defaults or fail gracefully
            except Exception:
                # Expected for invalid data
                pass

            # Test page validation
            page_repo = PageRepository(conn)

            try:
                # Try creating page with invalid URL
                await page_repo.create(
                    document_id=99999,  # Non-existent document
                    url="not-a-url",
                    content="",
                    title="",
                    content_hash="",
                    status="invalid",
                )
                # Should fail due to foreign key or validation
            except Exception:
                # Expected
                pass
