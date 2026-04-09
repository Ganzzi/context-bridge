"""
Embedding Service using Ollama API.

Provides async embedding generation for text content with caching and retry logic.
"""

import logging
import asyncio
import hashlib
from typing import List, Optional, Dict, Any
import aiohttp
from functools import lru_cache

from context_bridge.config import Config

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Base exception for embedding service errors."""

    pass


class EmbeddingConnectionError(EmbeddingError):
    """Raised when connection to Ollama API fails."""

    pass


class EmbeddingTimeoutError(EmbeddingError):
    """Raised when embedding request times out."""

    pass


class EmbeddingDimensionError(EmbeddingError):
    """Raised when embedding dimension is inconsistent."""

    pass


class EmbeddingService:
    """
    Service for generating text embeddings using Ollama.

    Uses async HTTP requests for better performance in I/O-bound operations.
    Includes caching, retry logic, and comprehensive error handling.
    """

    def __init__(self, config: Config, enable_cache: bool = True, max_cache_size: int = 1000):
        """
        Initialize embedding service.

        Args:
            config: Configuration object with Ollama settings
            enable_cache: Whether to enable embedding caching (default: True)
            max_cache_size: Maximum number of cached embeddings (default: 1000)
        """
        self.config = config
        self.base_url = config.ollama_base_url.rstrip("/v1").rstrip("/")
        self.model = config.embedding_model
        self.vector_dimension = config.vector_dimension
        self.enable_cache = enable_cache
        self.max_cache_size = max_cache_size

        # Initialize cache if enabled
        if self.enable_cache:
            self._embedding_cache: Dict[str, List[float]] = {}
            self._cache_hits = 0
            self._cache_misses = 0

        # Retry configuration
        self.max_retries = 3
        self.base_retry_delay = 5.0  # seconds (increased for model loading)
        self.max_retry_delay = 60.0  # seconds (increased for model loading)

        logger.info(f"Embedding service initialized: {self.model} ({self.vector_dimension}D)")
        if self.enable_cache:
            logger.info(f"Cache enabled with max size: {max_cache_size}")

    def _get_cache_key(self, text: str) -> str:
        """Generate a cache key for the given text."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _validate_embedding_dimension(self, embedding: List[float]) -> None:
        """
        Validate that the embedding has the expected dimension.

        Args:
            embedding: The embedding vector to validate

        Raises:
            EmbeddingDimensionError: If dimension doesn't match expected
        """
        if len(embedding) != self.vector_dimension:
            raise EmbeddingDimensionError(
                f"Expected embedding dimension {self.vector_dimension}, "
                f"got {len(embedding)}. Check model configuration."
            )

    async def _retry_with_backoff(
        self, operation: callable, *args, max_retries: Optional[int] = None, **kwargs
    ) -> Any:
        """
        Execute an operation with exponential backoff retry logic.

        Args:
            operation: The async operation to retry
            max_retries: Maximum number of retries (default: self.max_retries)
            *args, **kwargs: Arguments to pass to the operation

        Returns:
            Result of the operation

        Raises:
            The last exception encountered if all retries fail
        """
        if max_retries is None:
            max_retries = self.max_retries

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e

                if attempt < max_retries:
                    delay = min(self.base_retry_delay * (2**attempt), self.max_retry_delay)

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")

        # If we get here, all retries failed
        if isinstance(last_exception, asyncio.TimeoutError):
            raise EmbeddingTimeoutError(f"Operation timed out after {max_retries + 1} attempts")
        elif isinstance(last_exception, aiohttp.ClientError):
            raise EmbeddingConnectionError(
                f"Connection failed after {max_retries + 1} attempts: {last_exception}"
            )
        else:
            raise last_exception

    async def get_embedding(self, text: str, timeout: int = 120) -> List[float]:
        """
        Generate an embedding for the given text.

        Args:
            text: Text to embed
            timeout: Request timeout in seconds (default: 120 for model loading)

        Returns:
            List of float values representing the text embedding

        Raises:
            EmbeddingError: If embedding generation fails after retries
            EmbeddingDimensionError: If embedding dimension is inconsistent

        Example:
            embedding = await service.get_embedding("Hello world")
            print(f"Embedding dimension: {len(embedding)}")
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self.vector_dimension

        # Check cache first if enabled
        if self.enable_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._embedding_cache:
                self._cache_hits += 1
                logger.debug(f"Cache hit for text (length: {len(text)})")
                return self._embedding_cache[cache_key].copy()

            self._cache_misses += 1

        try:
            # Use retry logic for the actual API call
            embedding = await self._retry_with_backoff(
                self._get_embedding_single_attempt, text, timeout
            )

            # Validate dimension
            self._validate_embedding_dimension(embedding)

            # Cache the result if caching is enabled
            if self.enable_cache:
                if len(self._embedding_cache) >= self.max_cache_size:
                    # Simple LRU: remove oldest entry (not perfect but simple)
                    oldest_key = next(iter(self._embedding_cache))
                    del self._embedding_cache[oldest_key]
                    logger.debug("Cache full, removed oldest entry")

                self._embedding_cache[cache_key] = embedding.copy()
                logger.debug(f"Cached embedding for text (length: {len(text)})")

            return embedding

        except EmbeddingError:
            # Re-raise embedding-specific errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {e}")
            # Return zero vector as fallback for unexpected errors
            return [0.0] * self.vector_dimension

    async def _get_embedding_single_attempt(self, text: str, timeout: int) -> List[float]:
        """
        Single attempt to get embedding from Ollama API.

        Args:
            text: Text to embed
            timeout: Request timeout in seconds

        Returns:
            Embedding vector

        Raises:
            aiohttp.ClientError: If API request fails
            asyncio.TimeoutError: If request times out
            ValueError: If response format is invalid
        """
        payload = {
            "model": self.model,
            "prompt": text,
            # "options": {"num_gpu": 0},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                response.raise_for_status()
                result = await response.json()

                embedding = result.get("embedding", [])

                if not embedding:
                    raise ValueError("No embedding returned from Ollama API")

                return embedding

    async def get_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10,
        timeout: int = 120,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of concurrent requests (default: 10)
            timeout: Request timeout per embedding (default: 120)

        Returns:
            List of embeddings in the same order as input texts

        Example:
            texts = ["Hello", "World", "Test"]
            embeddings = await service.get_embeddings_batch(texts)
            print(f"Generated {len(embeddings)} embeddings")
        """
        if not texts:
            return []

        logger.info(f"Generating embeddings for {len(texts)} texts in batches of {batch_size}")

        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Process batch concurrently
            batch_embeddings = await asyncio.gather(
                *[self.get_embedding(text, timeout) for text in batch],
                return_exceptions=True,
            )

            # Handle any exceptions in the batch
            for j, result in enumerate(batch_embeddings):
                if isinstance(result, EmbeddingError):
                    logger.error(f"Embedding error for text {i+j}: {result}")
                    embeddings.append([0.0] * self.vector_dimension)
                elif isinstance(result, Exception):
                    logger.error(f"Unexpected error for text {i+j}: {result}")
                    embeddings.append([0.0] * self.vector_dimension)
                else:
                    embeddings.append(result)

            logger.debug(f"Processed batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")

        logger.info(f"Generated {len(embeddings)} embeddings successfully")
        return embeddings

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics if caching is enabled.

        Returns:
            Dictionary with cache statistics
        """
        if not self.enable_cache:
            return {"enabled": False}

        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

        return {
            "enabled": True,
            "size": len(self._embedding_cache),
            "max_size": self.max_cache_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate,
            "utilization": len(self._embedding_cache) / self.max_cache_size,
        }

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        if self.enable_cache:
            self._embedding_cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0
            logger.info("Embedding cache cleared")

    async def verify_connection(self) -> bool:
        """
        Verify that Ollama API is accessible and model is available.

        Returns:
            True if connection and model are available, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Check if Ollama is running
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    models = result.get("models", [])
                    model_names = [m.get("name", "") for m in models]

                    if self.model in model_names:
                        logger.info(f"Ollama connection verified, model {self.model} available")
                        return True
                    else:
                        logger.warning(
                            f"Ollama is running but model {self.model} not found. "
                            f"Available models: {model_names}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Failed to verify Ollama connection: {e}")
            return False

    async def ensure_model_available(self) -> bool:
        """
        Ensure the embedding model is available by attempting to generate a test embedding.

        Returns:
            True if model is available and working, False otherwise
        """
        try:
            test_embedding = await self.get_embedding("test", timeout=60)

            # Check if we got a real embedding (not zero vector)
            if sum(test_embedding) == 0:
                logger.error(f"Model {self.model} returned zero vector")
                return False

            logger.info(f"Model {self.model} is available and working")
            return True

        except EmbeddingError as e:
            logger.error(f"Model {self.model} is not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing model {self.model}: {e}")
            return False

    def validate_configuration(self) -> List[str]:
        """
        Validate the service configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.base_url:
            errors.append("Ollama base URL is not configured")

        if not self.model:
            errors.append("Embedding model is not configured")

        if self.vector_dimension <= 0:
            errors.append(f"Vector dimension must be positive, got {self.vector_dimension}")

        if self.enable_cache and self.max_cache_size <= 0:
            errors.append(
                f"Max cache size must be positive when caching is enabled, got {self.max_cache_size}"
            )

        if self.max_retries < 0:
            errors.append(f"Max retries must be non-negative, got {self.max_retries}")

        if self.base_retry_delay <= 0:
            errors.append(f"Base retry delay must be positive, got {self.base_retry_delay}")

        return errors
