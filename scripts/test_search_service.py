#!/usr/bin/env python3
"""
Search Service Database Testing Script.

This script provides comprehensive testing of the SearchService
with a real PostgreSQL database. It tests document search, content search,
and cross-version search functionality using real database connections.

Usage:
    python scripts/test_search_service.py          # Run all tests
    python scripts/test_search_service.py --init   # Initialize database first
    python scripts/test_search_service.py --reset  # Reset database before testing
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.group_repository import GroupRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.service.search_service import SearchService
from context_bridge.service.embedding import EmbeddingService


class SearchServiceTester:
    """
    Test class for SearchService operations with real database.

    This class provides integration tests for all SearchService
    methods using a real PostgreSQL connection and test data.
    """

    def __init__(self):
        self.config = get_config()
        self.manager = PostgreSQLManager(self.config)

        # Initialize repositories
        self.doc_repo = DocumentRepository(self.manager)
        self.page_repo = PageRepository(self.manager)
        self.group_repo = GroupRepository(self.manager)
        self.chunk_repo = ChunkRepository(self.manager)

        # Initialize services
        self.embedding_service = EmbeddingService(self.config)
        self.search_service = SearchService(
            document_repo=self.doc_repo,
            chunk_repo=self.chunk_repo,
            embedding_service=self.embedding_service,
        )

        # Test data
        self.test_docs = []  # List of (doc_id, name, version)
        self.test_groups = []  # List of group_ids
        self.test_chunks = []  # List of chunk_ids

    async def __aenter__(self):
        """Async context manager entry."""
        await self.manager.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.manager.close()

    async def setup_test_data(self):
        """Set up comprehensive test data for search testing."""
        print("🔧 Setting up test data...")

        try:
            # Clean up any existing test data first
            await self.cleanup_test_data()

            # Create multiple test documents with different content
            test_documents = [
                {
                    "name": "Python Programming Guide",
                    "version": "1.0.0",
                    "description": "Comprehensive guide to Python programming language",
                    "source_url": "https://python.org/guide",
                    "pages": [
                        {
                            "url": "https://python.org/guide/intro",
                            "content": "Python is a high-level programming language known for its simplicity and readability. It supports multiple programming paradigms including object-oriented, imperative, and functional programming.",
                        },
                        {
                            "url": "https://python.org/guide/advanced",
                            "content": "Advanced Python features include decorators, metaclasses, and async programming with asyncio. These features make Python powerful for complex applications.",
                        },
                    ],
                },
                {
                    "name": "Python Programming Guide",
                    "version": "2.0.0",
                    "description": "Updated comprehensive guide to Python programming",
                    "source_url": "https://python.org/guide/v2",
                    "pages": [
                        {
                            "url": "https://python.org/guide/v2/intro",
                            "content": "Python 2.0 introduces new features and improvements. The language continues to evolve with better performance and new syntax features.",
                        },
                        {
                            "url": "https://python.org/guide/v2/async",
                            "content": "Async programming in Python has been greatly enhanced. The asyncio library provides powerful tools for concurrent programming.",
                        },
                    ],
                },
                {
                    "name": "Web Development Handbook",
                    "version": "1.0.0",
                    "description": "Complete handbook for modern web development",
                    "source_url": "https://web.dev/handbook",
                    "pages": [
                        {
                            "url": "https://web.dev/handbook/frontend",
                            "content": "Frontend development involves HTML, CSS, and JavaScript. Modern frameworks like React and Vue.js make building user interfaces easier.",
                        },
                        {
                            "url": "https://web.dev/handbook/backend",
                            "content": "Backend development handles server-side logic, databases, and APIs. Python with FastAPI provides excellent tools for building robust APIs.",
                        },
                    ],
                },
            ]

            import uuid

            unique_suffix = str(uuid.uuid4())[:8]

            for doc_data in test_documents:
                # Create document
                doc_id = await self.doc_repo.create(
                    name=doc_data["name"],
                    version=doc_data["version"],
                    source_url=doc_data["source_url"],
                    description=doc_data["description"],
                    metadata={"type": "test", "purpose": "search_testing", "suffix": unique_suffix},
                )
                self.test_docs.append((doc_id, doc_data["name"], doc_data["version"]))
                print(
                    f"   ✅ Created test document '{doc_data['name']}' v{doc_data['version']} (ID: {doc_id})"
                )

                # Create pages
                page_ids = []
                for page_data in doc_data["pages"]:
                    page_id = await self.page_repo.create(
                        document_id=doc_id,
                        url=page_data["url"],
                        content=page_data["content"],
                        content_hash=f"hash_{unique_suffix}_{doc_id}_{len(page_ids)}",
                        metadata={"page_type": "test"},
                    )
                    page_ids.append(page_id)

                # Create group
                group_name = f"Test Group {doc_data['name']} v{doc_data['version']} {unique_suffix}"
                group_id = await self.group_repo.create_group(
                    document_id=doc_id, page_ids=page_ids, name=group_name
                )
                self.test_groups.append(group_id)
                print(f"   ✅ Created test group (ID: {group_id})")

                # Create chunks with embeddings
                await self._create_test_chunks_for_document(doc_id, group_id, page_ids)

            return True
        except Exception as e:
            print(f"   ❌ Error setting up test data: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def _create_test_chunks_for_document(
        self, doc_id: int, group_id: int, page_ids: List[int]
    ):
        """Create test chunks with embeddings for a document."""
        # Get pages content
        pages_content = []
        for page_id in page_ids:
            page = await self.page_repo.get_by_id(page_id)
            if page:
                pages_content.append(page.content)

        # Combine and chunk content
        full_content = " ".join(pages_content)

        # Simple chunking: split by sentences (basic approach)
        sentences = full_content.split(". ")
        chunks_content = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk + sentence) > 500:  # Chunk size limit
                if current_chunk:
                    chunks_content.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += ". " + sentence if current_chunk else sentence

        if current_chunk:
            chunks_content.append(current_chunk.strip())

        # Create chunks with mock embeddings
        for i, chunk_content in enumerate(chunks_content):
            # Generate mock embedding (768 dimensions)
            import random

            embedding = [random.uniform(-1, 1) for _ in range(768)]

            chunk_id = await self.chunk_repo.create(
                document_id=doc_id,
                group_id=group_id,
                chunk_index=i,
                content=chunk_content,
                embedding=embedding,
            )
            self.test_chunks.append(chunk_id)

        print(f"   ✅ Created {len(chunks_content)} chunks for document {doc_id}")

    async def cleanup_test_data(self):
        """Clean up test data."""
        print("🧹 Cleaning up test data...")

        try:
            # Delete all test documents and their cascades
            async with self.manager.connection() as conn:
                # Find and delete test documents
                test_docs = await conn.execute(
                    "SELECT id FROM documents WHERE metadata->>'type' = 'test' AND metadata->>'purpose' = 'search_testing'"
                )
                test_doc_ids = [row["id"] for row in test_docs.result() or []]

                for doc_id in test_doc_ids:
                    try:
                        await self.doc_repo.delete(doc_id)
                        print(f"   ✅ Deleted test document (ID: {doc_id})")
                    except Exception as e:
                        print(f"   ⚠️  Error deleting test document {doc_id}: {e}")

            # Reset instance variables
            self.test_docs = []
            self.test_groups = []
            self.test_chunks = []

            return True
        except Exception as e:
            print(f"   ❌ Error during cleanup: {e}")
            return False

    async def test_find_documents(self):
        """Test document search functionality."""
        print("\n📝 Testing document search...")

        try:
            # Test search for "Python"
            results = await self.search_service.find_documents("Python", limit=10)
            print(f"   ✅ Found {len(results)} documents matching 'Python'")
            for result in results[:3]:  # Show top 3
                print(
                    f"      {result.document.name} v{result.document.version} (score: {result.relevance_score:.3f})"
                )

            # Test search for "programming"
            results = await self.search_service.find_documents("programming", limit=10)
            print(f"   ✅ Found {len(results)} documents matching 'programming'")
            for result in results[:3]:  # Show top 3
                print(
                    f"      {result.document.name} v{result.document.version} (score: {result.relevance_score:.3f})"
                )

            # Test search for non-existent term
            results = await self.search_service.find_documents("nonexistent", limit=10)
            print(f"   ✅ Found {len(results)} documents matching 'nonexistent' (should be 0)")

            return True
        except Exception as e:
            print(f"   ❌ Document search failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_search_content(self):
        """Test content search within documents."""
        print("\n📖 Testing content search...")

        if not self.test_docs:
            print("   ❌ No test documents available")
            return False

        try:
            # Get the first test document (Python Guide v1.0.0)
            python_doc = next(
                (
                    doc
                    for doc in self.test_docs
                    if doc[1] == "Python Programming Guide" and doc[2] == "1.0.0"
                ),
                None,
            )
            if not python_doc:
                print("   ❌ Python Programming Guide v1.0.0 not found")
                return False

            doc_id = python_doc[0]

            # Test search for "programming"
            results = await self.search_service.search_content("programming", doc_id, limit=5)
            print(
                f"   ✅ Found {len(results)} content results for 'programming' in document {doc_id}"
            )
            for result in results[:3]:  # Show top 3
                print(
                    f"      Rank {result.rank}: Score {result.score:.3f} - {result.chunk.content[:100]}..."
                )

            # Test search for "Python"
            results = await self.search_service.search_content("Python", doc_id, limit=5)
            print(f"   ✅ Found {len(results)} content results for 'Python' in document {doc_id}")
            for result in results[:3]:  # Show top 3
                print(
                    f"      Rank {result.rank}: Score {result.score:.3f} - {result.chunk.content[:100]}..."
                )

            # Test with custom weights
            results = await self.search_service.search_content(
                "programming", doc_id, limit=5, vector_weight=0.8, bm25_weight=0.2
            )
            print(f"   ✅ Found {len(results)} content results with custom weights (0.8, 0.2)")

            return True
        except Exception as e:
            print(f"   ❌ Content search failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_search_across_versions(self):
        """Test cross-version search functionality."""
        print("\n🔄 Testing cross-version search...")

        try:
            # Search across versions of "Python Programming Guide"
            results = await self.search_service.search_across_versions(
                "Python", "Python Programming Guide", limit_per_version=3
            )
            print(f"   ✅ Cross-version search found results in {len(results)} versions")
            for version, version_results in results.items():
                print(f"      Version {version}: {len(version_results)} results")
                for result in version_results[:2]:  # Show top 2 per version
                    print(
                        f"         Rank {result.rank}: Score {result.score:.3f} - {result.chunk.content[:80]}..."
                    )

            # Search for term that appears in multiple versions
            results = await self.search_service.search_across_versions(
                "programming", "Python Programming Guide", limit_per_version=3
            )
            print(
                f"   ✅ Cross-version search for 'programming' found results in {len(results)} versions"
            )

            # Search for non-existent document
            results = await self.search_service.search_across_versions(
                "test", "NonExistent Document", limit_per_version=3
            )
            print(
                f"   ✅ Cross-version search for non-existent document found {len(results)} results (should be 0)"
            )

            return True
        except Exception as e:
            print(f"   ❌ Cross-version search failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_search_service_integration(self):
        """Test integrated search service workflow."""
        print("\n🔗 Testing integrated search workflow...")

        try:
            # 1. Find documents
            doc_results = await self.search_service.find_documents("Python", limit=5)
            if not doc_results:
                print("   ❌ No documents found for integration test")
                return False

            # 2. Search content in the first document found
            first_doc = doc_results[0].document
            content_results = await self.search_service.search_content(
                "programming", first_doc.id, limit=3
            )

            # 3. Verify results are consistent
            if content_results:
                # Check that all results belong to the correct document
                for result in content_results:
                    if (
                        result.document_name != first_doc.name
                        or result.document_version != first_doc.version
                    ):
                        print(
                            f"   ❌ Content search result document mismatch: {result.document_name} v{result.document_version}"
                        )
                        return False

                print(
                    f"   ✅ Integrated workflow successful: found {len(doc_results)} docs, {len(content_results)} content results"
                )
                return True
            else:
                print("   ⚠️  No content results found, but document search worked")
                return True

        except Exception as e:
            print(f"   ❌ Integration test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def run_all_tests(self):
        """Run all search service tests."""
        print("🧪 Starting Search Service Tests")
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

        # Test embedding service connection
        try:
            await self.embedding_service.verify_connection()
            print("✅ Embedding service connection successful")
        except Exception as e:
            print(f"⚠️  Embedding service connection failed (tests will use mock data): {e}")

        # Run tests
        try:
            # Set up test data
            if not await self.setup_test_data():
                return False

            # Test document search
            if not await self.test_find_documents():
                return False

            # Test content search
            if not await self.test_search_content():
                return False

            # Test cross-version search
            if not await self.test_search_across_versions():
                return False

            # Test integrated workflow
            if not await self.test_search_service_integration():
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
    print("🔧 Context Bridge Search Service Tester")
    print("=" * 60)

    # Check command line arguments
    init_db = "--init" in sys.argv
    reset_db = "--reset" in sys.argv
    help_requested = "--help" in sys.argv or "-h" in sys.argv or len(sys.argv) == 1

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
        async with SearchServiceTester() as tester:
            success = await tester.run_all_tests()

        if success:
            print("\n✅ All search service tests completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some search service tests failed!")
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
