"""
Unit tests for GroupRepository.

Tests CRUD operations, filtering, statistics, and edge cases.
Uses async operations with pytest-asyncio.
"""

import os
import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
import json
from psqlpy import ConnectionPool
from psqlpy.exceptions import BaseConnectionPoolError

from context_bridge.database.repositories.group_repository import GroupRepository
from context_bridge.database.models.group_models import (
    Group,
    GroupCreate,
    GroupUpdate,
    ProcessingStatus,
    GroupStatistics,
)


def _get_test_dsn():
    """Build test database DSN from environment variables."""
    host = os.getenv("TEST_POSTGRES_HOST", "localhost")
    port = os.getenv("TEST_POSTGRES_PORT", "5432")
    user = os.getenv("TEST_POSTGRES_USER", "postgres")
    password = os.getenv("TEST_POSTGRES_PASSWORD", "postgres")
    database = os.getenv("TEST_POSTGRES_DB", "context_bridge_test")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture
async def connection_pool():
    """Create a test connection pool."""
    dsn = _get_test_dsn()
    pool = ConnectionPool(dsn)
    yield pool
    # Cleanup: close pool
    try:
        await pool.close()
    except Exception:
        pass


@pytest.fixture
async def repository(connection_pool):
    """Create a GroupRepository instance with a clean database."""
    repo = GroupRepository(connection_pool)
    # Clean groups/chunks before each test to ensure isolation
    try:
        async with repo.connection() as conn:
            await conn.execute("DELETE FROM chunks")
            await conn.execute("DELETE FROM groups")
            # Ensure a test document exists
            await conn.execute(
                "INSERT INTO documents (name, version, source_url) "
                "VALUES ('test-doc', '1.0', 'https://example.com') "
                "ON CONFLICT DO NOTHING"
            )
    except BaseConnectionPoolError as exc:
        pytest.skip(f"PostgreSQL unavailable for integration tests: {exc}")
    return repo


@pytest.fixture
async def test_group_data():
    """Create test group data."""
    return GroupCreate(
        document_id=1,
        name="Test Group",
        description="A test group for unit testing",
        context_enabled=False,
        context_model="gpt-4",
    )


# CRUD Tests


class TestGroupRepositoryCRUD:
    """Tests for CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_group_success(self, repository, test_group_data):
        """Test creating a group successfully."""
        # Assuming document_id=1 exists
        group = await repository.create_group(test_group_data)

        assert group.id is not None
        assert group.document_id == test_group_data.document_id
        assert group.name == test_group_data.name
        assert group.description == test_group_data.description
        assert group.context_enabled == test_group_data.context_enabled
        assert group.context_model == test_group_data.context_model
        assert group.processing_status == ProcessingStatus.PENDING
        assert group.total_pages == 0
        assert group.total_chunks == 0
        assert group.combined_content_length == 0
        assert group.created_at is not None
        assert group.processed_at is None

    @pytest.mark.asyncio
    async def test_create_group_invalid_document(self, repository):
        """Test creating a group with non-existent document."""
        invalid_data = GroupCreate(
            document_id=99999,
            name="Invalid Group",
            description="Should fail",
        )

        with pytest.raises(ValueError, match="Document with ID"):
            await repository.create_group(invalid_data)

    @pytest.mark.asyncio
    async def test_create_group_minimal_data(self, repository):
        """Test creating a group with minimal required data."""
        minimal_data = GroupCreate(document_id=1)

        group = await repository.create_group(minimal_data)

        assert group.document_id == 1
        assert group.name is None
        assert group.description is None
        assert group.context_enabled is False  # Default value
        assert group.context_model is None

    @pytest.mark.asyncio
    async def test_get_group_by_id_exists(self, repository, test_group_data):
        """Test getting an existing group by ID."""
        created = await repository.create_group(test_group_data)

        retrieved = await repository.get_group_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name
        assert retrieved.document_id == created.document_id

    @pytest.mark.asyncio
    async def test_get_group_by_id_not_exists(self, repository):
        """Test getting a non-existent group."""
        fake_id = uuid4()

        result = await repository.get_group_by_id(fake_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_group_all_fields(self, repository, test_group_data):
        """Test updating all updatable fields of a group."""
        created = await repository.create_group(test_group_data)

        updates = GroupUpdate(
            name="Updated Name",
            description="Updated Description",
            context_enabled=True,
            context_model="gpt-3.5-turbo",
            processing_status=ProcessingStatus.PROCESSING,
            total_pages=10,
            total_chunks=50,
            combined_content_length=5000,
        )

        updated = await repository.update_group(created.id, updates)

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.description == "Updated Description"
        assert updated.context_enabled is True
        assert updated.context_model == "gpt-3.5-turbo"
        assert updated.processing_status == ProcessingStatus.PROCESSING
        assert updated.total_pages == 10
        assert updated.total_chunks == 50
        assert updated.combined_content_length == 5000

    @pytest.mark.asyncio
    async def test_update_group_partial_fields(self, repository, test_group_data):
        """Test updating only some fields."""
        created = await repository.create_group(test_group_data)
        original_description = created.description

        updates = GroupUpdate(name="New Name")

        updated = await repository.update_group(created.id, updates)

        assert updated is not None
        assert updated.name == "New Name"
        assert updated.description == original_description  # Unchanged

    @pytest.mark.asyncio
    async def test_update_group_no_changes(self, repository, test_group_data):
        """Test updating with no field changes."""
        created = await repository.create_group(test_group_data)

        updates = GroupUpdate()

        result = await repository.update_group(created.id, updates)

        assert result is not None
        assert result.id == created.id

    @pytest.mark.asyncio
    async def test_update_group_not_exists(self, repository):
        """Test updating a non-existent group."""
        fake_id = uuid4()
        updates = GroupUpdate(name="New Name")

        result = await repository.update_group(fake_id, updates)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_group_exists(self, repository, test_group_data):
        """Test deleting an existing group."""
        created = await repository.create_group(test_group_data)
        group_id = created.id

        deleted = await repository.delete_group(group_id)

        assert deleted is True

        # Verify it's gone
        retrieved = await repository.get_group_by_id(group_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_group_not_exists(self, repository):
        """Test deleting a non-existent group."""
        fake_id = uuid4()

        deleted = await repository.delete_group(fake_id)

        assert deleted is False


# List and Filtering Tests


class TestGroupRepositoryFiltering:
    """Tests for list operations and filtering."""

    @pytest.mark.asyncio
    async def test_list_groups_empty(self, repository):
        """Test listing groups when none exist."""
        groups = await repository.list_groups()

        assert isinstance(groups, list)
        assert len(groups) == 0

    @pytest.mark.asyncio
    async def test_list_groups_all(self, repository, test_group_data):
        """Test listing all groups."""
        # Create 3 groups
        created_ids = []
        for i in range(3):
            data = GroupCreate(
                document_id=1,
                name=f"Group {i}",
            )
            group = await repository.create_group(data)
            created_ids.append(group.id)

        groups = await repository.list_groups()

        assert len(groups) >= 3
        for group in groups:
            if group.id in created_ids:
                assert group.document_id == 1

    @pytest.mark.asyncio
    async def test_list_groups_by_document(self, repository):
        """Test filtering groups by document ID."""
        # Create groups for different documents
        for doc_id in [1, 2]:
            data = GroupCreate(document_id=doc_id, name=f"Doc {doc_id} Group")
            await repository.create_group(data)

        doc1_groups = await repository.list_groups(document_id=1)

        assert all(g.document_id == 1 for g in doc1_groups)

    @pytest.mark.asyncio
    async def test_list_groups_by_context_enabled(self, repository):
        """Test filtering by context_enabled flag."""
        # Create groups with different context settings
        for enabled in [True, False]:
            data = GroupCreate(
                document_id=1,
                name=f"Context {enabled}",
                context_enabled=enabled,
            )
            await repository.create_group(data)

        enabled_groups = await repository.list_groups(context_enabled=True)
        disabled_groups = await repository.list_groups(context_enabled=False)

        assert all(g.context_enabled for g in enabled_groups)
        assert all(not g.context_enabled for g in disabled_groups)

    @pytest.mark.asyncio
    async def test_list_groups_by_processing_status(self, repository):
        """Test filtering by processing status."""
        # Create groups with different statuses
        for status in [ProcessingStatus.PENDING, ProcessingStatus.COMPLETED]:
            data = GroupCreate(
                document_id=1,
                name=f"Status {status.value}",
                processing_status=status,
            )
            group = await repository.create_group(data)

            # Update status if needed
            if status != ProcessingStatus.PENDING:
                updates = GroupUpdate(processing_status=status)
                await repository.update_group(group.id, updates)

        pending_groups = await repository.list_groups(processing_status=ProcessingStatus.PENDING)

        assert all(g.processing_status == ProcessingStatus.PENDING for g in pending_groups)

    @pytest.mark.asyncio
    async def test_list_groups_combined_filters(self, repository):
        """Test listing with multiple filters combined."""
        # Create test data
        for i in range(3):
            data = GroupCreate(
                document_id=1,
                name=f"Group {i}",
                context_enabled=(i % 2 == 0),
            )
            await repository.create_group(data)

        results = await repository.list_groups(document_id=1, context_enabled=True)

        assert all(g.document_id == 1 and g.context_enabled for g in results)

    @pytest.mark.asyncio
    async def test_list_groups_pagination(self, repository):
        """Test pagination with limit and offset."""
        # Create 5 groups
        for i in range(5):
            data = GroupCreate(
                document_id=1,
                name=f"Group {i}",
            )
            await repository.create_group(data)

        page1 = await repository.list_groups(limit=2, offset=0)
        page2 = await repository.list_groups(limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2

        # Ensure no overlap
        page1_ids = {g.id for g in page1}
        page2_ids = {g.id for g in page2}
        assert len(page1_ids & page2_ids) == 0


# Statistics Tests


class TestGroupRepositoryStatistics:
    """Tests for statistics and analytics methods."""

    @pytest.mark.asyncio
    async def test_get_group_statistics(self, repository, test_group_data):
        """Test getting statistics for a group."""
        group = await repository.create_group(test_group_data)

        stats = await repository.get_group_statistics(group.id)

        assert stats is not None
        assert stats.group_id == group.id
        assert stats.total_pages == 0
        assert stats.total_chunks == 0
        assert stats.total_content_bytes == 0
        assert stats.avg_page_size == 0.0
        assert stats.avg_chunk_size == 0.0
        assert isinstance(stats.page_ids, list)

    @pytest.mark.asyncio
    async def test_get_group_statistics_not_exists(self, repository):
        """Test getting statistics for non-existent group."""
        fake_id = uuid4()

        stats = await repository.get_group_statistics(fake_id)

        assert stats is None

    @pytest.mark.asyncio
    async def test_count_groups_by_document(self, repository):
        """Test counting groups for a document."""
        document_id = 1

        # Create 3 groups for doc 1
        for i in range(3):
            data = GroupCreate(
                document_id=document_id,
                name=f"Group {i}",
            )
            await repository.create_group(data)

        count = await repository.count_groups_by_document(document_id)

        assert count >= 3

    @pytest.mark.asyncio
    async def test_count_groups_by_document_no_groups(self, repository):
        """Test counting groups for document with no groups."""
        count = await repository.count_groups_by_document(9999)

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_non_context_groups(self, repository):
        """Test retrieving non-context groups."""
        # Create groups with different context settings
        non_context_ids = []
        context_ids = []

        for i in range(2):
            data = GroupCreate(
                document_id=1,
                name=f"Non-context {i}",
                context_enabled=False,
            )
            group = await repository.create_group(data)
            non_context_ids.append(group.id)

        for i in range(2):
            data = GroupCreate(
                document_id=1,
                name=f"Context {i}",
                context_enabled=True,
            )
            group = await repository.create_group(data)
            context_ids.append(group.id)

        non_context = await repository.get_non_context_groups(document_id=1)

        assert all(not g.context_enabled for g in non_context)
        for group in non_context:
            assert group.id not in context_ids

    @pytest.mark.asyncio
    async def test_get_non_context_groups_filtered(self, repository):
        """Test non-context groups with document filter."""
        # Create in doc 1
        data1 = GroupCreate(document_id=1, name="Doc1 Non-context", context_enabled=False)
        g1 = await repository.create_group(data1)

        # Create in doc 2
        data2 = GroupCreate(document_id=2, name="Doc2 Non-context", context_enabled=False)
        g2 = await repository.create_group(data2)

        results = await repository.get_non_context_groups(document_id=1)

        result_ids = {g.id for g in results}
        assert g1.id in result_ids
        assert g2.id not in result_ids


# Edge Case Tests


class TestGroupRepositoryEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_create_group_with_metadata(self, repository):
        """Test creating a group with metadata JSONB field."""
        metadata = {"source": "api", "batch_id": "batch_123"}
        data = GroupCreate(
            document_id=1,
            name="Group with metadata",
            metadata=metadata,
        )

        group = await repository.create_group(data)

        assert group.metadata == metadata

    @pytest.mark.asyncio
    async def test_update_group_with_metadata(self, repository, test_group_data):
        """Test updating group with new metadata."""
        group = await repository.create_group(test_group_data)

        new_metadata = {"key": "value", "count": 42}
        updates = GroupUpdate(metadata=new_metadata)

        updated = await repository.update_group(group.id, updates)

        assert updated.metadata == new_metadata

    @pytest.mark.asyncio
    async def test_update_group_processed_at_timestamp(self, repository, test_group_data):
        """Test updating processed_at timestamp."""
        group = await repository.create_group(test_group_data)

        now = datetime.utcnow()
        updates = GroupUpdate(
            processing_status=ProcessingStatus.COMPLETED,
            processed_at=now,
        )

        updated = await repository.update_group(group.id, updates)

        assert updated.processing_status == ProcessingStatus.COMPLETED
        assert updated.processed_at is not None

    @pytest.mark.asyncio
    async def test_group_name_with_special_characters(self, repository):
        """Test creating group with special characters in name."""
        special_name = 'Group \'with "quotes" and, special; chars!'
        data = GroupCreate(
            document_id=1,
            name=special_name,
        )

        group = await repository.create_group(data)

        assert group.name == special_name

    @pytest.mark.asyncio
    async def test_large_content_length_values(self, repository, test_group_data):
        """Test updating with very large content length values."""
        group = await repository.create_group(test_group_data)

        large_value = 2_000_000_000  # Within PostgreSQL INTEGER range (~2.1B max)
        updates = GroupUpdate(
            combined_content_length=large_value,
            total_pages=1_000_000,
            total_chunks=5_000_000,
        )

        updated = await repository.update_group(group.id, updates)

        assert updated.combined_content_length == large_value
        assert updated.total_pages == 1_000_000
        assert updated.total_chunks == 5_000_000

    @pytest.mark.asyncio
    async def test_rapid_concurrent_creates(self, repository):
        """Test creating multiple groups in rapid succession."""
        import asyncio

        async def create_group(index):
            data = GroupCreate(
                document_id=1,
                name=f"Concurrent Group {index}",
            )
            return await repository.create_group(data)

        # Create 5 groups concurrently
        groups = await asyncio.gather(*[create_group(i) for i in range(5)])

        assert len(groups) == 5
        assert all(g.id is not None for g in groups)
        assert len(set(g.id for g in groups)) == 5  # All unique


# Integration Tests


class TestGroupRepositoryIntegration:
    """Integration tests combining multiple operations."""

    @pytest.mark.asyncio
    async def test_full_group_lifecycle(self, repository, test_group_data):
        """Test complete group lifecycle: create, read, update, delete."""
        # Create
        group = await repository.create_group(test_group_data)
        assert group.id is not None

        # Read
        retrieved = await repository.get_group_by_id(group.id)
        assert retrieved.name == test_group_data.name

        # Update
        updates = GroupUpdate(
            name="Updated",
            processing_status=ProcessingStatus.COMPLETED,
        )
        updated = await repository.update_group(group.id, updates)
        assert updated.name == "Updated"

        # List with filters
        groups = await repository.list_groups(document_id=test_group_data.document_id)
        assert any(g.id == group.id for g in groups)

        # Delete
        deleted = await repository.delete_group(group.id)
        assert deleted is True

        # Verify deleted
        final = await repository.get_group_by_id(group.id)
        assert final is None

    @pytest.mark.asyncio
    async def test_workflow_create_and_process(self, repository):
        """Test workflow: create, track processing, update status."""
        data = GroupCreate(
            document_id=1,
            name="Process Workflow",
        )

        # Create group
        group = await repository.create_group(data)
        assert group.processing_status == ProcessingStatus.PENDING

        # Start processing
        updates1 = GroupUpdate(processing_status=ProcessingStatus.PROCESSING)
        processing = await repository.update_group(group.id, updates1)
        assert processing.processing_status == ProcessingStatus.PROCESSING

        # Complete processing
        updates2 = GroupUpdate(
            processing_status=ProcessingStatus.COMPLETED,
            total_pages=10,
            total_chunks=50,
            combined_content_length=5000,
            processed_at=datetime.utcnow(),
        )
        completed = await repository.update_group(group.id, updates2)
        assert completed.processing_status == ProcessingStatus.COMPLETED
        assert completed.processed_at is not None

        # Get statistics (derived from pages/chunks tables)
        stats = await repository.get_group_statistics(group.id)
        assert stats.total_pages == 0
        assert stats.total_chunks == 0
