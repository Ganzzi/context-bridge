"""
Unit tests for EmbeddingService.

Tests embedding generation, caching, retry logic, and error handling.
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from context_bridge.service.embedding import (
    EmbeddingService,
    EmbeddingError,
    EmbeddingConnectionError,
    EmbeddingTimeoutError,
    EmbeddingDimensionError,
)
from context_bridge.config import Config


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = MagicMock(spec=Config)
    config.ollama_base_url = "http://localhost:11434"
    config.embedding_model = "nomic-embed-text"
    config.vector_dimension = 768
    return config


@pytest.fixture
def embedding_service(mock_config):
    """Create an embedding service instance for testing."""
    return EmbeddingService(mock_config, enable_cache=True, max_cache_size=10)


class TestEmbeddingService:
    """Test cases for EmbeddingService."""

    def test_initialization(self, mock_config):
        """Test service initialization with different configurations."""
        service = EmbeddingService(mock_config)
        assert service.config == mock_config
        assert service.base_url == "http://localhost:11434"
        assert service.model == "nomic-embed-text"
        assert service.vector_dimension == 768
        assert service.enable_cache is True
        assert service.max_cache_size == 1000  # default

    def test_initialization_with_cache_disabled(self, mock_config):
        """Test service initialization with caching disabled."""
        service = EmbeddingService(mock_config, enable_cache=False)
        assert service.enable_cache is False
        assert not hasattr(service, "_embedding_cache")

    def test_cache_key_generation(self, embedding_service):
        """Test cache key generation for texts."""
        text1 = "Hello world"
        text2 = "Hello world"
        text3 = "Hello World"  # Different case

        key1 = embedding_service._get_cache_key(text1)
        key2 = embedding_service._get_cache_key(text2)
        key3 = embedding_service._get_cache_key(text3)

        assert key1 == key2  # Same text should have same key
        assert key1 != key3  # Different text should have different key
        assert len(key1) == 32  # MD5 hash length

    def test_dimension_validation(self, embedding_service):
        """Test embedding dimension validation."""
        # Valid dimension
        valid_embedding = [0.1] * 768
        embedding_service._validate_embedding_dimension(valid_embedding)  # Should not raise

        # Invalid dimension - too small
        with pytest.raises(EmbeddingDimensionError):
            embedding_service._validate_embedding_dimension([0.1] * 500)

        # Invalid dimension - too large
        with pytest.raises(EmbeddingDimensionError):
            embedding_service._validate_embedding_dimension([0.1] * 1000)

    @pytest.mark.asyncio
    async def test_get_embedding_empty_text(self, embedding_service):
        """Test get_embedding with empty text."""
        result = await embedding_service.get_embedding("")
        assert result == [0.0] * 768

        result = await embedding_service.get_embedding("   ")
        assert result == [0.0] * 768

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_get_embedding_success(self, mock_post, embedding_service):
        """Test successful embedding generation."""
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value.__aenter__.return_value = mock_response

        result = await embedding_service.get_embedding("test text")

        assert result == [0.1] * 768
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_get_embedding_caching(self, mock_post, embedding_service):
        """Test embedding caching functionality."""
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.json.return_value = {"embedding": [0.2] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value.__aenter__.return_value = mock_response

        # First call should hit API
        result1 = await embedding_service.get_embedding("test text")
        assert result1 == [0.2] * 768
        assert mock_post.call_count == 1

        # Second call should use cache
        result2 = await embedding_service.get_embedding("test text")
        assert result2 == [0.2] * 768
        assert mock_post.call_count == 1  # Still 1 call

        # Check cache stats
        stats = embedding_service.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    @pytest.mark.asyncio
    @patch.object(EmbeddingService, "_get_embedding_single_attempt")
    async def test_get_embedding_api_error_with_retry(self, mock_single_attempt, embedding_service):
        """Test embedding generation with API errors and retry logic."""
        # Mock API failure followed by success
        mock_single_attempt.side_effect = [
            aiohttp.ClientError("Connection failed"),  # First attempt fails
            aiohttp.ClientError("Connection failed"),  # Second attempt fails
            [0.3] * 768,  # Third attempt succeeds
        ]

        result = await embedding_service.get_embedding("test text")

        assert result == [0.3] * 768
        assert mock_single_attempt.call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_get_embedding_timeout_error(self, mock_post, embedding_service):
        """Test embedding generation with timeout errors."""
        mock_post.return_value.__aenter__.side_effect = asyncio.TimeoutError()

        with pytest.raises(EmbeddingTimeoutError):
            await embedding_service.get_embedding("test text")

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_get_embedding_connection_error(self, mock_post, embedding_service):
        """Test embedding generation with connection errors."""
        mock_post.return_value.__aenter__.side_effect = aiohttp.ClientError("Connection failed")

        # Should eventually raise EmbeddingConnectionError after retries
        with pytest.raises(EmbeddingConnectionError):
            await embedding_service.get_embedding("test text")

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_get_embedding_dimension_mismatch(self, mock_post, embedding_service):
        """Test embedding generation with dimension mismatch."""
        # Mock response with wrong dimension
        mock_response = AsyncMock()
        mock_response.json.return_value = {"embedding": [0.1] * 500}  # Wrong dimension
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value.__aenter__.return_value = mock_response

        with pytest.raises(EmbeddingDimensionError):
            await embedding_service.get_embedding("test text")

    @pytest.mark.asyncio
    async def test_get_embeddings_batch_empty(self, embedding_service):
        """Test batch embedding generation with empty input."""
        result = await embedding_service.get_embeddings_batch([])
        assert result == []

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_get_embeddings_batch_success(self, mock_post, embedding_service):
        """Test successful batch embedding generation."""
        # Mock successful API responses
        mock_response = AsyncMock()
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value.__aenter__.return_value = mock_response

        texts = ["text1", "text2", "text3"]
        result = await embedding_service.get_embeddings_batch(texts, batch_size=2)

        assert len(result) == 3
        assert all(len(emb) == 768 for emb in result)
        assert mock_post.call_count == 3  # 3 separate API calls

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_get_embeddings_batch_with_errors(self, mock_post, embedding_service):
        """Test batch embedding generation with some errors."""
        # Mock mixed responses: success, error, success
        mock_response_success1 = AsyncMock()
        mock_response_success1.json.return_value = {"embedding": [0.1] * 768}
        mock_response_success1.raise_for_status = MagicMock()

        mock_response_error = AsyncMock()
        mock_response_error.raise_for_status.side_effect = aiohttp.ClientError("Failed")

        mock_response_success2 = AsyncMock()
        mock_response_success2.json.return_value = {"embedding": [0.2] * 768}
        mock_response_success2.raise_for_status = MagicMock()

        mock_post.return_value.__aenter__.side_effect = [
            mock_response_success1,
            mock_response_error,
            mock_response_success2,
        ]

        texts = ["text1", "text2", "text3"]
        result = await embedding_service.get_embeddings_batch(texts, batch_size=1)

        assert len(result) == 3
        assert result[0] == [0.1] * 768  # Success
        assert result[1] == [0.0] * 768  # Error fallback
        assert result[2] == [0.2] * 768  # Success

    def test_cache_stats_disabled_cache(self, mock_config):
        """Test cache stats when caching is disabled."""
        service = EmbeddingService(mock_config, enable_cache=False)
        stats = service.get_cache_stats()
        assert stats == {"enabled": False}

    def test_cache_stats_enabled_cache(self, embedding_service):
        """Test cache stats when caching is enabled."""
        stats = embedding_service.get_cache_stats()
        assert stats["enabled"] is True
        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats
        assert "hit_rate" in stats

    def test_clear_cache(self, embedding_service):
        """Test cache clearing functionality."""
        # Add something to cache
        embedding_service._embedding_cache["test"] = [0.1] * 768
        embedding_service._cache_hits = 5
        embedding_service._cache_misses = 3

        embedding_service.clear_cache()

        assert len(embedding_service._embedding_cache) == 0
        assert embedding_service._cache_hits == 0
        assert embedding_service._cache_misses == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_verify_connection_success(self, mock_get, embedding_service):
        """Test successful connection verification."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "models": [{"name": "nomic-embed-text"}, {"name": "other-model"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await embedding_service.verify_connection()
        assert result is True

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_verify_connection_model_not_found(self, mock_get, embedding_service):
        """Test connection verification when model is not available."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"models": [{"name": "other-model"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await embedding_service.verify_connection()
        assert result is False

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_verify_connection_api_error(self, mock_get, embedding_service):
        """Test connection verification with API error."""
        mock_get.return_value.__aenter__.side_effect = aiohttp.ClientError("Connection failed")

        result = await embedding_service.verify_connection()
        assert result is False

    @pytest.mark.asyncio
    @patch.object(EmbeddingService, "get_embedding")
    async def test_ensure_model_available_success(self, mock_get_embedding, embedding_service):
        """Test successful model availability check."""
        mock_get_embedding.return_value = [0.1] * 768

        result = await embedding_service.ensure_model_available()
        assert result is True

    @pytest.mark.asyncio
    @patch.object(EmbeddingService, "get_embedding")
    async def test_ensure_model_available_zero_vector(self, mock_get_embedding, embedding_service):
        """Test model availability check with zero vector response."""
        mock_get_embedding.return_value = [0.0] * 768

        result = await embedding_service.ensure_model_available()
        assert result is False

    @pytest.mark.asyncio
    @patch.object(EmbeddingService, "get_embedding")
    async def test_ensure_model_available_error(self, mock_get_embedding, embedding_service):
        """Test model availability check with embedding error."""
        mock_get_embedding.side_effect = EmbeddingConnectionError("Connection failed")

        result = await embedding_service.ensure_model_available()
        assert result is False

    def test_validate_configuration_valid(self, mock_config):
        """Test configuration validation with valid config."""
        service = EmbeddingService(mock_config)
        errors = service.validate_configuration()
        assert errors == []

    def test_validate_configuration_invalid(self):
        """Test configuration validation with invalid config."""
        config = MagicMock(spec=Config)
        config.ollama_base_url = ""  # Invalid
        config.embedding_model = ""  # Invalid
        config.vector_dimension = -1  # Invalid

        service = EmbeddingService(config, enable_cache=True, max_cache_size=-1)
        service.max_retries = -1  # Invalid
        service.base_retry_delay = 0  # Invalid

        errors = service.validate_configuration()

        assert len(errors) > 0
        assert any("base url" in error.lower() for error in errors)
        assert any("model" in error.lower() for error in errors)
        assert any("dimension" in error.lower() for error in errors)
        assert any("cache size" in error.lower() for error in errors)
        assert any("retries" in error.lower() for error in errors)
        assert any("retry delay" in error.lower() for error in errors)
