"""
Pattern 3: .env File Configuration

This is RECOMMENDED ONLY for local development and testing.

Advantages:
- ✅ Convenient: All settings in one file
- ✅ Organized: Easy to see all configuration
- ✅ Git-ignored: Keep secrets out of version control
- ✅ Sharable template: Use .env.example for team

Setup:
    1. Install dev dependencies: pip install context-bridge[dev]
    2. Create .env file (git-ignored): cp .env.example .env
    3. Edit .env with your local settings
    4. Run this script: python 03_dotenv_file_config.py

.env File Example:
    # PostgreSQL Configuration
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=your_password_here
    POSTGRES_DB=context_bridge
    
    # Ollama Configuration
    OLLAMA_BASE_URL=http://localhost:11434
    EMBEDDING_MODEL=nomic-embed-text:latest
    VECTOR_DIMENSION=768
    
    # Search Configuration
    SIMILARITY_THRESHOLD=0.7
    BM25_WEIGHT=0.3
    VECTOR_WEIGHT=0.7
"""

import asyncio
from context_bridge import ContextBridge, Config


async def main():
    print("=" * 70)
    print("Pattern 3: .env File Configuration")
    print("=" * 70)
    print("\n📁 Looking for .env file in current directory...")
    
    try:
        # Config automatically loads from .env (if python-dotenv available)
        config = Config()
        
        print(f"\n✅ Configuration loaded from .env file:")
        print(f"  Database: {config.postgres_db}@{config.postgres_host}:{config.postgres_port}")
        print(f"  Embedding Model: {config.embedding_model}")
        print(f"  Ollama URL: {config.ollama_base_url}")
        print(f"  Chunk Size: {config.chunk_size}")
        
        # Use with ContextBridge
        async with ContextBridge(config=config) as bridge:
            print("\n✅ ContextBridge initialized successfully!")
            
            # Check health
            health = await bridge.health_check()
            print(f"\nHealth status:")
            for key, value in health.items():
                print(f"  {key}: {value}")
    
    except ImportError:
        print("\n❌ python-dotenv not installed!")
        print("\nTo use .env files, install dev dependencies:")
        print("  pip install context-bridge[dev]")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure .env file exists with valid configuration")


if __name__ == "__main__":
    asyncio.run(main())
