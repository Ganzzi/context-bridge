"""
Pattern 1: Direct Python Configuration

This is the RECOMMENDED pattern for package users and production applications.

Advantages:
- ✅ Explicit: Configuration is visible in your code
- ✅ Type-safe: Full IDE autocomplete and type hints
- ✅ No dependencies: Doesn't require python-dotenv
- ✅ Easy to test: Pass different configs for different scenarios
- ✅ Production-ready: Works in all environments (local, Docker, K8s, etc.)
"""

import asyncio
from context_bridge import ContextBridge, Config


async def main():
    # Create configuration explicitly
    config = Config(
        # PostgreSQL connection
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="postgres",
        postgres_password="secure_password_123",
        postgres_db="context_bridge",
        # Connection pooling
        postgres_max_pool_size=10,
        # Embedding configuration
        ollama_base_url="http://localhost:11434",
        embedding_model="nomic-embed-text:latest",
        vector_dimension=768,
        # Search configuration
        similarity_threshold=0.7,
        bm25_weight=0.3,
        vector_weight=0.7,
        # Chunking configuration
        chunk_size=2000,
        min_combined_content_size=100,
        max_combined_content_size=3500000,
        # Crawling configuration
        crawl_max_depth=3,
        crawl_max_concurrent=10,
    )

    print("=" * 70)
    print("Pattern 1: Direct Python Configuration")
    print("=" * 70)
    print(f"\nConfiguration loaded:")
    print(f"  Database: {config.postgres_db}@{config.postgres_host}:{config.postgres_port}")
    print(f"  Embedding Model: {config.embedding_model}")
    print(f"  Ollama URL: {config.ollama_base_url}")
    print(f"  Vector Dimension: {config.vector_dimension}")
    print(f"  Chunk Size: {config.chunk_size}")

    # Initialize ContextBridge with explicit config
    async with ContextBridge(config=config) as bridge:
        print("\n✅ ContextBridge initialized successfully!")

        # Check health
        health = await bridge.health_check()
        print(f"\nHealth status:")
        for key, value in health.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
