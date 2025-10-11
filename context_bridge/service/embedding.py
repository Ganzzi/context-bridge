"""
Embedding Service using Ollama API.

Provides async embedding generation for text content.
"""

import logging
import asyncio
from typing import List, Optional
import aiohttp

from context_bridge.config import Config

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using Ollama.

    Uses async HTTP requests for better performance in I/O-bound operations.
    """

    def __init__(self, config: Config):
        """
        Initialize embedding service.

        Args:
            config: Configuration object with Ollama settings
        """
        self.config = config
        self.base_url = config.ollama_base_url.rstrip("/v1").rstrip("/")
        self.model = config.embedding_model
        self.vector_dimension = config.vector_dimension

        logger.info(f"Embedding service initialized: {self.model} ({self.vector_dimension}D)")

    async def get_embedding(self, text: str, timeout: int = 30) -> List[float]:
        """
        Generate an embedding for the given text.

        Args:
            text: Text to embed
            timeout: Request timeout in seconds (default: 30)

        Returns:
            List of float values representing the text embedding

        Raises:
            RuntimeError: If embedding generation fails

        Example:
            embedding = await service.get_embedding("Hello world")
            print(f"Embedding dimension: {len(embedding)}")
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self.vector_dimension

        try:
            payload = {
                "model": self.model,
                "prompt": text,
                "options": {"num_gpu": 0},
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

                    if len(embedding) != self.vector_dimension:
                        logger.warning(
                            f"Expected embedding dimension {self.vector_dimension}, "
                            f"got {len(embedding)}. Check model configuration."
                        )

                    return embedding

        except aiohttp.ClientError as e:
            logger.error(f"Error connecting to Ollama API at {self.base_url}: {e}")
            logger.error(
                f"Ensure Ollama is running and {self.model} model is installed: "
                f"ollama pull {self.model}"
            )
            # Return zero vector as fallback
            return [0.0] * self.vector_dimension

        except asyncio.TimeoutError:
            logger.error(f"Ollama API request timed out after {timeout}s for text: {text[:50]}...")
            return [0.0] * self.vector_dimension

        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {e}")
            return [0.0] * self.vector_dimension

    async def get_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10,
        timeout: int = 30,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of concurrent requests (default: 10)
            timeout: Request timeout per embedding (default: 30)

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
                if isinstance(result, Exception):
                    logger.error(f"Error generating embedding for text {i+j}: {result}")
                    embeddings.append([0.0] * self.vector_dimension)
                else:
                    embeddings.append(result)

            logger.debug(f"Processed batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")

        logger.info(f"Generated {len(embeddings)} embeddings successfully")
        return embeddings

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
            test_embedding = await self.get_embedding("test", timeout=10)

            # Check if we got a real embedding (not zero vector)
            if sum(test_embedding) == 0:
                logger.error(f"Model {self.model} returned zero vector")
                return False

            logger.info(f"Model {self.model} is available and working")
            return True

        except Exception as e:
            logger.error(f"Model {self.model} is not available: {e}")
            return False
