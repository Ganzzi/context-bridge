"""Test Google Gemini context generation with multiple model options."""
import asyncio
import time
from context_bridge.config import Config
from context_bridge.agents.context_generator import ContextGenerator


# List of Gemini models to try, in order of preference
GEMINI_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-preview-09-2025',
    'gemini-flash-latest',
    'gemini-2.0-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash-lite-preview-09-2025',
    'gemini-2.0-flash-lite',
    'gemini-flash-lite-latest',
]


async def test_single_model(model_name: str, document: str, chunk: str):
    """Test a single Gemini model.
    
    Returns:
        (success: bool, context: str, error: str)
    """
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"{'='*60}")
    
    try:
        # Create config with the model
        config = Config(
            context_agent_model=f"google:{model_name}",
            context_agent_temperature=0.3,
            context_agent_max_tokens=500,
        )
        
        # Create context generator
        generator = ContextGenerator(config)
        
        # Generate context - SINGLE REQUEST PER MODEL
        print("Making API request...")
        context = await generator.generate_context(chunk, document)
        
        if context:
            print(f"✅ SUCCESS!")
            print(f"Generated context: {context[:100]}...")
            return True, context, None
        else:
            print("⚠️  Empty context returned")
            return False, "", "Empty context"
            
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            print(f"❌ Quota exceeded for {model_name}")
        elif "404" in error_msg or "not found" in error_msg.lower():
            print(f"❌ Model not available: {model_name}")
        else:
            print(f"❌ Error: {e}")
        return False, "", error_msg


async def test_gemini_models():
    """Test multiple Gemini models until one succeeds."""
    print("=" * 60)
    print("Google Gemini Context Generation Test")
    print("=" * 60)
    print(f"\nThis script makes ONLY 1 API request per model.")
    print(f"It will try {len(GEMINI_MODELS)} models until one succeeds.\n")
    print(f"Total max requests if all fail: {len(GEMINI_MODELS)}")
    print(f"Google free tier limit: ~10-15 requests per minute\n")
    
    # Sample document and chunk
    document = """
# Python Context Bridge Documentation

## Overview
Context Bridge is a Python library for managing and searching documentation with AI-powered context generation.

## Installation
Install via pip:
```bash
pip install context-bridge
```

## Features
- Web crawling with intelligent depth control
- Markdown chunking with configurable chunk sizes
- Vector embeddings with Ollama
- Hybrid search (vector + BM25)
- AI-powered context generation for improved search relevance
"""
    
    chunk = "Install via pip:\n```bash\npip install context-bridge\n```"
    
    # Try each model
    for i, model_name in enumerate(GEMINI_MODELS, 1):
        print(f"\n[{i}/{len(GEMINI_MODELS)}] Trying {model_name}...")
        
        success, context, error = await test_single_model(model_name, document, chunk)
        
        if success:
            print("\n" + "=" * 60)
            print("✅ TEST PASSED!")
            print("=" * 60)
            print(f"\nWorking model: {model_name}")
            print(f"\nFull context:\n{context}\n")
            return
        
        # If quota error, wait before trying next model
        if error and ("429" in error or "quota" in error.lower()):
            if i < len(GEMINI_MODELS):
                wait_time = 5
                print(f"Waiting {wait_time}s before trying next model...")
                time.sleep(wait_time)
    
    print("\n" + "=" * 60)
    print("❌ ALL MODELS FAILED")
    print("=" * 60)
    print("\nPossible reasons:")
    print("1. Quota exceeded - wait a few minutes and try again")
    print("2. Models not available in your region")
    print("3. API key doesn't have access to these models")
    print("\nCheck your quota at: https://aistudio.google.com/app/apikey")


if __name__ == "__main__":
    asyncio.run(test_gemini_models())
