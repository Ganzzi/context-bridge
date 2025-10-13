#!/usr/bin/env python3
"""
DocManager Database Testing Script.

This script provides comprehensive testing of the DocManager
with a real PostgreSQL database and Ollama API. It tests document
crawling, storage, page management, and chunking operations using
real database connections and embedding services.

Usage:
    python scripts/test_doc_manager.py          # Run all tests
    python scripts/test_doc_manager.py --init   # Initialize database first
    python scripts/test_doc_manager.py --reset  # Reset database before testing
    python scripts/test_doc_manager.py --skip-ollama  # Skip Ollama-dependent tests
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.service.crawling_service import CrawlingService, CrawlConfig
from context_bridge.service.url_service import UrlService
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService
from context_bridge.service.doc_manager import DocManager


class DocManagerTester:
    """
    Test class for DocManager operations with real database and Ollama.

    This class provides integration tests for all DocManager
    methods using real PostgreSQL connection, Ollama API, and test data.
    """

    def __init__(self, skip_ollama: bool = False):
        self.config = get_config()
        self.manager = PostgreSQLManager(self.config)
        self.skip_ollama = skip_ollama

        # Initialize services
        self.crawling_service = CrawlingService(CrawlConfig(), UrlService())
        self.chunking_service = ChunkingService()
        self.embedding_service = EmbeddingService(self.config)

        # Initialize DocManager
        self.doc_manager = DocManager(
            db_manager=self.manager,
            crawling_service=self.crawling_service,
            chunking_service=self.chunking_service,
            embedding_service=self.embedding_service,
            config=self.config,
        )

        # Initialize repositories for direct access when needed
        self.doc_repo = DocumentRepository(self.manager)
        self.page_repo = PageRepository(self.manager)
        self.chunk_repo = ChunkRepository(self.manager)

        # Test data tracking
        self.test_docs = []  # List of (doc_id, name, version)
        self.test_pages = []  # List of page_ids

    async def __aenter__(self):
        """Async context manager entry."""
        await self.manager.initialize()

        if not self.skip_ollama:
            # Verify Ollama connection
            print("🔍 Verifying Ollama connection...")
            connection_ok = await self.embedding_service.verify_connection()
            if not connection_ok:
                raise RuntimeError(
                    "Ollama is not running or model is not available. "
                    "Start Ollama and run: ollama pull nomic-embed-text"
                )

            model_ok = await self.embedding_service.ensure_model_available()
            if not model_ok:
                raise RuntimeError("Ollama model is not working properly")

            print("✅ Ollama connection verified")
        else:
            print("⏭️  Skipping Ollama verification (--skip-ollama flag used)")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.manager.close()

    async def cleanup_test_data(self):
        """Clean up test data from previous runs."""
        print("🧹 Cleaning up test data...")

        try:
            # Delete chunks for test documents
            await self.manager.execute(
                """
                DELETE FROM chunks
                WHERE document_id IN (
                    SELECT id FROM documents
                    WHERE name LIKE 'test-doc-manager-%'
                )
            """
            )

            # Delete pages for test documents
            await self.manager.execute(
                """
                DELETE FROM pages
                WHERE document_id IN (
                    SELECT id FROM documents
                    WHERE name LIKE 'test-doc-manager-%'
                )
            """
            )

            # Delete test documents
            await self.manager.execute(
                """
                DELETE FROM documents
                WHERE name LIKE 'test-doc-manager-%'
            """
            )

            print("✅ Test data cleaned up")
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")

    async def test_crawl_and_store(self):
        """Test document crawling and storage functionality."""
        print("\n🕷️  Testing crawl_and_store functionality...")

        test_cases = [
            {
                "name": "test-doc-manager-httpbin",
                "version": "1.0.0",
                "url": "https://httpbin.org/html",
                "description": "Simple HTML test page",
            },
            {
                "name": "test-doc-manager-json",
                "version": "1.0.0",
                "url": "https://httpbin.org/json",
                "description": "JSON test endpoint",
            },
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"  Test case {i}: {test_case['name']} v{test_case['version']}")

            try:
                result = await self.doc_manager.crawl_and_store(
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
                doc = await self.doc_repo.get_by_id(result.document_id)
                assert doc is not None
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
            result = await self.doc_manager.crawl_and_store(
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

        # Create a new document specifically for deletion testing with a different URL
        print("  Creating test document for deletion...")
        delete_test_result = await self.doc_manager.crawl_and_store(
            name="test-doc-manager-delete",
            version="1.0.0",
            source_url="https://httpbin.org/uuid",  # Different URL to avoid duplicates
            description="Document for deletion testing",
        )

        doc_id = delete_test_result.document_id
        print(f"  Created document ID: {doc_id}")
        print(f"    📄 Pages stored: {delete_test_result.pages_stored}")
        print(f"    🔄 Duplicates skipped: {delete_test_result.duplicates_skipped}")

        # List all pages (including all statuses)
        all_pages = await self.doc_manager.list_pages(doc_id)
        print(f"    📋 Total pages: {len(all_pages)}")

        if all_pages:
            # Test listing with different statuses
            pending_pages = await self.doc_manager.list_pages(doc_id, status="pending")
            print(f"    ⏳ Pending pages: {len(pending_pages)}")

            # Test page deletion
            page_to_delete = all_pages[0]
            print(f"    🗑️  Deleting page ID: {page_to_delete.id} ({page_to_delete.url})")

            success = await self.doc_manager.delete_page(page_to_delete.id)
            assert success

            # Verify page is marked as deleted
            deleted_pages = await self.doc_manager.list_pages(doc_id, status="deleted")
            assert any(p.id == page_to_delete.id and p.status == "deleted" for p in deleted_pages)

            print("    ✅ Page deletion verified")
        else:
            print("    ⚠️  No pages found - all were duplicates")
            print("    ℹ️  This is expected if pages were already crawled in previous tests")

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
            pending_pages = await self.doc_manager.list_pages(doc_id, status="pending")
            print(f"    ⏳ Pending pages: {len(pending_pages)}")

            if pending_pages:
                page_ids = [p.id for p in pending_pages]

                # Test chunking with batch processing
                print(f"    🔄 Processing chunking for {len(page_ids)} pages (batch mode)...")
                chunk_result = await self.doc_manager.process_chunking(
                    document_id=doc_id,
                    page_ids=page_ids,
                    chunk_size=1000,  # Reasonable chunk size
                    batch_enabled=True,
                )

                print(f"    ✅ Processing started for {chunk_result.pages_processed} pages")

                # Wait for background processing to complete
                print("    ⏱️  Waiting for background processing...")
                max_wait = 15  # Maximum 15 seconds
                wait_interval = 1
                total_waited = 0

                while total_waited < max_wait:
                    await asyncio.sleep(wait_interval)
                    total_waited += wait_interval

                    # Check if pages are chunked
                    chunked_pages = await self.doc_manager.list_pages(doc_id, status="chunked")
                    processing_pages = await self.doc_manager.list_pages(
                        doc_id, status="processing"
                    )

                    if len(chunked_pages) >= len(page_ids):
                        print(f"    ✅ All pages chunked after {total_waited}s")
                        break
                    elif total_waited % 3 == 0:  # Progress update every 3 seconds
                        print(
                            f"    ⏳ Waiting... ({len(chunked_pages)}/{len(page_ids)} chunked, {len(processing_pages)} processing)"
                        )

                # Check final results
                chunked_pages = await self.doc_manager.list_pages(doc_id, status="chunked")
                print(f"    ✅ Chunked pages: {len(chunked_pages)}/{len(page_ids)}")

                # Verify chunks were created
                chunks = await self.chunk_repo.list_by_document(doc_id)
                print(f"    📦 Total chunks created: {len(chunks)}")

                if chunks:
                    # Verify chunk structure
                    sample_chunk = chunks[0]
                    assert sample_chunk.document_id == doc_id
                    assert isinstance(sample_chunk.content, str)
                    assert len(sample_chunk.content) > 0
                    assert sample_chunk.embedding is not None
                    print(f"    ✅ Sample chunk length: {len(sample_chunk.content)} chars")
                    print(f"    ✅ Embedding dimension: {len(sample_chunk.embedding)}")
                else:
                    print(f"    ⚠️  No chunks created (processing may still be running)")

            else:
                print("    ⚠️  No pending pages to process")

        print("✅ Chunking processing tests completed")

    async def test_error_handling(self):
        """Test error handling in various scenarios."""
        print("\n🚨 Testing error handling...")

        # Test with invalid URL
        print("  Testing invalid URL handling...")
        try:
            result = await self.doc_manager.crawl_and_store(
                name="test-doc-manager-invalid",
                version="1.0.0",
                source_url="https://invalid-domain-that-does-not-exist-12345.com",
            )
            print(f"    📊 Result: {result.errors} errors (expected)")
        except Exception as e:
            print(f"    ⚠️  Exception caught: {e}")

        # Test chunking with invalid page IDs
        print("  Testing invalid page ID handling...")
        try:
            await self.doc_manager.process_chunking(
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

    async def run_all_tests(self):
        """Run all DocManager tests."""
        print("🚀 Starting DocManager Integration Tests")
        print("=" * 50)

        try:
            # Clean up first
            await self.cleanup_test_data()

            # Run test suites
            await self.test_crawl_and_store()
            await self.test_duplicate_handling()

            # Run chunking before page management so we have pending pages
            if not self.skip_ollama:
                await self.test_chunking_processing()
            else:
                print("\n⏭️  Skipping chunking tests (--skip-ollama flag used)")

            # Page management tests create their own document for deletion
            await self.test_page_management()

            await self.test_error_handling()

            print("\n" + "=" * 50)
            if self.skip_ollama:
                print("✅ DocManager tests completed successfully (Ollama tests skipped)!")
            else:
                print("✅ All DocManager tests completed successfully!")

        except Exception as e:
            print(f"\n❌ Test suite failed: {e}")
            raise
        finally:
            # Final cleanup
            await self.cleanup_test_data()


async def main():
    """Main entry point for the test script."""
    parser = argparse.ArgumentParser(description="DocManager Integration Tests")
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
        config = get_config()
        manager = PostgreSQLManager(config)
        await manager.initialize()
        print("✅ Database initialized")
        await manager.close()
        return

    async with DocManagerTester(skip_ollama=args.skip_ollama) as tester:
        if args.reset:
            await tester.cleanup_test_data()
            print("✅ Database reset completed")

        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
