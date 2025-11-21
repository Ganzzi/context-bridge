"""
Unit tests for TagRepository.
"""

import pytest
from context_bridge.database.repositories.tag_repository import TagRepository
from context_bridge.database.models.tag_models import (
    TagCreate,
    TagCategory,
    TagUpdate,
)


@pytest.mark.asyncio
class TestTagRepository:
    """Test cases for TagRepository."""

    async def test_create_tag(self, db_manager):
        """Test creating a new tag."""
        repo = TagRepository(db_manager)

        tag_create = TagCreate(
            name="test-tag",
            category=TagCategory.CUSTOM,
            description="Test tag description",
        )

        tag = await repo.create_tag(tag_create)

        assert tag is not None
        assert tag.name == "test-tag"
        assert tag.category == TagCategory.CUSTOM
        assert tag.description == "Test tag description"
        assert tag.id is not None

    async def test_get_tag_by_id(self, db_manager):
        """Test retrieving a tag by ID."""
        repo = TagRepository(db_manager)

        # Create a tag
        tag_create = TagCreate(
            name="api-test",
            category=TagCategory.DOCUMENTATION_TYPE,
        )
        created_tag = await repo.create_tag(tag_create)

        # Retrieve by ID
        retrieved_tag = await repo.get_tag_by_id(created_tag.id)

        assert retrieved_tag is not None
        assert retrieved_tag.id == created_tag.id
        assert retrieved_tag.name == "api-test"

    async def test_get_tag_by_name(self, db_manager):
        """Test retrieving a tag by name."""
        repo = TagRepository(db_manager)

        # Create a tag
        tag_create = TagCreate(
            name="python-doc",
            category=TagCategory.TECHNOLOGY,
        )
        created_tag = await repo.create_tag(tag_create)

        # Retrieve by name
        retrieved_tag = await repo.get_tag_by_name("python-doc")

        assert retrieved_tag is not None
        assert retrieved_tag.name == "python-doc"
        assert retrieved_tag.id == created_tag.id

    async def test_list_tags(self, db_manager):
        """Test listing tags."""
        repo = TagRepository(db_manager)

        # Create multiple tags
        for i in range(3):
            tag_create = TagCreate(
                name=f"list-test-{i}",
                category=TagCategory.CUSTOM,
            )
            await repo.create_tag(tag_create)

        # List tags
        tags = await repo.list_tags(limit=10)

        assert len(tags) >= 3
        assert all(hasattr(tag, "id") for tag in tags)
        assert all(hasattr(tag, "name") for tag in tags)

    async def test_list_tags_by_category(self, db_manager):
        """Test listing tags filtered by category."""
        repo = TagRepository(db_manager)

        # Create tags in different categories
        tech_tag = TagCreate(
            name="category-test-tech",
            category=TagCategory.TECHNOLOGY,
        )
        doc_tag = TagCreate(
            name="category-test-doc",
            category=TagCategory.DOCUMENTATION_TYPE,
        )

        await repo.create_tag(tech_tag)
        await repo.create_tag(doc_tag)

        # List by category
        tech_tags = await repo.list_tags(category=TagCategory.TECHNOLOGY, limit=10)
        doc_tags = await repo.list_tags(category=TagCategory.DOCUMENTATION_TYPE, limit=10)

        # Check that filtered lists contain appropriate tags
        tech_names = [t.name for t in tech_tags]
        doc_names = [t.name for t in doc_tags]

        assert "category-test-tech" in tech_names
        assert "category-test-doc" in doc_names
        assert "category-test-tech" not in doc_names

    async def test_update_tag(self, db_manager):
        """Test updating a tag."""
        repo = TagRepository(db_manager)

        # Create a tag
        tag_create = TagCreate(
            name="update-test",
            category=TagCategory.CUSTOM,
            description="Original description",
        )
        created_tag = await repo.create_tag(tag_create)

        # Update the tag
        update = TagUpdate(description="Updated description")
        updated_tag = await repo.update_tag(created_tag.id, update)

        assert updated_tag is not None
        assert updated_tag.description == "Updated description"
        assert updated_tag.name == "update-test"

    async def test_delete_tag(self, db_manager):
        """Test deleting a tag."""
        repo = TagRepository(db_manager)

        # Create a tag
        tag_create = TagCreate(
            name="delete-test",
            category=TagCategory.CUSTOM,
        )
        created_tag = await repo.create_tag(tag_create)

        # Delete the tag
        deleted = await repo.delete_tag(created_tag.id)
        assert deleted

        # Verify tag is deleted
        retrieved = await repo.get_tag_by_id(created_tag.id)
        assert retrieved is None

    async def test_add_tag_to_document(self, db_manager, sample_document):
        """Test adding a tag to a document."""
        repo = TagRepository(db_manager)

        # Create a tag
        tag_create = TagCreate(
            name="doc-tag-test",
            category=TagCategory.CUSTOM,
        )
        tag = await repo.create_tag(tag_create)

        # Add tag to document
        added = await repo.add_tag_to_document(sample_document.id, tag.id)
        assert added

        # Verify tag was added
        tags = await repo.get_document_tags(sample_document.id)
        tag_ids = [t.id for t in tags]
        assert tag.id in tag_ids

    async def test_add_multiple_tags_to_document(self, db_manager, sample_document):
        """Test adding multiple tags to a document."""
        repo = TagRepository(db_manager)

        # Create multiple tags
        tag_ids = []
        for i in range(3):
            tag_create = TagCreate(
                name=f"multi-tag-test-{i}",
                category=TagCategory.CUSTOM,
            )
            tag = await repo.create_tag(tag_create)
            tag_ids.append(tag.id)

        # Add all tags to document
        count = await repo.add_tags_to_document(sample_document.id, tag_ids)
        assert count == 3

        # Verify all tags were added
        doc_tags = await repo.get_document_tags(sample_document.id)
        doc_tag_ids = [t.id for t in doc_tags]
        assert all(tid in doc_tag_ids for tid in tag_ids)

    async def test_remove_tag_from_document(self, db_manager, sample_document):
        """Test removing a tag from a document."""
        repo = TagRepository(db_manager)

        # Create and add a tag
        tag_create = TagCreate(
            name="remove-tag-test",
            category=TagCategory.CUSTOM,
        )
        tag = await repo.create_tag(tag_create)
        await repo.add_tag_to_document(sample_document.id, tag.id)

        # Remove tag
        removed = await repo.remove_tag_from_document(sample_document.id, tag.id)
        assert removed

        # Verify tag was removed
        tags = await repo.get_document_tags(sample_document.id)
        tag_ids = [t.id for t in tags]
        assert tag.id not in tag_ids

    async def test_get_documents_by_tag(self, db_manager, sample_document):
        """Test getting documents by tag."""
        repo = TagRepository(db_manager)

        # Create a tag
        tag_create = TagCreate(
            name="search-tag-test",
            category=TagCategory.CUSTOM,
        )
        tag = await repo.create_tag(tag_create)

        # Add tag to document
        await repo.add_tag_to_document(sample_document.id, tag.id)

        # Get documents by tag
        doc_ids = await repo.get_documents_by_tag(tag.id)

        assert sample_document.id in doc_ids

    async def test_get_tag_statistics(self, db_manager):
        """Test getting tag statistics."""
        repo = TagRepository(db_manager)

        # Get statistics
        stats = await repo.get_tag_statistics()

        assert stats is not None
        assert len(stats) > 0
        assert all(hasattr(s, "tag_id") for s in stats)
        assert all(hasattr(s, "usage_count") for s in stats)

    async def test_count_tags_by_category(self, db_manager):
        """Test counting tags by category."""
        repo = TagRepository(db_manager)

        # Get counts
        counts = await repo.count_tags_by_category()

        assert counts is not None
        assert "documentation_type" in counts or "technology" in counts or "domain" in counts
        assert all(isinstance(v, int) for v in counts.values())
