"""Configuration settings for Context Bridge.

Supports three configuration methods:
1. Direct Python instantiation (recommend    model_config = ConfigDict(
        env_file=".env",  # Load from .env file in project root (if exists and python-dotenv available)
        env_file_encoding="utf-8",  # Encoding for .env file
        case_sensitive=False,  # Treat env var names case-insensitively (POSTGRES_HOST == postgres_host)
        extra="ignore",  # Ignore extra fields not defined in Config model
    ) PyPI installs)
2. Environment variables (recommended for Docker/Kubernetes)
3. .env file (convenient for local development only)

The .env file loading is optional and only attempted if python-dotenv is available.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

# Optional .env loading - only if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, just use environment variables
    pass


class Config(BaseModel):
    """Configuration for Context Bridge.

    This class provides type-safe configuration management and supports three
    initialization patterns:

    **Pattern 1: Direct Python (Recommended for PyPI users)**
    ```python
    from context_bridge import ContextBridge, Config

    config = Config(
        postgres_host="localhost",
        postgres_password="secure_password",
        embedding_model="nomic-embed-text:latest"
    )

    async with ContextBridge(config=config) as bridge:
        result = await bridge.crawl_documentation(...)
    ```

    **Pattern 2: Environment Variables (Recommended for Docker/K8s)**
    ```bash
    export POSTGRES_HOST=postgres
    export POSTGRES_PASSWORD=secure_pass
    export EMBEDDING_MODEL=nomic-embed-text:latest
    python my_app.py
    ```
    ```python
    from context_bridge import ContextBridge

    async with ContextBridge() as bridge:
        result = await bridge.crawl_documentation(...)
    ```

    **Pattern 3: .env File (Convenient for local development)**
    ```bash
    # .env (git-ignored)
    POSTGRES_HOST=localhost
    POSTGRES_PASSWORD=devpass
    EMBEDDING_MODEL=nomic-embed-text:latest
    ```
    ```python
    # Automatically loaded if python-dotenv is available
    from context_bridge import ContextBridge

    async with ContextBridge() as bridge:
        result = await bridge.crawl_documentation(...)
    ```
    """

    # PostgreSQL Configuration
    postgres_host: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: int = Field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    postgres_user: str = Field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    postgres_password: str = Field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    postgres_db: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "context_bridge"))
    postgres_max_pool_size: int = Field(default_factory=lambda: int(os.getenv("DB_POOL_MAX", "10")))

    # Ollama Configuration
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    embedding_model: str = Field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
    )
    vector_dimension: int = Field(default_factory=lambda: int(os.getenv("VECTOR_DIMENSION", "768")))

    # Search Configuration
    similarity_threshold: float = Field(
        default_factory=lambda: float(os.getenv("SIMILARITY_THRESHOLD", "0.7")),
        description="Default similarity threshold",
    )
    bm25_weight: float = Field(
        default_factory=lambda: float(os.getenv("BM25_WEIGHT", "0.3")),
        description="Weight for BM25 in hybrid search",
    )
    vector_weight: float = Field(
        default_factory=lambda: float(os.getenv("VECTOR_WEIGHT", "0.7")),
        description="Weight for vector in hybrid search",
    )

    # Chunking configuration
    chunk_size: int = Field(
        default_factory=lambda: int(os.getenv("CHUNK_SIZE", "2000")),
        description="Default chunk size for markdown chunking",
    )
    min_combined_content_size: int = Field(
        default_factory=lambda: int(os.getenv("MIN_COMBINED_CONTENT_SIZE", "100")),
        description="Minimum total size for combined page content",
    )
    max_combined_content_size: int = Field(
        default_factory=lambda: int(os.getenv("MAX_COMBINED_CONTENT_SIZE", "3500000")),
        description="Maximum total size for combined page content",
    )

    # Crawling configuration
    crawl_max_depth: int = Field(
        default_factory=lambda: int(os.getenv("CRAWL_MAX_DEPTH", "3")),
        description="Maximum crawl depth for web crawling",
    )
    crawl_max_concurrent: int = Field(
        default_factory=lambda: int(os.getenv("CRAWL_MAX_CONCURRENT", "10")),
        description="Maximum concurrent crawling operations",
    )

    # AI Context Generation Settings
    context_agent_model: str = Field(
        default_factory=lambda: os.getenv(
            "CONTEXT_AGENT_MODEL", "anthropic:claude-3-5-sonnet-20241022"
        ),
        description="Model for context generation agent (format: provider:model_name)",
    )
    context_agent_temperature: float = Field(
        default_factory=lambda: float(os.getenv("CONTEXT_AGENT_TEMPERATURE", "0.3")),
        description="Temperature for context generation (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    context_agent_max_tokens: int = Field(
        default_factory=lambda: int(os.getenv("CONTEXT_AGENT_MAX_TOKENS", "500")),
        description="Max tokens for context generation response",
        ge=1,
    )
    context_batch_size: int = Field(
        default_factory=lambda: int(os.getenv("CONTEXT_BATCH_SIZE", "10")),
        description="Number of chunks to process in parallel for context generation",
        ge=1,
    )
    context_enable_cache: bool = Field(
        default_factory=lambda: os.getenv("CONTEXT_ENABLE_CACHE", "true").lower() == "true",
        description="Enable prompt caching for cost savings",
    )

    # API Keys for context generation
    anthropic_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"),
        description="Anthropic API key for Claude models",
    )
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY"),
        description="OpenAI API key for GPT models",
    )

    model_config = ConfigDict(
        env_file=".env",  # Optional .env loading - only loaded if file exists
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("postgres_password")
    @classmethod
    def validate_password(cls, v: str, info) -> str:
        """Validate that passwords meet minimum security requirements.

        Only validates if a password is actually provided (non-empty).
        This allows development with default empty password while requiring
        secure passwords in production configs.
        """
        if v and len(v) < 8:
            raise ValueError(
                f"{info.field_name} must be at least 8 characters long for security. "
                f"Current length: {len(v)}"
            )
        return v


# Global config instance (for backward compatibility with get_config/set_config pattern)
# This is optional - the recommended pattern is to pass Config directly to ContextBridge
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    **Use Case**: Fallback pattern for CLI scripts, services, and tests.
    This maintains a global singleton for convenience when a Config can't be
    passed directly through the call stack.

    **Recommended for:**
    - CLI tools (init_databases.py, db_interact.py)
    - Service classes that accept optional config parameter
    - Test scripts that need quick config access

    **NOT Recommended for:**
    - Main application code - pass Config explicitly to ContextBridge
    - Library code - accept Config as parameter instead

    The returned Config is loaded in this order (first match wins):
    1. Environment variables (POSTGRES_HOST, etc.)
    2. .env file (if python-dotenv is available and file exists)
    3. Default hardcoded values

    Example:
        ```python
        # For CLI scripts - OK to use get_config()
        from context_bridge.config import get_config
        config = get_config()
        manager = PostgreSQLManager(config)

        # For main app - pass Config explicitly (BETTER)
        from context_bridge import ContextBridge, Config
        config = Config(postgres_host="localhost", ...)
        bridge = ContextBridge(config=config)
        ```

    Returns:
        Config object loaded from environment variables, .env file, or defaults
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance.

    **Use Case**: Mainly for testing or CLI scripts that need to override config.

    Use this to temporarily set a different config for:
    - Unit tests (mock configurations)
    - Testing different database connections
    - CLI tools that load config dynamically

    **NOT Recommended for:**
    - Production code - pass Config to ContextBridge instead
    - Library code - accept Config as parameter

    Example:
        ```python
        # For testing - OK to use set_config()
        test_config = Config(postgres_db="test_db", ...)
        set_config(test_config)
        config = get_config()  # Returns test_config

        # For production - pass Config directly (BETTER)
        config = Config(...)
        bridge = ContextBridge(config=config)
        ```

    Args:
        config: Configuration object to set as global instance
    """
    global _config
    _config = config
