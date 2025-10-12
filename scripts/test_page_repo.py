#!/usr/bin/env python3
"""
Page Repository Database Testing Script.

This script provides comprehensive testing of the PageRepository
with a real PostgreSQL database. It tests all CRUD operations,
status updates, and deduplication functionality using PSQLPy best practices.

Usage:
    python scripts/test_page_repo.py          # Run all tests
    python scripts/test_page_repo.py --init   # Initialize database first
    python scripts/test_page_repo.py --reset  # Reset database before testing
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository


class PageRepoTester:
    """
    Test class for PageRepository operations with real database.

    This class provides integration tests for all PageRepository
    methods using a real PostgreSQL connection.
    """

    def __init__(self):
        self.config = get_config()
        self.manager = PostgreSQLManager(self.config)
        self.doc_repo = DocumentRepository(self.manager)
        self.page_repo = PageRepository(self.manager)
        self.test_doc_id = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.manager.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.manager.close()

    async def cleanup_existing_test_data(self):
        """
        Clean up any existing test data before running tests.

        Returns:
            True if cleanup succeeded, False otherwise
        """
        print("🧹 Cleaning up existing test data...")

        try:
            # Create test document if it doesn't exist
            test_doc = await self.doc_repo.get_by_name_version("Test Document", "1.0.0")
            if not test_doc:
                self.test_doc_id = await self.doc_repo.create(
                    name="Test Document",
                    version="1.0.0",
                    description="Document for page repository testing",
                    metadata={"test": True},
                )
                print(f"   Created test document (ID: {self.test_doc_id})")
            else:
                self.test_doc_id = test_doc.id
                print(f"   Using existing test document (ID: {self.test_doc_id})")

            # Delete all test pages for this document
            pages = await self.page_repo.list_by_document(self.test_doc_id, limit=1000)
            print(f"   Found {len(pages)} test pages to clean up")

            deleted_count = 0
            for page in pages:
                success = await self.page_repo.delete(page.id)
                if success:
                    deleted_count += 1

            print(f"   ✅ Cleaned up {deleted_count} existing test pages")
            return True
        except Exception as e:
            print(f"   ❌ Error during cleanup: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_create_pages(self):
        """Test page creation and deduplication."""
        print("\n📝 Testing page creation and deduplication...")

        # Test data with unique URLs
        import time

        timestamp = int(time.time())
        pages = [
            {
                "url": f"https://example.com/page1-{timestamp}",
                "content": "# Page 1\n\nThis is the first test page.",
                "content_hash": "hash1",
                "metadata": {"priority": 1},
            },
            {
                "url": f"https://example.com/page2-{timestamp}",
                "content": "# Page 2\n\nThis is the second test page.",
                "content_hash": "hash2",
                "metadata": {"priority": 2},
            },
            {
                "url": f"https://example.com/page1-{timestamp}",  # Duplicate URL
                "content": "# Page 1 Duplicate\n\nDifferent content but same URL.",
                "content_hash": "hash1_duplicate",
                "metadata": {"priority": 3},
            },
        ]

        created_ids = []
        for page_data in pages:
            try:
                page_id = await self.page_repo.create(document_id=self.test_doc_id, **page_data)
                created_ids.append(page_id)
                print(f"   ✅ Created/retrieved page '{page_data['url']}' (ID: {page_id})")
            except Exception as e:
                print(f"   ❌ Failed to create page '{page_data['url']}': {e}")
                return False

        # Verify deduplication worked
        if len(created_ids) != 3 or created_ids[0] != created_ids[2]:
            print(f"   ❌ Deduplication failed: got IDs {created_ids}")
            return False

        print(f"   ✅ Deduplication worked: first and third pages have same ID ({created_ids[0]})")
        return created_ids[:2], [
            pages[0]["url"],
            pages[1]["url"],
        ]  # Return unique page IDs and URLs

    async def test_retrieve_pages(self, page_ids, test_urls):
        """Test page retrieval."""
        print("\n📖 Testing page retrieval...")

        # Test get_by_id
        for page_id in page_ids:
            try:
                page = await self.page_repo.get_by_id(page_id)
                if page:
                    print(
                        f"   ✅ Retrieved page ID {page_id}: '{page.url}' ({page.content_length} chars)"
                    )
                else:
                    print(f"   ❌ Page ID {page_id} not found")
                    return False
            except Exception as e:
                print(f"   ❌ Error retrieving page {page_id}: {e}")
                return False

        # Test get_by_url
        try:
            page = await self.page_repo.get_by_url(test_urls[0])
            if page:
                print(f"   ✅ Retrieved by URL: '{page.url}' (ID: {page.id})")
            else:
                print("   ❌ Page not found by URL")
                return False
        except Exception as e:
            print(f"   ❌ Error retrieving page by URL: {e}")
            return False

        return True

    async def test_list_and_count_pages(self):
        """Test listing and counting pages."""
        print("\n📋 Testing page listing and counting...")

        try:
            # Test count_by_document without status filter
            total_count = await self.page_repo.count_by_document(self.test_doc_id)
            print(f"   Total pages for document: {total_count}")

            # Test count_by_document with status filter
            pending_count = await self.page_repo.count_by_document(self.test_doc_id, "pending")
            print(f"   Pending pages for document: {pending_count}")

            # Test list_by_document without status filter
            all_pages = await self.page_repo.list_by_document(self.test_doc_id, limit=10)
            print(f"   Listed {len(all_pages)} pages total")

            # Test list_by_document with status filter
            pending_pages = await self.page_repo.list_by_document(
                self.test_doc_id, status="pending", limit=10
            )
            print(f"   Listed {len(pending_pages)} pending pages")

            # Verify counts match their respective lists
            expected_all_pages = min(total_count, 10)
            if len(all_pages) != expected_all_pages:
                print(
                    f"   ❌ List count mismatch: listed {len(all_pages)} but expected {expected_all_pages} (min of count {total_count} and limit 10)"
                )
                return False

            expected_pending_pages = min(pending_count, 10)
            if len(pending_pages) != expected_pending_pages:
                print(
                    f"   ❌ Pending count mismatch: listed {len(pending_pages)} but expected {expected_pending_pages} (min of count {pending_count} and limit 10)"
                )
                return False

            print("   ✅ All counts and lists match")
            return True

        except Exception as e:
            print(f"   ❌ Error in list/count operations: {e}")
            return False

    async def test_status_updates(self, page_ids):
        """Test status update operations."""
        print("\n🔄 Testing status updates...")

        try:
            # Test single status update
            success = await self.page_repo.update_status(page_ids[0], "grouped")
            if success:
                print(f"   ✅ Updated page {page_ids[0]} status to 'grouped'")
            else:
                print(f"   ❌ Failed to update page {page_ids[0]} status")
                return False

            # Verify status was updated
            page = await self.page_repo.get_by_id(page_ids[0])
            if page and page.status != "grouped":
                print(
                    f"   ❌ Status not updated correctly: got '{page.status}', expected 'grouped'"
                )
                return False

            # Test bulk status update
            bulk_count = await self.page_repo.update_status_bulk(
                [page_ids[0], page_ids[1]], "deleted"
            )
            if bulk_count == 2:
                print(f"   ✅ Bulk updated {bulk_count} pages to 'deleted'")
            else:
                print(f"   ❌ Bulk update failed: updated {bulk_count} pages, expected 2")
                return False

            # Verify bulk update worked
            for page_id in page_ids:
                page = await self.page_repo.get_by_id(page_id)
                if page and page.status != "deleted":
                    print(f"   ❌ Bulk status not updated for page {page_id}: got '{page.status}'")
                    return False

            print("   ✅ All status updates successful")
            return True

        except Exception as e:
            print(f"   ❌ Error in status updates: {e}")
            return False

    async def test_delete_operations(self):
        """Test delete operations."""
        print("\n🗑️  Testing delete operations...")

        try:
            # Create a fresh page for deletion testing
            delete_page_id = await self.page_repo.create(
                document_id=self.test_doc_id,
                url="https://example.com/delete-test",
                content="# Delete Test\n\nThis page will be deleted.",
                content_hash="delete_hash",
                metadata={"delete_test": True},
            )
            print(f"   Created page for deletion testing (ID: {delete_page_id})")

            # Test single delete
            success = await self.page_repo.delete(delete_page_id)
            if success:
                print(f"   ✅ Soft deleted page {delete_page_id}")
            else:
                print(f"   ❌ Failed to delete page {delete_page_id}")
                return False

            # Verify page status is 'deleted'
            page = await self.page_repo.get_by_id(delete_page_id)
            if page and page.status != "deleted":
                print(f"   ❌ Page not marked as deleted: status is '{page.status}'")
                return False

            # Create more pages for bulk delete testing
            bulk_delete_ids = []
            for i in range(3):
                page_id = await self.page_repo.create(
                    document_id=self.test_doc_id,
                    url=f"https://example.com/bulk-delete-{i}",
                    content=f"# Bulk Delete {i}\n\nContent {i}",
                    content_hash=f"bulk_hash_{i}",
                    metadata={"bulk_delete": True},
                )
                bulk_delete_ids.append(page_id)

            print(f"   Created {len(bulk_delete_ids)} pages for bulk deletion")

            # Test bulk delete
            bulk_count = await self.page_repo.delete_bulk(bulk_delete_ids)
            if bulk_count == len(bulk_delete_ids):
                print(f"   ✅ Bulk deleted {bulk_count} pages")
            else:
                print(
                    f"   ❌ Bulk delete failed: deleted {bulk_count} pages, expected {len(bulk_delete_ids)}"
                )
                return False

            # Verify all pages are marked as deleted
            for page_id in bulk_delete_ids:
                page = await self.page_repo.get_by_id(page_id)
                if page and page.status != "deleted":
                    print(f"   ❌ Page {page_id} not marked as deleted: status is '{page.status}'")
                    return False

            print("   ✅ All delete operations successful")
            return True

        except Exception as e:
            print(f"   ❌ Error in delete operations: {e}")
            return False

    async def test_deduplication(self):
        """Test content hash deduplication."""
        print("\n🔍 Testing content hash deduplication...")

        try:
            # Create some pages with known hashes
            test_hashes = ["dedupe_hash_1", "dedupe_hash_2", "dedupe_hash_3"]
            created_pages = []

            for i, hash_val in enumerate(test_hashes):
                page_id = await self.page_repo.create(
                    document_id=self.test_doc_id,
                    url=f"https://example.com/dedupe-{i}",
                    content=f"# Dedupe Page {i}\n\nContent {i}",
                    content_hash=hash_val,
                    metadata={"dedupe_test": True},
                )
                created_pages.append(page_id)
                print(f"   Created page with hash '{hash_val}' (ID: {page_id})")

            # Test check_duplicates with existing hashes
            existing = await self.page_repo.check_duplicates(test_hashes)
            if existing == set(test_hashes):
                print(f"   ✅ Found all {len(test_hashes)} existing hashes")
            else:
                print(f"   ❌ Hash check failed: found {existing}, expected {set(test_hashes)}")
                return False

            # Test check_duplicates with mix of existing and new hashes
            mixed_hashes = test_hashes + ["new_hash_1", "new_hash_2"]
            existing_mixed = await self.page_repo.check_duplicates(mixed_hashes)
            if existing_mixed == set(test_hashes):
                print(
                    f"   ✅ Correctly identified {len(test_hashes)} existing hashes from mixed list"
                )
            else:
                print(
                    f"   ❌ Mixed hash check failed: found {existing_mixed}, expected {set(test_hashes)}"
                )
                return False

            # Test check_duplicates with empty list
            empty_result = await self.page_repo.check_duplicates([])
            if empty_result == set():
                print("   ✅ Empty hash list check returned empty set")
            else:
                print(f"   ❌ Empty hash check failed: got {empty_result}")
                return False

            # Clean up test pages
            for page_id in created_pages:
                await self.page_repo.delete(page_id)

            print("   ✅ All deduplication tests passed")
            return True

        except Exception as e:
            print(f"   ❌ Error in deduplication tests: {e}")
            return False

    async def run_all_tests(self):
        """Run all tests in sequence."""
        print("🚀 Starting PageRepository integration tests...")

        # Cleanup
        if not await self.cleanup_existing_test_data():
            return False

        # Run tests
        tests = [
            ("Page Creation", self.test_create_pages),
            ("Page Retrieval", self.test_retrieve_pages),
            ("List/Count Operations", self.test_list_and_count_pages),
            ("Status Updates", self.test_status_updates),
            ("Delete Operations", self.test_delete_operations),
            ("Deduplication", self.test_deduplication),
        ]

        page_ids = None
        test_urls = None
        for test_name, test_func in tests:
            print(f"\n{'='*50}")
            print(f"Running: {test_name}")

            try:
                if "Retrieval" in test_name and page_ids and test_urls:
                    result = await test_func(page_ids, test_urls)
                elif "Updates" in test_name and page_ids:
                    result = await test_func(page_ids)
                else:
                    result = await test_func()

                if result is False:
                    print(f"❌ {test_name} FAILED")
                    return False
                elif (
                    isinstance(result, tuple) and len(result) == 2
                ):  # (page_ids, urls) from creation test
                    page_ids, test_urls = result
                    print(f"✅ {test_name} PASSED (created {len(page_ids)} pages)")
                else:
                    print(f"✅ {test_name} PASSED")

            except Exception as e:
                print(f"❌ {test_name} FAILED with exception: {e}")
                import traceback

                traceback.print_exc()
                return False

        print(f"\n{'='*50}")
        print("🎉 All PageRepository integration tests PASSED!")
        return True


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="PageRepository Integration Tests")
    parser.add_argument("--init", action="store_true", help="Initialize database first")
    parser.add_argument("--reset", action="store_true", help="Reset database before testing")
    args = parser.parse_args()

    try:
        async with PageRepoTester() as tester:
            # Initialize/reset database if requested
            if args.init or args.reset:
                from context_bridge.database.init_databases import init_postgresql

                print("🔧 Initializing database...")
                if args.reset:
                    print("   (Reset mode: dropping and recreating all tables)")
                await init_postgresql()

            # Run tests
            success = await tester.run_all_tests()

            if success:
                print("\n✅ All tests completed successfully!")
                sys.exit(0)
            else:
                print("\n❌ Some tests failed!")
                sys.exit(1)

    except Exception as e:
        print(f"❌ Fatal error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows
    if sys.platform == "win32":
        import os

        os.environ["PYTHONIOENCODING"] = "utf-8"

    asyncio.run(main())
