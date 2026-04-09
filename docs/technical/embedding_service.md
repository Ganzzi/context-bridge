# Embedding Service Implementation Guide

This guide provides instructions for implementing an `EmbeddingService` that supports both local Ollama embeddings and Google Gemini API embeddings, using a unified configuration class.

## Overview

The `EmbeddingService` should provide a unified interface for generating text embeddings from different providers:

- **Ollama**: Local embedding models for offline, privacy-focused usage
- **Gemini**: Cloud-based embeddings from Google's Gemini API for high-quality, scalable embeddings

## Unified Configuration Class

Extend the existing `Config` class in `context_bridge/config/settings.py` to include embedding provider selection:

```python
from enum import Enum
from typing import Literal

class EmbeddingProvider(str, Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"

class Config(BaseModel):
    # ... existing fields ...

    # Embedding Provider Configuration
    embedding_provider: EmbeddingProvider = Field(
        default_factory=lambda: EmbeddingProvider(os.getenv("EMBEDDING_PROVIDER", "ollama"))
    )

    # Ollama-specific configuration
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    embedding_model: str = Field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    )
    vector_dimension: int = Field(
        default_factory=lambda: int(os.getenv("VECTOR_DIMENSION", "768"))
    )

    # Gemini-specific configuration
    google_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY")
    )
    gemini_embedding_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    )
    gemini_task_type: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_TASK_TYPE", "SEMANTIC_SIMILARITY")
    )
    gemini_output_dimensionality: Optional[int] = Field(
        default_factory=lambda: int(os.getenv("GEMINI_OUTPUT_DIMENSIONALITY", "768"))
    )

    # ... existing fields ...
```

## EmbeddingService Implementation

Create or modify `context_bridge/services/embedding.py` to support both providers:

```python
import logging
import asyncio
from typing import List, Optional, Union
import aiohttp

from context_bridge.config import Config, EmbeddingProvider

try:
    import google.genai as genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Unified service for generating text embeddings using Ollama or Gemini API.

    Supports both local Ollama models and Google Gemini cloud embeddings.
    """

    def __init__(self, config: Config):
        """
        Initialize embedding service.

        Args:
            config: Configuration object with embedding settings
        """
        self.config = config
        self.provider = config.embedding_provider

        if self.provider == EmbeddingProvider.OLLAMA:
            self._init_ollama()
        elif self.provider == EmbeddingProvider.GEMINI:
            self._init_gemini()
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def _init_ollama(self):
        """Initialize Ollama-specific settings."""
        self.base_url = self.config.ollama_base_url.rstrip("/v1").rstrip("/")
        self.model = self.config.embedding_model
        self.vector_dimension = self.config.vector_dimension
        logger.info(f"Ollama embedding service initialized: {self.model} ({self.vector_dimension}D)")

    def _init_gemini(self):
        """Initialize Gemini-specific settings."""
        if not self.config.google_api_key:
            raise ValueError("Google API key required for Gemini embeddings")

        if genai is None:
            raise ImportError("google-genai package required for Gemini embeddings")

        genai.configure(api_key=self.config.google_api_key)
        self.client = genai.GenerativeModel(self.config.gemini_embedding_model)
        self.task_type = self.config.gemini_task_type
        self.output_dimensionality = self.config.gemini_output_dimensionality
        logger.info(f"Gemini embedding service initialized: {self.config.gemini_embedding_model}")

    async def get_embedding(self, text: str, timeout: int = 30) -> List[float]:
        """
        Generate an embedding for the given text.

        Args:
            text: Text to embed
            timeout: Request timeout in seconds

        Returns:
            List of float values representing the text embedding
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self._get_dimension()

        if self.provider == EmbeddingProvider.OLLAMA:
            return await self._get_ollama_embedding(text, timeout)
        elif self.provider == EmbeddingProvider.GEMINI:
            return await self._get_gemini_embedding(text)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _get_dimension(self) -> int:
        """Get the expected embedding dimension."""
        if self.provider == EmbeddingProvider.OLLAMA:
            return self.vector_dimension
        elif self.provider == EmbeddingProvider.GEMINI:
            return self.output_dimensionality or 768
        return 768

    async def _get_ollama_embedding(self, text: str, timeout: int) -> List[float]:
        """Generate embedding using Ollama API."""
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

                    return embedding

        except Exception as e:
            logger.error(f"Ollama embedding error: {e}")
            return [0.0] * self.vector_dimension

    async def _get_gemini_embedding(self, text: str) -> List[float]:
        """Generate embedding using Gemini API."""
        try:
            result = genai.embed_content(
                model=self.config.gemini_embedding_model,
                content=text,
                task_type=self.task_type,
                output_dimensionality=self.output_dimensionality,
            )

            embedding = result['embedding']
            return embedding

        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            return [0.0] * self._get_dimension()

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
            batch_size: Number of concurrent requests
            timeout: Request timeout per embedding

        Returns:
            List of embeddings in the same order as input texts
        """
        if not texts:
            return []

        if self.provider == EmbeddingProvider.OLLAMA:
            return await self._get_ollama_embeddings_batch(texts, batch_size, timeout)
        elif self.provider == EmbeddingProvider.GEMINI:
            return await self._get_gemini_embeddings_batch(texts)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _get_ollama_embeddings_batch(
        self, texts: List[str], batch_size: int, timeout: int
    ) -> List[List[float]]:
        """Generate batch embeddings using Ollama."""
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await asyncio.gather(
                *[self._get_ollama_embedding(text, timeout) for text in batch],
                return_exceptions=True,
            )

            for result in batch_embeddings:
                if isinstance(result, Exception):
                    logger.error(f"Batch embedding error: {result}")
                    embeddings.append([0.0] * self.vector_dimension)
                else:
                    embeddings.append(result)

        return embeddings

    async def _get_gemini_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings using Gemini."""
        try:
            # Gemini supports batch embedding natively
            result = genai.embed_content(
                model=self.config.gemini_embedding_model,
                content=texts,
                task_type=self.task_type,
                output_dimensionality=self.output_dimensionality,
            )

            embeddings = result['embedding']
            return embeddings

        except Exception as e:
            logger.error(f"Gemini batch embedding error: {e}")
            dimension = self._get_dimension()
            return [[0.0] * dimension for _ in texts]

    async def verify_connection(self) -> bool:
        """
        Verify that the embedding service is accessible and working.

        Returns:
            True if connection and model are available, False otherwise
        """
        try:
            test_embedding = await self.get_embedding("test connection", timeout=10)
            return sum(test_embedding) != 0
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            return False
```

## Configuration Examples

### Ollama Configuration (.env)
```bash
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
VECTOR_DIMENSION=768
```

### Gemini Configuration (.env)
```bash
EMBEDDING_PROVIDER=gemini
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_TASK_TYPE=SEMANTIC_SIMILARITY
GEMINI_OUTPUT_DIMENSIONALITY=768
```

## Usage Examples

```python
from context_bridge.config import get_config
from context_bridge.services.embedding import EmbeddingService

# Initialize service
config = get_config()
service = EmbeddingService(config)

# Single embedding
embedding = await service.get_embedding("Hello world")
print(f"Embedding dimension: {len(embedding)}")

# Batch embeddings
texts = ["Hello", "World", "Test"]
embeddings = await service.get_embeddings_batch(texts)
print(f"Generated {len(embeddings)} embeddings")

# Verify connection
is_connected = await service.verify_connection()
print(f"Service connected: {is_connected}")
```

## Gemini-Specific Features

### Task Types
Gemini embeddings support task-specific optimization:

- `SEMANTIC_SIMILARITY`: For similarity assessment
- `CLASSIFICATION`: For text classification
- `CLUSTERING`: For clustering texts
- `RETRIEVAL_DOCUMENT`: For document indexing
- `RETRIEVAL_QUERY`: For search queries
- `QUESTION_ANSWERING`: For Q&A systems
- `FACT_VERIFICATION`: For fact-checking

### Output Dimensionality
Gemini supports flexible output dimensions (128-3072), with recommendations:
- 768: Good balance of quality and efficiency
- 1536: Higher quality
- 3072: Maximum quality (default)

### Batch Processing
Gemini supports native batch embedding for better performance with multiple texts.

## Dependencies

For Ollama support:
- `aiohttp` for HTTP requests

For Gemini support:
- `google-genai` package: `pip install google-genai`

## Error Handling

The service includes comprehensive error handling:
- Returns zero vectors as fallbacks for failed requests
- Logs errors for debugging
- Validates configuration on initialization
- Supports connection verification

## Performance Considerations

- **Ollama**: Best for offline usage, lower latency for single requests
- **Gemini**: Better for batch processing, higher throughput with Batch API
- Consider using Gemini's Batch API for large-scale embedding generation at 50% cost reduction

## Migration Guide

To migrate from Ollama-only to unified service:

1. Update configuration to include provider selection
2. Install `google-genai` if using Gemini
3. Set appropriate environment variables
4. Update any direct Ollama API calls to use the service interface