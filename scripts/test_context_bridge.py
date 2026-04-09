#!/usr/bin/env python3
"""
ContextBridge Integration Tests.

This script provides comprehensive testing of the ContextBridge
public API with a real PostgreSQL database and Ollama API. It tests
the complete workflow from crawling to searching using the unified API.

Usage:
    python scripts/test_context_bridge.py          # Run all tests
    python scripts/test_context_bridge.py --init   # Initialize database first
    python scripts/test_context_bridge.py --reset  # Reset database before testing
    python scripts/test_context_bridge.py --skip-ollama  # Skip Ollama-dependent tests
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge import ContextBridge
from context_bridge.config import get_config


class ContextBridgeTester:
    """
    Test class for ContextBridge operations with real database and Ollama.

    This class provides integration tests for all ContextBridge
    methods using real PostgreSQL connection, Ollama API, and test data.
    """

    def __init__(self, skip_ollama: bool = False):
        self.skip_ollama = skip_ollama

        # Test data tracking
        self.test_docs = []  # List of (doc_id, name, version)
        self.test_pages = []  # List of page_ids

    async def __aenter__(self):
        """Async context manager entry."""
        self.bridge = ContextBridge()
        await self.bridge.initialize()

        if not self.skip_ollama:
            # Verify Ollama connection
            print("🔍 Verifying Ollama connection...")
            health = await self.bridge.health_check()
            if not health.get("embedding_service", False):
                raise RuntimeError(
                    "Ollama is not running or model is not available. "
                    "Start Ollama and run: ollama pull nomic-embed-text"
                )

            print("✅ Ollama connection verified")
        else:
            print("⏭️  Skipping Ollama verification (--skip-ollama flag used)")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.bridge.close()

    async def cleanup_test_data(self):
        """Clean up test data from previous runs."""
        print("🧹 Cleaning up test data...")

        try:
            # Get all test documents
            docs = await self.bridge.find_documents()
            test_docs = [d for d in docs if d.name.startswith("test-cb-")]

            for doc in test_docs:
                print(f"  Deleting document: {doc.name} v{doc.version}")
                await self.bridge.delete_document(doc.id)

            print("✅ Test data cleaned up")
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")

    async def test_basic_operations(self):
        """Test basic document operations."""
        print("\n📄 Testing basic document operations...")

        # Test finding all documents (should be empty initially)
        docs = await self.bridge.find_documents()
        initial_count = len(docs)
        print(f"  Initial documents: {initial_count}")

        # Test finding non-existent document
        docs = await self.bridge.find_documents(name="non-existent", version="1.0.0")
        assert len(docs) == 0
        print("  ✅ Non-existent document returns empty list")

        print("✅ Basic operations tests completed")

    async def test_crawl_and_store(self):
        """Test document crawling and storage functionality."""
        print("\n🕷️  Testing crawl_and_store functionality...")

        test_cases = [
            {
                "name": "test-cb-httpbin",
                "version": "1.0.0",
                "url": "https://httpbin.org/html",
                "description": "Simple HTML test page",
            },
            {
                "name": "test-cb-json",
                "version": "1.0.0",
                "url": "https://httpbin.org/html",  # Changed from json to html for more content
                "description": "JSON test endpoint",
            },
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"  Test case {i}: {test_case['name']} v{test_case['version']}")

            try:
                result = await self.bridge.crawl_documentation(
                    name=test_case["name"],
                    version=test_case["version"],
                    source_url=test_case["url"],
                    description=test_case["description"],
                )

                print(f"    ✅ Document ID: {result.document_id}")
                print(f"    📄 Pages crawled: {result.pages_crawled}")
                print(f"    💾 Pages stored: {result.pages_stored}")
                print(f"    🔄 Duplicates skipped: {result.duplicates_skipped}")
                print(f"    ❌ Errors: {result.errors}")

                self.test_docs.append((result.document_id, test_case["name"], test_case["version"]))

                # Verify document was created
                docs = await self.bridge.find_documents(test_case["name"], test_case["version"])
                assert len(docs) == 1
                doc = docs[0]
                assert doc.name == test_case["name"]
                assert doc.version == test_case["version"]

            except Exception as e:
                print(f"    ❌ Error: {e}")
                raise

        print("✅ crawl_and_store tests completed")

    async def test_duplicate_handling(self):
        """Test duplicate document and page handling."""
        print("\n🔄 Testing duplicate handling...")

        # Use the first test document
        if not self.test_docs:
            await self.test_crawl_and_store()

        doc_id, name, version = self.test_docs[0]

        # Try to crawl the same document again
        print(f"  Recrawling {name} v{version}...")

        try:
            result = await self.bridge.crawl_documentation(
                name=name, version=version, source_url="https://httpbin.org/html"  # Same URL
            )

            print(f"    ✅ Reused document ID: {result.document_id}")
            print(f"    📄 Pages crawled: {result.pages_crawled}")
            print(f"    💾 Pages stored: {result.pages_stored} (should be 0)")
            print(f"    🔄 Duplicates skipped: {result.duplicates_skipped}")

            assert result.document_id == doc_id
            assert result.pages_stored == 0  # No new pages
            assert result.duplicates_skipped >= result.pages_crawled

        except Exception as e:
            print(f"    ❌ Error: {e}")
            raise

        print("✅ Duplicate handling tests completed")

    async def test_page_management(self):
        """Test page listing and deletion functionality."""
        print("\n📄 Testing page management...")

        # Ensure we have test documents
        if not self.test_docs:
            await self.test_crawl_and_store()

        for doc_id, name, version in self.test_docs:
            print(f"  Testing pages for {name} v{version} (ID: {doc_id})")

            # List all pages
            all_pages = await self.bridge.list_pages(doc_id)
            print(f"    📋 Total pages: {len(all_pages)}")

            if all_pages:
                # Test listing with different statuses
                pending_pages = await self.bridge.list_pages(doc_id, status="pending")
                print(f"    ⏳ Pending pages: {len(pending_pages)}")

                # Test page deletion
                page_to_delete = all_pages[0]
                print(f"    🗑️  Deleting page ID: {page_to_delete.id} ({page_to_delete.url})")

                success = await self.bridge.delete_page(page_to_delete.id)
                assert success

                # Verify page is marked as deleted
                deleted_pages = await self.bridge.list_pages(doc_id, status="deleted")
                assert any(
                    p.id == page_to_delete.id and p.status == "deleted" for p in deleted_pages
                )

                print("    ✅ Page deletion verified")
            else:
                print("    ⚠️  No pages found for this document")

        print("✅ Page management tests completed")

    async def test_chunking_processing(self):
        """Test chunking and embedding processing functionality."""
        print("\n🧩 Testing chunking processing...")

        # Ensure we have test documents with pages
        if not self.test_docs:
            await self.test_crawl_and_store()

        for doc_id, name, version in self.test_docs:
            print(f"  Testing chunking for {name} v{version} (ID: {doc_id})")

            # Get pending pages
            pending_pages = await self.bridge.list_pages(doc_id, status="pending")
            print(f"    ⏳ Pending pages: {len(pending_pages)}")

            if pending_pages:
                page_ids = [p.id for p in pending_pages]

                # Debug: Check content size
                from context_bridge.database.repositories.page_repository import PageRepository

                page_repo = PageRepository(self.bridge._db_manager)
                content_length = 0
                for page_id in page_ids:
                    page = await page_repo.get_by_id(page_id)
                    if page:
                        content_length += len(page.content)
                print(f"    📏 Total content length: {content_length} characters")

                # Test group creation with chunking and embedding
                print(f"    🔄 Creating group for {len(page_ids)} pages...")
                group_result = await self.bridge.create_group(
                    document_id=doc_id,
                    page_ids=page_ids,
                    chunk_size=1000,  # Reasonable chunk size
                    name=f"{name}_v{version}_group",
                )

                print(f"    ✅ Group created: {group_result.get('group_id', 'N/A')}")

                # Get group statistics
                print(f"    📊 Fetching group statistics...")
                if group_result.get("group_id"):
                    stats = await self.bridge.get_group_stats(group_result["group_id"])
                    print(
                        f"    📊 Group stats: {stats.get('chunk_count', 0)} chunks, status: {stats.get('status', 'unknown')}"
                    )
                else:
                    print("    ⚠️  Group ID not available in result")

            else:
                print("    ⚠️  No pending pages to process")

        print("✅ Chunking processing tests completed")

    async def test_synchronous_chunking(self):
        """Test synchronous chunking functionality."""
        print("\n🔄 Testing synchronous chunking...")

        # Create fresh test data for synchronous testing
        sync_docs = []
        try:
            # Create test documents
            result1 = await self.bridge.crawl_documentation(
                name="test-cb-sync-html",
                version="1.0.0",
                source_url="https://httpbin.org/html",
                description="Sync test HTML page",
            )
            sync_docs.append((result1.document_id, "test-cb-sync-html", "1.0.0"))

            result2 = await self.bridge.crawl_documentation(
                name="test-cb-sync-html2",
                version="1.0.0",
                source_url="https://httpbin.org/xml",  # Different endpoint
                description="Sync test XML page",
            )
            sync_docs.append((result2.document_id, "test-cb-sync-html2", "1.0.0"))
            sync_docs.append((result2.document_id, "test-cb-sync-json", "1.0.0"))

            for doc_id, name, version in sync_docs:
                print(f"  Testing synchronous chunking for {name} v{version} (ID: {doc_id})")

                # Get pending pages
                pending_pages = await self.bridge.list_pages(doc_id, status="pending")
                print(f"    ⏳ Pending pages: {len(pending_pages)}")

                if pending_pages:
                    page_ids = [p.id for p in pending_pages]

                    # Test synchronous chunking
                    print(f"    🔄 Creating group synchronously for {len(page_ids)} pages...")
                    start_time = asyncio.get_event_loop().time()

                    result = await self.bridge.create_group(
                        document_id=doc_id,
                        page_ids=page_ids,
                        chunk_size=1000,
                        name=f"sync_group_{doc_id}",
                    )

                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time

                    print(f"    ✅ Group creation completed in {duration:.1f}s")
                    print(f"    🆔 Group ID: {result.get('group_id', 'N/A')}")

                    # Verify group was created
                    if result.get("group_id"):
                        stats = await self.bridge.get_group_stats(result["group_id"])
                        print(
                            f"    📊 Group stats: {stats.get('chunk_count', 0)} chunks, status: {stats.get('status', 'unknown')}"
                        )
                        print("    ✅ Group creation completed successfully")
                    else:
                        print("    ⚠️  Group ID not available in result")

                else:
                    print("    ⚠️  No pending pages to process")

        finally:
            # Clean up sync test data
            for doc_id, name, version in sync_docs:
                try:
                    await self.bridge.delete_document(doc_id)
                    print(f"    🧹 Cleaned up sync test document: {name} v{version}")
                except Exception as e:
                    print(f"    ⚠️  Error cleaning up {name}: {e}")

        print("✅ Synchronous chunking tests completed")

    async def test_search_functionality(self):
        """Test search functionality."""
        print("\n🔍 Testing search functionality...")

        # Ensure we have processed documents
        if not self.test_docs:
            await self.test_crawl_and_store()

        if not self.skip_ollama:
            # Test search within a document
            doc_id, name, version = self.test_docs[0]
            print(f"  Testing search in {name} v{version} (ID: {doc_id})")

            try:
                results = await self.bridge.search(query="test", document_id=doc_id, limit=5)

                print(f"    ✅ Found {len(results)} results for query 'test'")
                if results:
                    sample = results[0]
                    print(f"    📄 Sample result score: {sample.score:.3f}")
                    print(f"    📝 Content preview: {sample.chunk.content[:100]}...")

            except Exception as e:
                print(f"    ❌ Search error: {e}")
                raise

            # Test find_documents functionality
            print(f"  Testing find_documents for {name}")
            try:
                # Find all versions of the document
                version_docs = await self.bridge.find_documents(name=name)
                print(f"    ✅ Found {len(version_docs)} version(s) of document '{name}'")

                for doc in version_docs:
                    print(f"      v{doc.version}: ID {doc.id}")

                # Find specific version
                specific_docs = await self.bridge.find_documents(name=name, version=version)
                print(f"    ✅ Found specific version: {len(specific_docs)} document(s)")

            except Exception as e:
                print(f"    ❌ Find documents error: {e}")
                raise
        else:
            print("  ⏭️  Skipping search tests (--skip-ollama flag used)")

        print("✅ Search functionality tests completed")

    async def test_error_handling(self):
        """Test error handling in various scenarios."""
        print("\n🚨 Testing error handling...")

        # Test with invalid URL
        print("  Testing invalid URL handling...")
        try:
            result = await self.bridge.crawl_documentation(
                name="test-cb-invalid",
                version="1.0.0",
                source_url="https://invalid-domain-that-does-not-exist-12345.com",
            )
            print(f"    📊 Result: {result.errors} errors (expected)")
        except Exception as e:
            print(f"    ⚠️  Exception caught: {e}")

        # Test group creation with invalid page IDs
        print("  Testing invalid page ID handling...")
        try:
            await self.bridge.create_group(
                document_id=99999,  # Non-existent document
                page_ids=[1, 2, 3],  # Non-existent pages
                chunk_size=1000,
            )
            print("    ❌ Should have raised an exception")
        except ValueError as e:
            print(f"    ✅ Expected ValueError: {e}")
        except Exception as e:
            print(f"    ⚠️  Unexpected exception: {e}")

        print("✅ Error handling tests completed")

    async def test_health_check(self):
        """Test health check functionality."""
        print("\n🏥 Testing health check...")

        try:
            health = await self.bridge.health_check()

            print("  Health status:")
            print(f"    ✅ Initialized: {health.get('initialized', False)}")
            print(f"    ✅ Database: {health.get('database', False)}")
            print(f"    ✅ Embedding service: {health.get('embedding_service', False)}")

            services = health.get("services", {})
            print(f"    ✅ Doc manager: {services.get('doc_manager', False)}")
            print(f"    ✅ Search service: {services.get('search_service', False)}")

            # Verify all critical services are healthy
            assert health.get("initialized", False)
            assert health.get("database", False)
            if not self.skip_ollama:
                assert health.get("embedding_service", False)

        except Exception as e:
            print(f"    ❌ Health check error: {e}")
            raise

        print("✅ Health check tests completed")

    async def run_all_tests(self):
        """Run all ContextBridge tests."""
        print("🚀 Starting ContextBridge Integration Tests")
        print("=" * 50)

        try:
            # Clean up first
            await self.cleanup_test_data()

            # Run test suites
            await self.test_basic_operations()
            await self.test_crawl_and_store()
            await self.test_duplicate_handling()

            if not self.skip_ollama:
                await self.test_chunking_processing()
                await self.test_synchronous_chunking()
                await self.test_search_functionality()
            else:
                print("\n⏭️  Skipping chunking and search tests (--skip-ollama flag used)")

            await self.test_page_management()
            await self.test_error_handling()
            await self.test_health_check()

            print("\n" + "=" * 50)
            if self.skip_ollama:
                print("✅ ContextBridge tests completed successfully (Ollama tests skipped)!")
            else:
                print("✅ All ContextBridge tests completed successfully!")

        except Exception as e:
            print(f"\n❌ Test suite failed: {e}")
            raise
        finally:
            # Final cleanup
            await self.cleanup_test_data()


async def main():
    """Main entry point for the test script."""
    parser = argparse.ArgumentParser(description="ContextBridge Integration Tests")
    parser.add_argument("--init", action="store_true", help="Initialize database only")
    parser.add_argument("--reset", action="store_true", help="Reset database before testing")
    parser.add_argument(
        "--skip-ollama",
        action="store_true",
        help="Skip Ollama-dependent tests (crawling and chunking)",
    )
    args = parser.parse_args()

    if args.init:
        # Just initialize and exit
        async with ContextBridge() as bridge:
            print("✅ ContextBridge initialized successfully")
        return

    async with ContextBridgeTester(skip_ollama=args.skip_ollama) as tester:
        if args.reset:
            await tester.cleanup_test_data()
            print("✅ Database reset completed")

        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
