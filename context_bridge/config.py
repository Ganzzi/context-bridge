"""Configuration settings for Agent Mem."""

import os
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from dotenv import load_dotenv

load_dotenv()


class Config(BaseModel):
    """Configuration for Agent Mem package."""

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
    chunk_size: int = Field(default=2000, description="Default chunk size for markdown chunking")
    min_combined_content_size: int = Field(
        default=100, description="Minimum total size for combined page content"
    )
    max_combined_content_size: int = Field(
        default=50000, description="Maximum total size for combined page content"
    )

    # Crawling configuration
    crawl_max_depth: int = Field(default=3, description="Maximum crawl depth for web crawling")
    crawl_max_concurrent: int = Field(
        default=10, description="Maximum concurrent crawling operations"
    )

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("postgres_password")
    @classmethod
    def validate_password(cls, v: str, info) -> str:
        """Validate that passwords meet minimum security requirements."""
        if v and len(v) < 8:
            raise ValueError(
                f"{info.field_name} must be at least 8 characters long for security. "
                f"Current length: {len(v)}"
            )
        return v


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
