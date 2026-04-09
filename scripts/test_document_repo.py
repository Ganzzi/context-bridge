#!/usr/bin/env python3
"""
Document Repository Database Testing Script.

This script provides comprehensive testing of the DocumentRepository
with a real PostgreSQL database. It tests all CRUD operations and
search functionality using PSQLPy best practices.

Usage:
    python scripts/test_document_repo.py          # Run all tests
    python scripts/test_document_repo.py --init   # Initialize database first
    python scripts/test_document_repo.py --reset  # Reset database before testing
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


class DocumentRepoTester:
    """
    Test class for DocumentRepository operations with real database.

    This class provides integration tests for all DocumentRepository
    methods using a real PostgreSQL connection.
    """

    def __init__(self):
        self.config = get_config()
        self.manager = PostgreSQLManager(self.config)
        self.repo = DocumentRepository(self.manager)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.manager.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.manager.close()

    async def cleanup_existing_test_data(self):
        """
        Clean up any existing test documents before running tests.

        Returns:
            True if cleanup succeeded, False otherwise
        """
        print("🧹 Cleaning up existing test data...")

        try:
            # Get all documents
            docs = await self.repo.list_all(limit=1000)
            print(f"   Found {len(docs)} total documents in database")

            # Delete test documents by name
            test_doc_names = ["Python Guide", "FastAPI Tutorial", "PostgreSQL Manual"]
            deleted_count = 0

            for doc in docs:
                if doc.name in test_doc_names:
                    success = await self.repo.delete(doc.id)
                    if success:
                        deleted_count += 1
                        print(f"   Deleted: '{doc.name}' v{doc.version} (ID {doc.id})")

            print(f"   ✅ Cleaned up {deleted_count} existing test documents")
            return True
        except Exception as e:
            print(f"   ❌ Error during cleanup: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_create_documents(self):
        """Test document creation."""
        print("\n📝 Testing document creation...")

        # Test data
        docs = [
            {
                "name": "Python Guide",
                "version": "1.0.0",
                "source_url": "https://docs.python.org/3/",
                "description": "Official Python documentation",
                "metadata": {"language": "python", "type": "documentation"},
            },
            {
                "name": "FastAPI Tutorial",
                "version": "0.1.0",
                "source_url": "https://fastapi.tiangolo.com/",
                "description": "FastAPI web framework tutorial",
                "metadata": {"framework": "fastapi", "type": "tutorial"},
            },
            {
                "name": "PostgreSQL Manual",
                "version": "15.0",
                "source_url": "https://www.postgresql.org/docs/",
                "description": "PostgreSQL database manual",
                "metadata": {"database": "postgresql", "type": "manual"},
            },
        ]

        created_ids = []
        for doc_data in docs:
            try:
                doc_id = await self.repo.create(**doc_data)
                created_ids.append(doc_id)
                print(
                    f"   ✅ Created document '{doc_data['name']}' v{doc_data['version']} (ID: {doc_id})"
                )
            except Exception as e:
                print(f"   ❌ Failed to create '{doc_data['name']}': {e}")
                return False

        return created_ids

    async def test_retrieve_documents(self, doc_ids):
        """Test document retrieval."""
        print("\n📖 Testing document retrieval...")

        # Test get_by_id
        for doc_id in doc_ids:
            try:
                doc = await self.repo.get_by_id(doc_id)
                if doc:
                    print(f"   ✅ Retrieved document ID {doc_id}: '{doc.name}' v{doc.version}")
                else:
                    print(f"   ❌ Document ID {doc_id} not found")
                    return False
            except Exception as e:
                print(f"   ❌ Error retrieving document {doc_id}: {e}")
                return False

        # Test get_by_name_version
        try:
            doc = await self.repo.get_by_name_version("Python Guide", "1.0.0")
            if doc:
                print(f"   ✅ Retrieved by name/version: '{doc.name}' v{doc.version}")
            else:
                print("   ❌ Document not found by name/version")
                return False
        except Exception as e:
            print(f"   ❌ Error retrieving by name/version: {e}")
            return False

        return True

    async def test_search_documents(self):
        """Test document search functionality."""
        print("\n🔍 Testing document search...")

        # Test search by name
        try:
            results = await self.repo.find_by_query("Python")
            print(f"   ✅ Found {len(results)} documents matching 'Python'")
            for doc in results:
                print(f"      - {doc.name} v{doc.version}")
        except Exception as e:
            print(f"   ❌ Error searching for 'Python': {e}")
            return False

        # Test search by description
        try:
            results = await self.repo.find_by_query("tutorial")
            print(f"   ✅ Found {len(results)} documents matching 'tutorial'")
            for doc in results:
                print(f"      - {doc.name}: {doc.description}")
        except Exception as e:
            print(f"   ❌ Error searching for 'tutorial': {e}")
            return False

        # Test search with custom fields
        try:
            results = await self.repo.find_by_query("docs.python.org", search_fields=["source_url"])
            print(f"   ✅ Found {len(results)} documents with URL containing 'docs.python.org'")
        except Exception as e:
            print(f"   ❌ Error searching URLs: {e}")
            return False

        return True

    async def test_list_operations(self):
        """Test list and pagination operations."""
        print("\n📋 Testing list operations...")

        # Test list_all
        try:
            docs = await self.repo.list_all(limit=10)
            print(f"   ✅ Listed {len(docs)} documents (limit 10)")
            for doc in docs:
                print(f"      - {doc.name} v{doc.version}")
        except Exception as e:
            print(f"   ❌ Error listing documents: {e}")
            return False

        # Test list_versions
        try:
            versions = await self.repo.list_versions("Python Guide")
            print(f"   ✅ Found versions for 'Python Guide': {versions}")
        except Exception as e:
            print(f"   ❌ Error listing versions: {e}")
            return False

        return True

    async def test_update_documents(self, doc_ids):
        """Test document updates."""
        print("\n✏️  Testing document updates...")

        if not doc_ids:
            print("   ⚠️  No documents to update")
            return True

        # Update first document
        doc_id = doc_ids[0]
        try:
            success = await self.repo.update(
                doc_id,
                description="Updated Python documentation",
                metadata={"language": "python", "type": "documentation", "updated": True},
            )
            if success:
                print(f"   ✅ Updated document ID {doc_id}")
            else:
                print(f"   ❌ Failed to update document ID {doc_id}")
                return False
        except Exception as e:
            print(f"   ❌ Error updating document {doc_id}: {e}")
            return False

        # Verify update
        try:
            doc = await self.repo.get_by_id(doc_id)
            if doc and "updated" in doc.metadata:
                print(f"   ✅ Verified update: metadata contains 'updated' flag")
            else:
                print("   ❌ Update verification failed")
                return False
        except Exception as e:
            print(f"   ❌ Error verifying update: {e}")
            return False

        return True

    async def test_delete_documents(self, doc_ids):
        """Test document deletion."""
        print("\n🗑️  Testing document deletion...")

        if not doc_ids:
            print("   ⚠️  No documents to delete")
            return True

        # Delete first document
        doc_id = doc_ids[0]
        try:
            success = await self.repo.delete(doc_id)
            if success:
                print(f"   ✅ Deleted document ID {doc_id}")
            else:
                print(f"   ❌ Failed to delete document ID {doc_id}")
                return False
        except Exception as e:
            print(f"   ❌ Error deleting document {doc_id}: {e}")
            return False

        # Verify deletion
        try:
            doc = await self.repo.get_by_id(doc_id)
            if doc is None:
                print(f"   ✅ Verified deletion: document {doc_id} no longer exists")
            else:
                print(f"   ❌ Deletion verification failed: document {doc_id} still exists")
                return False
        except Exception as e:
            print(f"   ❌ Error verifying deletion: {e}")
            return False

        return True

    async def cleanup_test_documents(self):
        """Clean up test documents after testing."""
        print("\n🧹 Cleaning up test documents...")

        try:
            # Get all documents
            docs = await self.repo.list_all(limit=100)

            # Delete test documents
            deleted_count = 0
            for doc in docs:
                if doc.name in ["Python Guide", "FastAPI Tutorial", "PostgreSQL Manual"]:
                    await self.repo.delete(doc.id)
                    deleted_count += 1

            print(f"   ✅ Cleaned up {deleted_count} test documents")
            return True
        except Exception as e:
            print(f"   ❌ Error during cleanup: {e}")
            return False

    async def run_all_tests(self):
        """Run all document repository tests."""
        print("🧪 Starting Document Repository Tests")
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
            # Clean up existing test data first
            if not await self.cleanup_existing_test_data():
                return False

            # Create test documents
            doc_ids = await self.test_create_documents()
            if not doc_ids:
                return False

            # Test retrieval
            if not await self.test_retrieve_documents(doc_ids):
                return False

            # Test search
            if not await self.test_search_documents():
                return False

            # Test list operations
            if not await self.test_list_operations():
                return False

            # Test updates
            if not await self.test_update_documents(doc_ids):
                return False

            # Test deletion
            if not await self.test_delete_documents(doc_ids):
                return False

            # Clean up remaining documents
            await self.cleanup_test_documents()

            print("\n" + "=" * 50)
            print("🎉 All Document Repository tests passed!")
            return True

        except Exception as e:
            print(f"\n❌ Test suite failed with error: {e}")
            return False


async def initialize_database():
    """Initialize the database schema."""
    print("🚀 Initializing database schema...")

    from context_bridge.database.init_databases import init_postgresql

    try:
        await init_postgresql()
        print("✅ Database initialization completed!")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


async def reset_database():
    """Reset the database."""
    print("🗑️  Resetting database...")

    from context_bridge.database.init_databases import reset_database

    try:
        await reset_database()
        print("✅ Database reset completed!")
        return True
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        return False


async def main():
    """Main entry point."""
    print("🔧 Context Bridge Document Repository Tester")
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
        async with DocumentRepoTester() as tester:
            success = await tester.run_all_tests()

        if success:
            print("\n✅ All tests completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
