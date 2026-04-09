"""
Integration tests for EmbeddingService.

Tests embedding generation with real Ollama API calls.
These tests require Ollama to be running with the nomic-embed-text model.
"""

import pytest
import asyncio
from context_bridge.service.embedding import EmbeddingService
from context_bridge.config import Config


@pytest.fixture
def real_config():
    """Create a real configuration for integration testing."""
    return Config()


@pytest.fixture
async def embedding_service(real_config):
    """Create an embedding service instance for integration testing."""
    service = EmbeddingService(real_config, enable_cache=True, max_cache_size=10)

    # Verify connection before running tests
    connection_ok = await service.verify_connection()
    if not connection_ok:
        pytest.skip(
            "Ollama is not running or model is not available. "
            "Start Ollama and run: ollama pull nomic-embed-text"
        )

    # Verify model is working
    model_ok = await service.ensure_model_available()
    if not model_ok:
        pytest.skip("Model is not working properly")

    return service


@pytest.mark.integration
class TestEmbeddingServiceIntegration:
    """Integration tests for EmbeddingService with real Ollama."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_embedding_real_api(self, embedding_service):
        """Test embedding generation with real Ollama API."""
        text = "This is a test sentence for embedding generation."

        embedding = await embedding_service.get_embedding(text)

        assert isinstance(embedding, list)
        assert len(embedding) == 768  # Expected dimension
        assert all(isinstance(x, float) for x in embedding)
        assert sum(embedding) != 0  # Should not be zero vector

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_embedding_caching_integration(self, embedding_service):
        """Test caching functionality with real API calls."""
        text = "Test text for caching functionality."

        # First call should hit API
        embedding1 = await embedding_service.get_embedding(text)
        stats_after_first = embedding_service.get_cache_stats()

        assert stats_after_first["misses"] == 1
        assert stats_after_first["hits"] == 0

        # Second call should use cache
        embedding2 = await embedding_service.get_embedding(text)
        stats_after_second = embedding_service.get_cache_stats()

        assert stats_after_second["misses"] == 1
        assert stats_after_second["hits"] == 1
        assert embedding1 == embedding2  # Should be identical

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_embeddings_batch_real_api(self, embedding_service):
        """Test batch embedding generation with real API."""
        texts = [
            "First test sentence.",
            "Second test sentence with different content.",
            "Third sentence for batch processing.",
            "Fourth and final test sentence.",
        ]

        embeddings = await embedding_service.get_embeddings_batch(texts, batch_size=2)

        assert len(embeddings) == len(texts)
        for embedding in embeddings:
            assert isinstance(embedding, list)
            assert len(embedding) == 768
            assert all(isinstance(x, float) for x in embedding)
            assert sum(embedding) != 0  # Should not be zero vector

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_embedding_empty_text_integration(self, embedding_service):
        """Test embedding generation with empty text in integration."""
        embedding = await embedding_service.get_embedding("")

        assert embedding == [0.0] * 768

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_embedding_whitespace_text_integration(self, embedding_service):
        """Test embedding generation with whitespace-only text in integration."""
        embedding = await embedding_service.get_embedding("   \n\t  ")

        assert embedding == [0.0] * 768

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cache_stats_integration(self, embedding_service):
        """Test cache statistics with real API calls."""
        # Clear cache first
        embedding_service.clear_cache()

        texts = ["text1", "text2", "text1"]  # text1 appears twice

        for text in texts:
            await embedding_service.get_embedding(text)

        stats = embedding_service.get_cache_stats()

        assert stats["enabled"] is True
        assert stats["size"] == 2  # text1 and text2
        assert stats["hits"] == 1  # Second occurrence of text1
        assert stats["misses"] == 2  # text1 and text2 first occurrences
        assert stats["hit_rate"] == 0.3333333333333333  # 1/3

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cache_eviction_integration(self, embedding_service):
        """Test cache eviction when max size is reached."""
        # Set small cache size
        embedding_service.max_cache_size = 2

        # Fill cache
        texts = ["text1", "text2", "text3"]  # This should evict text1

        for text in texts:
            await embedding_service.get_embedding(text)

        stats = embedding_service.get_cache_stats()

        # Should have evicted one entry
        assert stats["size"] <= 2
        assert stats["misses"] == 3  # All were misses due to eviction

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_verify_connection_integration(self, embedding_service):
        """Test connection verification with real API."""
        result = await embedding_service.verify_connection()
        assert result is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ensure_model_available_integration(self, embedding_service):
        """Test model availability check with real API."""
        result = await embedding_service.ensure_model_available()
        assert result is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self, embedding_service):
        """Test configuration validation."""
        errors = embedding_service.validate_configuration()
        assert isinstance(errors, list)
        assert len(errors) == 0  # Should have no errors with valid config

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_embedding_consistency(self, embedding_service):
        """Test that same text produces consistent embeddings."""
        text = "This is a consistency test sentence."
        embedding1 = await embedding_service.get_embedding(text)
        embedding2 = await embedding_service.get_embedding(text)

        # Should be identical (from cache)
        assert embedding1 == embedding2

        # Should have expected properties
        assert len(embedding1) == 768
        assert all(-1 <= x <= 1 for x in embedding1)  # Embeddings typically in [-1, 1]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_different_texts_different_embeddings(self, embedding_service):
        """Test that different texts produce different embeddings."""
        text1 = "The cat sits on the mat."
        text2 = "The dog runs in the park."

        embedding1 = await embedding_service.get_embedding(text1)
        embedding2 = await embedding_service.get_embedding(text2)

        # Should be different
        assert embedding1 != embedding2

        # But should have same structure
        assert len(embedding1) == len(embedding2) == 768

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_large_batch_processing(self, embedding_service):
        """Test processing a larger batch of texts."""
        texts = [f"Test sentence number {i} for batch processing." for i in range(10)]

        embeddings = await embedding_service.get_embeddings_batch(texts, batch_size=3)

        assert len(embeddings) == 10
        for embedding in embeddings:
            assert len(embedding) == 768
            assert sum(embedding) != 0
