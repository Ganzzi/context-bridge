#!/usr/bin/env python3
"""
Group Repository Database Testing Script.

This script provides comprehensive testing of the GroupRepository
with a real PostgreSQL database. It tests all CRUD operations,
group creation, content concatenation, and constraint validation.

Usage:
    python scripts/test_group_repo.py          # Run all tests
    python scripts/test_group_repo.py --init   # Initialize database first
    python scripts/test_group_repo.py --reset  # Reset database before testing
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.group_repository import GroupRepository


class GroupRepoTester:
    """
    Test class for GroupRepository operations with real database.

    This class provides integration tests for all GroupRepository
    methods using a real PostgreSQL connection.
    """

    def __init__(self):
        self.config = get_config()
        self.manager = PostgreSQLManager(self.config)
        self.doc_repo = DocumentRepository(self.manager)
        self.page_repo = PageRepository(self.manager)
        self.group_repo = GroupRepository(self.manager)
        self.test_doc_id = None
        self.test_page_ids = []

    async def __aenter__(self):
        """Async context manager entry."""
        await self.manager.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.manager.close()

    async def setup_test_data(self):
        """Create test document and pages for testing."""
        print("Setting up test data...")

        # Create test document with unique name
        import time

        unique_suffix = str(int(time.time()))
        doc_name = f"Test Document {unique_suffix}"

        # Create test document
        doc_id = await self.doc_repo.create(
            name=doc_name, version="1.0.0", description="Test document for group repository testing"
        )
        self.test_doc_id = doc_id
        print(f"Created test document with ID: {doc_id}")

        # Create test pages
        base_time = datetime.now()
        pages_data = [
            {
                "url": f"https://example.com/page{i}_{unique_suffix}",
                "content": f"# Page {i}\n\nThis is test content for page {i}.\n\n{'Some additional content. ' * i}",
                "content_hash": f"hash{i}_{unique_suffix}",
                "metadata": {"index": i},
            }
            for i in range(1, 6)  # Create 5 test pages
        ]

        for i, page_data in enumerate(pages_data, 1):
            page_id = await self.page_repo.create(
                document_id=doc_id,
                url=page_data["url"],
                content=page_data["content"],
                content_hash=page_data["content_hash"],
                metadata=page_data["metadata"],
            )
            self.test_page_ids.append(page_id)
            print(f"Created test page {i} with ID: {page_id}")

        print(f"Setup complete. Document ID: {doc_id}, Page IDs: {self.test_page_ids}")

    async def cleanup_test_data(self):
        """Clean up test data."""
        print("Cleaning up test data...")

        # Delete test document (cascade will delete pages and groups)
        if self.test_doc_id:
            await self.doc_repo.delete(self.test_doc_id)
            print(f"Deleted test document {self.test_doc_id}")

        self.test_doc_id = None
        self.test_page_ids = []

    async def test_create_group(self):
        """Test group creation with validation."""
        print("\n=== Testing Group Creation ===")

        # Test successful group creation
        group_id = await self.group_repo.create_group(
            document_id=self.test_doc_id,
            page_ids=self.test_page_ids[:3],  # Use first 3 pages
            name="Test Group 1",
        )
        print(f"✓ Created group with ID: {group_id}")

        # Verify group was created
        group = await self.group_repo.get_by_id(group_id)
        assert group is not None
        assert group.document_id == self.test_doc_id
        assert group.name == "Test Group 1"
        assert group.page_count == 3
        assert group.status == "eligible"
        print(f"✓ Group verified: {group.page_count} pages, total size {group.total_size}")

        # Test group with pages
        group_with_pages = await self.group_repo.get_with_pages(group_id)
        assert group_with_pages is not None
        assert len(group_with_pages.page_ids) == 3
        print(f"✓ Group has {len(group_with_pages.page_ids)} member pages")

        return group_id

    async def test_group_content_concatenation(self, group_id):
        """Test group content concatenation."""
        print("\n=== Testing Content Concatenation ===")

        content = await self.group_repo.get_group_content(group_id)
        print(f"✓ Retrieved group content, length: {len(content)}")

        # Verify content contains expected separators
        assert "\n\n---\n\n" in content
        print("✓ Content properly concatenated with separators")

        # Verify all page content is included
        for i in range(1, 4):  # Pages 1-3
            assert f"Page {i}" in content
        print("✓ All page content included")

    async def test_group_operations(self, group_id):
        """Test various group operations."""
        print("\n=== Testing Group Operations ===")

        # Test status update
        success = await self.group_repo.update_status(group_id, "processed")
        assert success
        print("✓ Status updated to 'processed'")

        # Verify status change
        group = await self.group_repo.get_by_id(group_id)
        assert group.status == "processed"
        print("✓ Status change verified")

        # Test listing groups
        groups = await self.group_repo.list_by_document(self.test_doc_id)
        assert len(groups) >= 1
        print(f"✓ Listed {len(groups)} groups for document")

        # Test eligible groups
        eligible = await self.group_repo.get_eligible_groups(self.test_doc_id)
        print(f"✓ Found {len(eligible)} eligible groups")

    async def test_constraint_validation(self):
        """Test constraint validation."""
        print("\n=== Testing Constraint Validation ===")

        # Use pages that weren't grouped in the previous test (pages 4 and 5)
        unused_pages = self.test_page_ids[3:]

        # Test valid constraints
        is_valid, error, total_size = await self.group_repo.validate_group_constraints(unused_pages)
        assert is_valid
        assert error is None
        assert total_size > 0
        print(f"✓ Valid constraints: total_size={total_size}")

        # Test empty pages
        is_valid, error, total_size = await self.group_repo.validate_group_constraints([])
        assert not is_valid
        assert "empty page list" in error
        print("✓ Empty pages validation works")

        # Test size constraints
        is_valid, error, total_size = await self.group_repo.validate_group_constraints(
            unused_pages, min_size=10000  # Very large minimum
        )
        assert not is_valid
        assert "below minimum" in error
        print("✓ Size constraints work")

    async def test_group_deletion(self, group_id):
        """Test group deletion and ungrouping."""
        print("\n=== Testing Group Deletion ===")

        # Test ungrouping
        success = await self.group_repo.ungroup(group_id)
        assert success
        print("✓ Group ungrouped successfully")

        # Verify pages are back to pending
        for page_id in self.test_page_ids[:3]:
            page = await self.page_repo.get_by_id(page_id)
            assert page.status == "pending"
        print("✓ Pages reset to pending status")

        # Verify group is deleted
        group = await self.group_repo.get_by_id(group_id)
        assert group is None
        print("✓ Group deleted")

    async def test_multiple_groups(self):
        """Test creating and managing multiple groups."""
        print("\n=== Testing Multiple Groups ===")

        # Create two separate groups with non-overlapping pages
        group_ids = []
        # Group 1: pages 0-1
        group_id1 = await self.group_repo.create_group(
            document_id=self.test_doc_id,
            page_ids=self.test_page_ids[0:2],
            name="Test Group A",
        )
        group_ids.append(group_id1)
        print(f"✓ Created group A with ID: {group_id1}")

        # Group 2: pages 2-3
        group_id2 = await self.group_repo.create_group(
            document_id=self.test_doc_id,
            page_ids=self.test_page_ids[2:4],
            name="Test Group B",
        )
        group_ids.append(group_id2)
        print(f"✓ Created group B with ID: {group_id2}")

        # List all groups
        groups = await self.group_repo.list_by_document(self.test_doc_id)
        assert len(groups) >= 2
        print(f"✓ Listed {len(groups)} groups total")

        # Test filtering by status
        eligible_groups = await self.group_repo.list_by_document(
            self.test_doc_id, status="eligible"
        )
        print(f"✓ Found {len(eligible_groups)} eligible groups")

        # Clean up groups
        for group_id in group_ids:
            await self.group_repo.delete(group_id)
        print("✓ Cleaned up test groups")

    async def run_all_tests(self):
        """Run all integration tests."""
        print("Starting GroupRepository Integration Tests")
        print("=" * 50)

        try:
            await self.setup_test_data()

            # Run tests
            group_id = await self.test_create_group()
            await self.test_group_content_concatenation(group_id)
            await self.test_group_operations(group_id)
            await self.test_constraint_validation()
            await self.test_group_deletion(group_id)
            await self.test_multiple_groups()

            print("\n" + "=" * 50)
            print("✅ All GroupRepository integration tests passed!")

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            raise
        finally:
            await self.cleanup_test_data()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Group Repository Integration Tests")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--reset", action="store_true", help="Reset database before testing")

    args = parser.parse_args()

    async with GroupRepoTester() as tester:
        if args.init or args.reset:
            from context_bridge.database.init_databases import init_databases

            print("Initializing database...")
            await init_databases()

        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
