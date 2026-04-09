#!/usr/bin/env python3
"""
Simple test data setup for search functionality testing.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge import ContextBridge


async def create_test_data():
    """Create test document for search testing."""
    print("🔧 Creating test data for search functionality...")

    bridge = ContextBridge()
    await bridge.initialize()

    try:
        # Create a test document by crawling a simple page
        print("📄 Creating test document...")
        crawl_result = await bridge.crawl_documentation(
            name="test_docs",
            version="1.0.0",
            source_url="https://example.com",
            description="Test documentation for search functionality",
        )
        doc_id = crawl_result.document_id
        print(f"✅ Created document with ID: {doc_id}")

        # List pages to see what was crawled
        pages = await bridge.list_pages(doc_id)
        print(f"📄 Found {len(pages)} pages")

        # Process pages into chunks via group creation
        if pages:
            print("🔄 Creating group for pages...")
            page_ids = [p.id for p in pages]
            group_result = await bridge.create_group(
                document_id=doc_id, page_ids=page_ids, name="test_docs_group"
            )
            print(f"✅ Created group with ID: {group_result.get('group_id', 'N/A')}")

        print("🎉 Test data creation complete!")
        print("   You can now test search functionality in the Streamlit app")

    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await bridge.close()


if __name__ == "__main__":
    asyncio.run(create_test_data())
