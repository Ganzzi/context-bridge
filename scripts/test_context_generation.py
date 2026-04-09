"""Test script for context generation with different LLM providers.

This script demonstrates how to use the ContextGenerator with different
LLM providers (Anthropic Claude, OpenAI GPT, Google Gemini, Grok).

Usage:
    # Set API keys in environment
    export ANTHROPIC_API_KEY="your-key"
    export OPENAI_API_KEY="your-key"
    export GOOGLE_API_KEY="your-key"
    export GROK_API_KEY="your-key"
    
    # Run the script
    python scripts/test_context_generation.py
"""

import asyncio
import logging
from context_bridge.config import Config
from context_bridge.agents.context_generator import ContextGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Sample document content
SAMPLE_DOCUMENT = """
# Python Context Bridge Documentation

## Overview
Context Bridge is a Python library for managing and searching documentation with AI-powered context generation.

## Installation
Install via pip:
```bash
pip install context-bridge
```

## Quick Start
```python
from context_bridge import ContextBridge, Config

config = Config(
    postgres_host="localhost",
    postgres_password="secure_pass",
    embedding_model="nomic-embed-text:latest"
)

async with ContextBridge(config=config) as bridge:
    result = await bridge.crawl_documentation(
        name="mylib",
        version="1.0.0",
        source_url="https://docs.example.com"
    )
```

## Features
- Web crawling with intelligent depth control
- Markdown chunking with configurable chunk sizes
- Vector embeddings with Ollama
- Hybrid search (vector + BM25)
- AI-powered context generation for improved search relevance
- Tag-based document organization
"""

SAMPLE_CHUNKS = [
    "Install via pip:\n```bash\npip install context-bridge\n```",
    "Context Bridge is a Python library for managing and searching documentation with AI-powered context generation.",
    "- Web crawling with intelligent depth control\n- Markdown chunking with configurable chunk sizes",
]


async def test_provider(provider_name: str, model_name: str):
    """Test context generation with a specific provider.
    
    Args:
        provider_name: Name of the provider (anthropic, openai, google, grok)
        model_name: Full model specification (e.g., "anthropic:claude-3-5-sonnet-20241022")
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing {provider_name.upper()} provider")
    logger.info(f"Model: {model_name}")
    logger.info(f"{'='*60}\n")
    
    try:
        # Create config with the specified model
        config = Config(
            context_agent_model=model_name,
            context_agent_temperature=0.3,
            context_agent_max_tokens=500,
        )
        
        # Create context generator
        generator = ContextGenerator(config)
        
        # Test single context generation
        logger.info("Testing single context generation...")
        context = await generator.generate_context(
            chunk_content=SAMPLE_CHUNKS[0],
            document_content=SAMPLE_DOCUMENT
        )
        logger.info(f"✓ Generated context: {context}\n")
        
        # Test batch context generation
        logger.info("Testing batch context generation...")
        contexts = await generator.generate_contexts_batch(
            chunks=SAMPLE_CHUNKS,
            document_content=SAMPLE_DOCUMENT
        )
        
        for i, ctx in enumerate(contexts):
            logger.info(f"✓ Context {i+1}: {ctx}\n")
        
        logger.info(f"✅ {provider_name.upper()} test completed successfully!\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ {provider_name.upper()} test failed: {e}\n")
        return False


async def main():
    """Run tests for all available providers."""
    logger.info("Context Generation Test Suite")
    logger.info("="*60)
    logger.info("Testing context generation with multiple LLM providers\n")
    
    # Test configurations: (provider_name, model_spec)
    providers_to_test = [
        ("anthropic", "anthropic:claude-3-5-sonnet-20241022"),
        ("openai", "openai:gpt-4o"),
        ("google", "google:gemini-1.5-pro"),
        ("grok", "grok:grok-2-latest"),
    ]
    
    results = {}
    
    for provider_name, model_spec in providers_to_test:
        # Check if API key is available
        config = Config()
        api_key_attr = f"{provider_name}_api_key"
        
        if not hasattr(config, api_key_attr) or not getattr(config, api_key_attr):
            logger.warning(f"⚠️  Skipping {provider_name.upper()}: No API key configured")
            logger.warning(f"   Set {provider_name.upper()}_API_KEY environment variable to test\n")
            results[provider_name] = "skipped"
            continue
        
        # Run test
        success = await test_provider(provider_name, model_spec)
        results[provider_name] = "passed" if success else "failed"
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("Test Summary")
    logger.info("="*60)
    for provider, status in results.items():
        emoji = "✅" if status == "passed" else "⚠️" if status == "skipped" else "❌"
        logger.info(f"{emoji} {provider.upper()}: {status}")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
