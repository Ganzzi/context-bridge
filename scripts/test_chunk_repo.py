#!/usr/bin/env python3
"""
Chunk Repository Database Testing Script.

This script provides comprehensive testing of the ChunkRepository
with a real PostgreSQL database. It tests all CRUD operations,
search functionality, and hybrid search using PSQLPy best practices.

Usage:
    python scripts/test_chunk_repo.py          # Run all tests
    python scripts/test_chunk_repo.py --init   # Initialize database first
    python scripts/test_chunk_repo.py --reset  # Reset database before testing
"""

import asyncio
import sys
from pathlib import Path
from typing import List

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository


class ChunkRepoTester:
    """
    Test class for ChunkRepository operations with real database.

    This class provides integration tests for all ChunkRepository
    methods using a real PostgreSQL connection.
    """

    def __init__(self):
        self.config = get_config()
        self.manager = PostgreSQLManager(self.config)
        self.doc_repo = DocumentRepository(self.manager)
        self.page_repo = PageRepository(self.manager)
        self.chunk_repo = ChunkRepository(self.manager)

        # Test data
        self.test_doc_id = None
        self.test_page_ids = []
        self.test_chunk_ids = []

    async def __aenter__(self):
        """Async context manager entry."""
        await self.manager.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.manager.close()

    async def setup_test_data(self):
        """Set up test document and group for chunk testing."""
        print("🔧 Setting up test data...")

        try:
            # Clean up any existing test data first
            await self.cleanup_test_data()

            # Create test document with unique name
            import uuid

            unique_suffix = str(uuid.uuid4())[:8]
            doc_name = f"Test Document {unique_suffix}"

            doc_id = await self.doc_repo.create(
                name=doc_name,
                version="1.0.0",
                source_url="https://example.com/test",
                description="Test document for chunk repository",
                metadata={"type": "test", "purpose": "chunk_testing"},
            )
            self.test_doc_id = doc_id
            print(f"   ✅ Created test document '{doc_name}' (ID: {doc_id})")

            # Create test pages with unique URLs
            page_ids = []
            for i in range(3):
                page_id = await self.page_repo.create(
                    document_id=doc_id,
                    url=f"https://example.com/test-{unique_suffix}-page{i+1}",
                    content=f"This is test page {i+1} content for chunking. It contains some text that will be split into chunks. Page {i+1} has unique content.",
                    content_hash=f"hash{unique_suffix}{i+1}",
                    metadata={"page_number": i + 1},
                )
                page_ids.append(page_id)
                print(f"   ✅ Created test page {i+1} (ID: {page_id})")

            # Store test page IDs
            self.test_page_ids = page_ids
            print(f"   ✅ Created {len(page_ids)} test pages")

            return True
        except Exception as e:
            print(f"   ❌ Error setting up test data: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def cleanup_test_data(self):
        """Clean up test data."""
        print("🧹 Cleaning up test data...")

        try:
            # Delete all test documents and their cascades (more thorough cleanup)
            async with self.manager.connection() as conn:
                # Find and delete test documents
                test_docs = await conn.execute(
                    "SELECT id FROM documents WHERE metadata->>'type' = 'test' AND metadata->>'purpose' = 'chunk_testing'"
                )
                test_doc_ids = [row["id"] for row in test_docs.result() or []]

                for doc_id in test_doc_ids:
                    try:
                        await self.doc_repo.delete(doc_id)
                        print(f"   ✅ Deleted test document (ID: {doc_id})")
                    except Exception as e:
                        print(f"   ⚠️  Error deleting test document {doc_id}: {e}")

            # Reset instance variables
            self.test_doc_id = None
            self.test_page_ids = []
            self.test_chunk_ids = []

            return True
        except Exception as e:
            print(f"   ❌ Error during cleanup: {e}")
            return False

    async def test_create_chunks(self):
        """Test chunk creation."""
        print("\n📝 Testing chunk creation...")

        if not self.test_doc_id or not self.test_page_ids:
            print("   ❌ Test data not set up")
            return False

        # Test data - mock embeddings (768 dimensions for typical models)
        test_chunks = [
            {
                "document_id": self.test_doc_id,
                "chunk_index": 0,
                "content": "This is the first chunk of content. It contains information about Python programming language features and best practices.",
                "embedding": [0.1] * 768,  # Mock embedding
            },
            {
                "document_id": self.test_doc_id,
                "chunk_index": 1,
                "content": "The second chunk discusses web development frameworks, particularly FastAPI and its async capabilities.",
                "embedding": [0.2] * 768,  # Mock embedding
            },
            {
                "document_id": self.test_doc_id,
                "chunk_index": 2,
                "content": "This chunk spans multiple pages and contains database-related information about PostgreSQL.",
                "embedding": [0.3] * 768,  # Mock embedding
            },
        ]

        created_ids = []
        for i, chunk_data in enumerate(test_chunks):
            try:
                chunk_id = await self.chunk_repo.create(**chunk_data)
                created_ids.append(chunk_id)
                print(f"   ✅ Created chunk {i+1} (ID: {chunk_id})")
            except Exception as e:
                print(f"   ❌ Failed to create chunk {i+1}: {e}")
                import traceback

                traceback.print_exc()
                return False

        self.test_chunk_ids = created_ids
        return created_ids

    async def test_create_batch_chunks(self):
        """Test batch chunk creation."""
        print("\n📦 Testing batch chunk creation...")

        if not self.test_doc_id:
            print("   ❌ Test data not set up")
            return False

        # Test batch data
        batch_chunks = [
            {
                "document_id": self.test_doc_id,
                "chunk_index": 3,
                "content": "Batch chunk 1: This is content created via batch operation.",
                "embedding": [0.4] * 768,
            },
            {
                "document_id": self.test_doc_id,
                "chunk_index": 4,
                "content": "Batch chunk 2: Another chunk from the batch creation test.",
                "embedding": [0.5] * 768,
            },
        ]

        try:
            batch_ids = await self.chunk_repo.create_batch(batch_chunks)
            if len(batch_ids) == len(batch_chunks):
                self.test_chunk_ids.extend(batch_ids)
                print(f"   ✅ Created {len(batch_ids)} chunks in batch")
                return True
            else:
                print(f"   ❌ Expected {len(batch_chunks)} chunks, got {len(batch_ids)}")
                return False
        except Exception as e:
            print(f"   ❌ Batch creation failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_retrieve_chunks(self):
        """Test chunk retrieval."""
        print("\n📖 Testing chunk retrieval...")

        if not self.test_chunk_ids:
            print("   ❌ No test chunks created")
            return False

        # Test get_by_id
        for chunk_id in self.test_chunk_ids[:2]:  # Test first 2 chunks
            try:
                chunk = await self.chunk_repo.get_by_id(chunk_id)
                if chunk:
                    print(
                        f"   ✅ Retrieved chunk ID {chunk_id}: index {chunk.chunk_index}, len={len(chunk.content)}"
                    )
                else:
                    print(f"   ❌ Chunk ID {chunk_id} not found")
                    return False
            except Exception as e:
                print(f"   ❌ Error retrieving chunk {chunk_id}: {e}")
                return False

        return True

    async def test_list_chunks(self):
        """Test chunk listing operations."""
        print("\n📋 Testing chunk listing...")

        if not self.test_doc_id:
            print("   ❌ Test data not set up")
            return False

        try:
            # Test list_by_document
            chunks = await self.chunk_repo.list_by_document(self.test_doc_id, limit=10)
            print(f"   ✅ Listed {len(chunks)} chunks for document {self.test_doc_id}")

            # Test count_by_document
            count = await self.chunk_repo.count_by_document(self.test_doc_id)
            print(f"   ✅ Counted {count} chunks for document {self.test_doc_id}")

            return True
        except Exception as e:
            print(f"   ❌ Error in listing operations: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_vector_search(self):
        """Test vector similarity search."""
        print("\n🔍 Testing vector search...")

        if not self.test_doc_id:
            print("   ❌ Test data not set up")
            return False

        try:
            # Use a query embedding similar to our test data
            query_embedding = [0.15] * 768  # Similar to first chunk's embedding

            results = await self.chunk_repo.vector_search(
                document_id=self.test_doc_id,
                query_embedding=query_embedding,
                limit=5,
                similarity_threshold=0.5,
            )

            print(f"   ✅ Vector search found {len(results)} results")
            for result in results[:3]:  # Show top 3
                print(
                    f"      Rank {result.rank}: Chunk {result.chunk.id}, Score {result.score:.3f}"
                )

            return True
        except Exception as e:
            print(f"   ❌ Vector search failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_bm25_search(self):
        """Test BM25 full-text search."""
        print("\n📄 Testing BM25 search...")

        if not self.test_doc_id:
            print("   ❌ Test data not set up")
            return False

        try:
            # Search for common terms in our test content
            query = "Python programming"

            results = await self.chunk_repo.bm25_search(
                document_id=self.test_doc_id, query=query, limit=5
            )

            print(f"   ✅ BM25 search for '{query}' found {len(results)} results")
            for result in results[:3]:  # Show top 3
                print(
                    f"      Rank {result.rank}: Chunk {result.chunk.id}, Score {result.score:.3f}"
                )

            return True
        except Exception as e:
            print(f"   ❌ BM25 search failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_hybrid_search(self):
        """Test hybrid search combining vector and BM25."""
        print("\n🔄 Testing hybrid search...")

        if not self.test_doc_id:
            print("   ❌ Test data not set up")
            return False

        try:
            query = "Python programming"
            query_embedding = [0.15] * 768

            results = await self.chunk_repo.hybrid_search(
                document_id=self.test_doc_id,
                query=query,
                query_embedding=query_embedding,
                vector_weight=0.7,
                bm25_weight=0.3,
                limit=5,
            )

            print(f"   ✅ Hybrid search found {len(results)} results")
            for result in results[:3]:  # Show top 3
                print(
                    f"      Rank {result.rank}: Chunk {result.chunk.id}, Score {result.score:.3f}"
                )

            return True
        except Exception as e:
            print(f"   ❌ Hybrid search failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_delete_operations(self):
        """Test chunk deletion operations."""
        print("\n🗑️  Testing delete operations...")

        if not self.test_doc_id:
            print("   ❌ Test data not set up")
            return False

        try:
            # Test delete_by_document
            deleted_count = await self.chunk_repo.delete_by_document(self.test_doc_id)
            print(f"   ✅ Deleted {deleted_count} chunks for document {self.test_doc_id}")

            # Verify chunks are gone
            remaining = await self.chunk_repo.count_by_document(self.test_doc_id)
            if remaining == 0:
                print("   ✅ Verified all chunks deleted")
            else:
                print(f"   ⚠️  {remaining} chunks still remain")

            return True
        except Exception as e:
            print(f"   ❌ Delete operations failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def run_all_tests(self):
        """Run all chunk repository tests."""
        print("🧪 Starting Chunk Repository Tests")
        print("=" * 50)

        # Test connection first
        try:
            is_healthy = await self.manager.health_check()
            if not is_healthy:
                print("❌ Database connection failed!")
                return False
            print("✅ Database connection successful")
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

        # Run tests
        try:
            # Set up test data
            if not await self.setup_test_data():
                return False

            # Test creation
            chunk_ids = await self.test_create_chunks()
            if not chunk_ids:
                return False

            batch_success = await self.test_create_batch_chunks()
            if not batch_success:
                return False

            # Test retrieval
            if not await self.test_retrieve_chunks():
                return False

            # Test listing
            if not await self.test_list_chunks():
                return False

            # Test search operations
            if not await self.test_vector_search():
                return False

            if not await self.test_bm25_search():
                return False

            if not await self.test_hybrid_search():
                return False

            # Test deletion
            if not await self.test_delete_operations():
                return False

            # Clean up
            await self.cleanup_test_data()

            return True

        except Exception as e:
            print(f"❌ Test suite failed with error: {e}")
            import traceback

            traceback.print_exc()
            return False


async def initialize_database():
    """Initialize the database schema."""
    print("🔧 Initializing database...")

    from context_bridge.database.init_databases import init_postgresql

    try:
        await init_postgresql()
        print("✅ Database initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


async def reset_database():
    """Reset the database (dev only)."""
    print("🔄 Resetting database...")

    from context_bridge.database.init_databases import reset_database

    try:
        await reset_database()
        print("✅ Database reset successfully!")
        return True
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        return False


async def main():
    """Main entry point."""
    print("🔧 Context Bridge Chunk Repository Tester")
    print("=" * 60)

    # Check command line arguments
    init_db = "--init" in sys.argv
    reset_db = "--reset" in sys.argv
    help_requested = "--help" in sys.argv or "-h" in sys.argv

    if help_requested:
        print(__doc__)
        sys.exit(0)

    try:
        if reset_db:
            if not await reset_database():
                sys.exit(1)

        if init_db or reset_db:
            if not await initialize_database():
                sys.exit(1)

        # Run tests
        async with ChunkRepoTester() as tester:
            success = await tester.run_all_tests()

        if success:
            print("\n✅ All chunk repository tests completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some chunk repository tests failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
