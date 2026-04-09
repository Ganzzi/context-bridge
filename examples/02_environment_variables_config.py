"""
Pattern 2: Environment Variables Configuration

This is the RECOMMENDED pattern for containerized deployments (Docker, Kubernetes, etc.)

Advantages:
- ✅ Cloud-native: Standard approach for all container platforms
- ✅ No files: No need to manage .env files in containers
- ✅ Secrets integration: Works with Kubernetes Secrets, AWS Secrets Manager, etc.
- ✅ Easy CI/CD: Environment variables are standard in GitHub Actions, GitLab CI, etc.
- ✅ Dynamic: Change settings without rebuilding container images

Environment Variables (set these before running):
    export POSTGRES_HOST=localhost
    export POSTGRES_PASSWORD=secure_password
    export EMBEDDING_MODEL=nomic-embed-text:latest
    python 02_environment_variables_config.py
"""

import asyncio
import os
from context_bridge import ContextBridge, Config


async def main():
    print("=" * 70)
    print("Pattern 2: Environment Variables Configuration")
    print("=" * 70)
    print("\nEnvironment variables set:")

    env_vars = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "OLLAMA_BASE_URL",
        "EMBEDDING_MODEL",
        "VECTOR_DIMENSION",
        "SIMILARITY_THRESHOLD",
        "BM25_WEIGHT",
        "VECTOR_WEIGHT",
    ]

    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Hide password for security
            display_value = "***" if "PASSWORD" in var else value
            print(f"  {var}: {display_value}")

    # Config automatically loads from environment variables
    config = Config()

    print(f"\n✅ Configuration loaded from environment:")
    print(f"  Database: {config.postgres_db}@{config.postgres_host}:{config.postgres_port}")
    print(f"  Embedding Model: {config.embedding_model}")
    print(f"  Ollama URL: {config.ollama_base_url}")

    # Use with ContextBridge
    async with ContextBridge(config=config) as bridge:
        print("\n✅ ContextBridge initialized successfully!")

        # Check health
        health = await bridge.health_check()
        print(f"\nHealth status:")
        for key, value in health.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
