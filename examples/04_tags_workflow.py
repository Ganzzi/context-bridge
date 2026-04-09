"""
Example: Complete Document Lifecycle with Tag Management (v0.3+)

Demonstrates the full workflow of using Context Bridge with tag management:
1. Crawling documentation from URLs
2. Creating custom tags for domain-specific organization
3. Assigning tags to documents for better organization
4. Creating groups and processing chunks
5. Searching with tagged context

Prerequisites:
- PostgreSQL running with pgvector and vchord_bm25 extensions
- Ollama running (or Google API key configured for embeddings)
- context-bridge installed: pip install context-bridge

Usage:
    python examples/04_tags_workflow.py

Configuration:
    Set environment variables or create .env file:
    - POSTGRES_HOST (default: localhost)
    - POSTGRES_PASSWORD (required)
    - OLLAMA_BASE_URL (default: http://localhost:11434)
    - EMBEDDING_MODEL (default: nomic-embed-text:latest)
"""

import asyncio
import logging
from context_bridge import ContextBridge, TagCategory

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Execute the complete tag workflow example."""

    try:
        # Initialize Context Bridge
        logger.info("🚀 Initializing Context Bridge...")
        async with ContextBridge() as bridge:
            logger.info("✅ Context Bridge initialized")

            # =================================================================
            # STEP 1: Crawl Documentation
            # =================================================================
            logger.info("\n📚 STEP 1: Crawling Documentation")
            logger.info("Crawling psqlpy documentation from GitHub...")

            result = await bridge.crawl_documentation(
                name="psqlpy",
                version="0.9.0",
                source_url="https://github.com/Ganzzi/psqlpy",
                description="Async PostgreSQL driver for Python with built-in connection pooling",
                max_depth=2,
            )

            doc_id = result.document_id
            logger.info(f"✅ Crawled {result.pages_stored} pages")
            logger.info(f"   Document ID: {doc_id}")
            logger.info(f"   Document: {result.document_name} v{result.document_version}")

            # =================================================================
            # STEP 2: List Existing Tags (Predefined)
            # =================================================================
            logger.info("\n🏷️  STEP 2: Exploring Available Tags")

            tech_tags = await bridge.list_tags(category=TagCategory.technology)
            logger.info(f"✅ Found {len(tech_tags)} technology tags")
            logger.info(f"   Examples: {', '.join([t.name for t in tech_tags[:5]])}")

            # =================================================================
            # STEP 3: Create Custom Tags
            # =================================================================
            logger.info("\n✨ STEP 3: Creating Custom Tags")

            custom_tags = [
                {
                    "name": "connection-pooling",
                    "category": TagCategory.technology,
                    "description": "Connection pool management and configuration",
                },
                {
                    "name": "async-python",
                    "category": TagCategory.technology,
                    "description": "Async/await patterns and concurrency",
                },
                {
                    "name": "database-optimization",
                    "category": TagCategory.custom,
                    "description": "Performance tuning and optimization tips",
                },
            ]

            created_tags = []
            for tag_data in custom_tags:
                try:
                    new_tag = await bridge.create_tag(
                        name=tag_data["name"],
                        category=tag_data["category"],
                        description=tag_data["description"],
                    )
                    created_tags.append(new_tag)
                    logger.info(f"✅ Created tag: {new_tag.name} (ID: {new_tag.id})")
                except ValueError as e:
                    # Tag might already exist
                    logger.warning(f"⚠️  Could not create tag {tag_data['name']}: {e}")
                    # Try to find existing tag
                    all_tags = await bridge.list_tags()
                    existing = next((t for t in all_tags if t.name == tag_data["name"]), None)
                    if existing:
                        created_tags.append(existing)
                        logger.info(f"   Using existing tag: {existing.name} (ID: {existing.id})")

            # =================================================================
            # STEP 4: Assign Tags to Document
            # =================================================================
            logger.info("\n📌 STEP 4: Assigning Tags to Document")

            # Combine custom tags with some predefined ones
            tag_ids_to_assign = [t.id for t in created_tags[:3]]

            if tech_tags:
                # Add a few relevant technology tags
                tag_ids_to_assign.extend([t.id for t in tech_tags[:2]])

            # Remove duplicates
            tag_ids_to_assign = list(set(tag_ids_to_assign))

            logger.info(f"Assigning {len(tag_ids_to_assign)} tags...")
            assigned_count = await bridge.add_tags_to_document(
                document_id=doc_id, tag_ids=tag_ids_to_assign
            )
            logger.info(f"✅ Assigned {assigned_count} tags to document")

            # =================================================================
            # STEP 5: Verify Tagged Document
            # =================================================================
            logger.info("\n🔍 STEP 5: Verifying Tagged Document")

            document_tags = await bridge.get_document_tags(doc_id)
            logger.info(f"✅ Document has {len(document_tags)} tags:")
            for tag in sorted(document_tags, key=lambda t: t.name):
                logger.info(
                    f"   - {tag.name} ({tag.category.value}): {tag.description or 'No description'}"
                )

            # =================================================================
            # STEP 6: Get Document Pages
            # =================================================================
            logger.info("\n📖 STEP 6: Getting Crawled Pages")

            pages = await bridge.list_pages(doc_id, limit=100)
            logger.info(f"✅ Retrieved {len(pages)} pages")

            if pages:
                logger.info(f"   First page: {pages[0].title or 'Untitled'}")
                if len(pages) > 1:
                    logger.info(f"   Last page: {pages[-1].title or 'Untitled'}")

            # =================================================================
            # STEP 7: Create Group and Process Pages
            # =================================================================
            logger.info("\n👥 STEP 7: Creating Group for Chunking")

            if len(pages) >= 5:
                # Use first 20 pages or all if less
                page_ids = [p.id for p in pages[: min(20, len(pages))]]

                logger.info(f"Creating group with {len(page_ids)} pages...")
                group_result = await bridge.create_group(
                    document_id=doc_id,
                    page_ids=page_ids,
                    name="initial-group",
                    context_enabled=False,  # Disable context generation for faster demo
                )

                logger.info(f"✅ Group created successfully")
                logger.info(f"   Group ID: {group_result['group_id']}")
                logger.info(f"   Status: {group_result['status']}")
                if "chunk_count" in group_result:
                    logger.info(f"   Chunks created: {group_result['chunk_count']}")
            else:
                logger.warning(f"⚠️  Not enough pages ({len(pages)}) to create a group (minimum 5)")

            # =================================================================
            # STEP 8: Document Organization Summary
            # =================================================================
            logger.info("\n📊 STEP 8: Document Organization Summary")
            logger.info(
                f"""
✅ Workflow Complete!

Document Details:
  - Name: psqlpy v0.9.0
  - Document ID: {doc_id}
  - Pages Crawled: {len(pages)}
  - Tags Assigned: {len(document_tags)}

Tags Assigned:
{chr(10).join([f'  - {t.name}' for t in document_tags[:5]])}
{'  ...' if len(document_tags) > 5 else ''}

Next Steps:
1. Use search() to find content: await bridge.search("connection pooling", doc_id)
2. Access the Streamlit UI: streamlit run streamlit_app/app.py
3. Query via MCP Server for AI agent integration
4. Export results with tag filtering

📚 Document is now ready for RAG workflows!
            """
            )

    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        logger.info("Please ensure:")
        logger.info("  - PostgreSQL is running and extensions are installed")
        logger.info("  - POSTGRES_PASSWORD environment variable is set")
        logger.info("  - Ollama is running (or Google API key is configured)")
        raise
    except Exception as e:
        logger.error(f"❌ Error during workflow: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run the async workflow
    asyncio.run(main())
