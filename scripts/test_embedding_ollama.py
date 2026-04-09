#!/usr/bin/env python3
"""
Test script for EmbeddingService with Ollama.

This script demonstrates how to use the EmbeddingService to generate embeddings
for text using the Ollama API. It includes basic testing and verification.
"""

import asyncio
import logging
from context_bridge.config import Config
from context_bridge.service.embedding import EmbeddingService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main test function."""
    print("Testing EmbeddingService with Ollama...")

    # Initialize configuration
    config = Config()

    # Create embedding service
    service = EmbeddingService(config)

    # Verify connection and model availability
    print("Verifying Ollama connection...")
    connection_ok = await service.verify_connection()
    if not connection_ok:
        print("❌ Ollama connection or model not available. Please check your Ollama setup.")
        return

    print("✅ Ollama connection verified.")

    # Test model availability with a real embedding
    print("Testing model availability...")
    model_ok = await service.ensure_model_available()
    if not model_ok:
        print("❌ Model is not working properly.")
        return

    print("✅ Model is available and working.")

    # Test embedding generation
    test_texts = [
        "Hello world",
        "This is a test sentence for embedding generation.",
        "Ollama provides local AI models for various tasks.",
    ]

    print("\nGenerating embeddings for test texts...")
    for text in test_texts:
        try:
            embedding = await service.get_embedding(text)
            print(f"✅ Text: '{text[:50]}...' -> Embedding dimension: {len(embedding)}")
            print(f"   Sample values: {embedding[:5]}...")
        except Exception as e:
            print(f"❌ Failed to generate embedding for '{text[:50]}...': {e}")

    # Test batch embedding
    print("\nTesting batch embedding generation...")
    try:
        embeddings = await service.get_embeddings_batch(test_texts, batch_size=2)
        print(f"✅ Generated {len(embeddings)} embeddings in batch")
        for i, emb in enumerate(embeddings):
            print(f"   Text {i+1}: dimension {len(emb)}")
    except Exception as e:
        print(f"❌ Batch embedding failed: {e}")

    # Show cache stats if enabled
    cache_stats = service.get_cache_stats()
    if cache_stats["enabled"]:
        print(f"\nCache stats: {cache_stats}")

    print("\n🎉 Embedding tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
