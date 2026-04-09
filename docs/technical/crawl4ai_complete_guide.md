# Crawl4AI Technical Documentation Guide

## Overview

This guide provides comprehensive instructions for using **Crawl4AI** to crawl and extract technical documentation from the internet. It focuses on using the `CrawlingService` class with a unified configuration approach for reliable, efficient, and intelligent web crawling.

**Crawl4AI** is an open-source, high-performance web crawler designed specifically for AI agents and LLMs, enabling fast, precise, and AI-ready data extraction with clean Markdown generation.

## Quick Start

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from database.utility_services.crawling_service import CrawlingService, CrawlConfig

async def quick_start():
    # Initialize service with configuration
    service = CrawlingService(CrawlConfig(
        max_depth=3,              # Crawl depth
        max_concurrent=10,        # Concurrent sessions
        memory_threshold=75.0     # Memory threshold
    ))
    
    # Crawl documentation
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await service.crawl_webpage(crawler, "https://docs.python.org/3/")
        
        # Check results
        print(f"Pages crawled: {result.successful_count}")
        for crawl_result in result.results:
            print(f"URL: {crawl_result.url}")
            print(f"Content: {len(crawl_result.markdown)} chars\n")

asyncio.run(quick_start())
```

## Table of Contents

1. [Installation](#installation)
2. [Core Concepts](#core-concepts)
3. [CrawlingService Architecture](#crawlingservice-architecture)
4. [Configuration Reference](#configuration-reference)
5. [Usage Examples](#usage-examples)
   - Basic Documentation Crawling
   - Error Handling and Validation
   - Multiple Documentation Sources
   - Sitemap Crawling
   - Text/Markdown Files
   - Practical Usage Pattern
6. [Best Practices for Technical Documentation](#best-practices-for-technical-documentation)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)
9. [Performance Optimization Checklist](#performance-optimization-checklist)
10. [API Reference](#api-reference)
11. [Summary](#summary)

---

## Installation

```bash
pip install crawl4ai
```

For async support and additional features:

```bash
pip install crawl4ai[all]
```

---

## Core Concepts

### 1. CrawlingService

The main service class that provides a unified interface for crawling operations. It requires an `AsyncWebCrawler` instance to be passed to its methods.

```python
from database.utility_services.crawling_service import CrawlingService, CrawlConfig
from crawl4ai import AsyncWebCrawler

# Initialize service with configuration
service = CrawlingService(CrawlConfig(max_depth=3, max_concurrent=10))

# Use with AsyncWebCrawler
async with AsyncWebCrawler(verbose=True) as crawler:
    result = await service.crawl_webpage(crawler, "https://example.com/docs")
```

### 2. CrawlConfig

Configuration for the crawling service behavior:

```python
from database.utility_services.crawling_service import CrawlConfig

config = CrawlConfig(
    max_depth=3,              # Depth for recursive crawling
    max_concurrent=10,        # Concurrent crawling sessions
    memory_threshold=70.0     # Memory threshold percentage
)
```

**Note**: The `chunk_size` parameter is currently unused in the implementation.

### 3. Result Models

#### CrawlResult

Individual crawl result with validation:

```python
class CrawlResult(BaseModel):
    url: str              # The crawled URL (validated)
    markdown: str         # Extracted markdown content (non-empty)
```

#### CrawlBatchResult

Batch crawl results with metadata:

```python
class CrawlBatchResult(BaseModel):
    results: List[CrawlResult]     # List of successful crawl results
    crawl_type: CrawlType          # Type of crawl performed
    total_urls_attempted: int      # Total URLs attempted
    successful_count: int          # Number of successful crawls
    failed_count: int              # Number of failed crawls
```

### 4. Crawl Types

The `CrawlingService` automatically detects and handles:

- **CrawlType.WEBPAGE**: Standard HTML pages with recursive internal link following
- **CrawlType.SITEMAP**: XML sitemaps for bulk URL discovery
- **CrawlType.TEXT_FILE**: Direct `.txt` or `.md` file URLs

---

## CrawlingService Architecture

### Overview

The `CrawlingService` provides a unified interface for different crawling strategies with automatic URL type detection and appropriate crawling method selection.

### Key Components

```python
from database.utility_services.crawling_service import (
    CrawlingService,
    CrawlConfig,
    CrawlResult,
    CrawlBatchResult,
    CrawlType
)
```

### Class Structure

```
CrawlingService
├── config: CrawlConfig          # Unified configuration
├── url_service: UrlService      # URL detection and parsing
│
├── crawl_webpage()              # Main entry point (auto-detects URL type)
├── _crawl_recursive_internal_links()  # For standard webpages
├── _crawl_batch()               # For sitemaps and multiple URLs
└── _crawl_text_file()           # For markdown/text files
```

---

## Configuration Reference

### CrawlConfig

Unified configuration class for the CrawlingService:

```python
from database.utility_services.crawling_service import CrawlConfig

config = CrawlConfig(
    max_depth=3,              # Maximum depth for recursive crawling (1-10)
    max_concurrent=10,        # Maximum concurrent crawl sessions (1-50)
    memory_threshold=70.0     # Memory usage threshold percentage (10.0-95.0)
)
```

#### Configuration Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `max_depth` | int | 3 | 1-10 | How deep to follow internal links recursively |
| `max_concurrent` | int | 10 | 1-50 | Number of concurrent crawling sessions |
| `memory_threshold` | float | 70.0 | 10.0-95.0 | Memory usage percentage before throttling |

**Important Notes**:
- `max_depth` is used at **runtime** by the `_crawl_recursive_internal_links` method
- `max_concurrent` is passed to the `MemoryAdaptiveDispatcher` 
- `memory_threshold` controls when the dispatcher throttles requests
- The `chunk_size` parameter exists in the config but is currently **unused** in the implementation

### Error Handling

The `CrawlingService` has built-in error handling:

```python
# Returns CrawlBatchResult even on errors
result = await service.crawl_webpage(crawler, url)

# Check for success
if result.successful_count > 0:
    print(f"Successfully crawled {result.successful_count} pages")
else:
    print(f"All crawls failed: {result.failed_count} failures")

# Access individual results
for crawl_result in result.results:
    print(f"URL: {crawl_result.url}")
    print(f"Content: {crawl_result.markdown[:100]}...")
```

**Exception Handling**:
- `crawl_webpage()` catches all exceptions and returns a `CrawlBatchResult` with zero successful results
- Individual `CrawlResult` objects validate URLs (must start with http:// or https://)
- Individual `CrawlResult` objects validate markdown content (must not be empty)
- Pydantic `ValidationError` may be raised if result data is invalid

---

## Usage Examples

### Example 1: Basic Documentation Crawling

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from database.utility_services.crawling_service import CrawlingService, CrawlConfig

async def crawl_documentation():
    # Configure the service
    config = CrawlConfig(
        max_depth=3,              # Crawl up to 3 levels deep
        max_concurrent=5,         # 5 concurrent sessions
        memory_threshold=75.0     # Throttle at 75% memory
    )
    
    # Initialize the service
    service = CrawlingService(config)
    
    # Crawl a documentation site
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await service.crawl_webpage(crawler, "https://docs.python.org/3/")
        
        # Check results
        print(f"Crawl Type: {result.crawl_type.value}")
        print(f"Success Rate: {result.successful_count}/{result.total_urls_attempted}")
        print(f"Failed: {result.failed_count}")
        
        # Process results
        if result.successful_count > 0:
            for crawl_result in result.results:
                print(f"\n{'='*80}")
                print(f"URL: {crawl_result.url}")
                print(f"Content Length: {len(crawl_result.markdown)} characters")
                print(f"Preview: {crawl_result.markdown[:200]}...")
        else:
            print("No pages were successfully crawled")

if __name__ == "__main__":
    asyncio.run(crawl_documentation())
```

### Example 2: Error Handling and Validation

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from database.utility_services.crawling_service import (
    CrawlingService,
    CrawlConfig,
    CrawlResult
)
from pydantic import ValidationError

async def crawl_with_error_handling():
    service = CrawlingService(CrawlConfig(max_depth=2, max_concurrent=5))
    
    urls_to_crawl = [
        "https://docs.python.org/3/",
        "https://invalid-url-that-might-fail.com/docs",
        "https://another-docs-site.com"
    ]
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        for url in urls_to_crawl:
            print(f"\n{'='*80}")
            print(f"Processing: {url}")
            
            try:
                result = await service.crawl_webpage(crawler, url)
                
                # Check if any pages were crawled
                if result.successful_count == 0:
                    print(f"⚠️  No pages crawled from {url}")
                    print(f"   Failed attempts: {result.failed_count}")
                    continue
                
                # Process successful results
                print(f"✅ Successfully crawled {result.successful_count} pages")
                
                for crawl_result in result.results:
                    try:
                        # Validate result (already validated by Pydantic)
                        if len(crawl_result.markdown) < 100:
                            print(f"⚠️  Short content: {crawl_result.url}")
                        else:
                            print(f"✅ Valid result: {crawl_result.url}")
                            # Store or process the result
                            
                    except ValidationError as e:
                        print(f"❌ Validation error for result: {e}")
                        
            except Exception as e:
                print(f"❌ Unexpected error processing {url}: {e}")

if __name__ == "__main__":
    asyncio.run(crawl_with_error_handling())
```

### Example 3: Crawling Multiple Documentation Sources

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from database.utility_services.crawling_service import CrawlingService, CrawlConfig

async def crawl_multiple_docs():
    # Configure for moderate crawling
    config = CrawlConfig(
        max_depth=2,              # Shallower for multiple sites
        max_concurrent=8,
        memory_threshold=80.0
    )
    
    service = CrawlingService(config)
    
    # Multiple documentation sources
    doc_urls = [
        "https://docs.python.org/3/",
        "https://docs.django.org/en/stable/",
        "https://fastapi.tiangolo.com/",
    ]
    
    # Reuse the same crawler for all URLs
    async with AsyncWebCrawler(verbose=True) as crawler:
        for url in doc_urls:
            print(f"\n{'='*80}")
            print(f"Processing: {url}")
            print('='*80)
            
            result = await service.crawl_webpage(crawler, url)
            
            if result.successful_count > 0:
                print(f"✅ Crawled {result.successful_count} pages from {url}")
                print(f"   Type: {result.crawl_type.value}")
                
                # Store or process results
                for crawl_result in result.results:
                    await store_in_database(crawl_result)
            else:
                print(f"❌ Failed to crawl {url}")
                print(f"   Failed attempts: {result.failed_count}")

async def store_in_database(crawl_result):
    """Store crawled content in your database"""
    # Your database storage implementation
    print(f"   Storing: {crawl_result.url} ({len(crawl_result.markdown)} chars)")

if __name__ == "__main__":
    asyncio.run(crawl_multiple_docs())
```

### Example 4: Crawling Technical Documentation with Sitemap

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from database.utility_services.crawling_service import (
    CrawlingService,
    CrawlConfig,
    CrawlType
)

async def crawl_sitemap_docs():
    """
    Automatically detects and processes sitemap URLs.
    The service will fetch all URLs from the sitemap and crawl them in batch.
    """
    config = CrawlConfig(
        max_concurrent=15,        # Higher for bulk sitemap processing
        memory_threshold=75.0
    )
    
    service = CrawlingService(config)
    
    # Sitemap URL - automatically detected by is_sitemap()
    sitemap_url = "https://example.com/sitemap.xml"
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await service.crawl_webpage(crawler, sitemap_url)
        
        # Verify sitemap detection
        if result.crawl_type == CrawlType.SITEMAP:
            print("✅ Sitemap detected and processed")
        
        print(f"Sitemap Processing Results:")
        print(f"  Total URLs in sitemap: {result.total_urls_attempted}")
        print(f"  Successfully crawled: {result.successful_count}")
        print(f"  Failed: {result.failed_count}")
        
        if result.total_urls_attempted > 0:
            success_rate = result.successful_count / result.total_urls_attempted * 100
            print(f"  Success rate: {success_rate:.1f}%")
        
        # Process each successfully crawled page
        for crawl_result in result.results:
            print(f"\n📄 {crawl_result.url}")
            print(f"   Length: {len(crawl_result.markdown)} chars")

if __name__ == "__main__":
    asyncio.run(crawl_sitemap_docs())
```

### Example 5: Crawling Markdown/Text Documentation Files

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from database.utility_services.crawling_service import (
    CrawlingService,
    CrawlConfig,
    CrawlType
)

async def crawl_readme_files():
    """
    Crawl README.md or other text documentation files.
    The service automatically detects .txt, .md, and .markdown extensions.
    """
    config = CrawlConfig()  # Use defaults for simple text files
    service = CrawlingService(config)
    
    # Text file URLs - automatically detected by is_txt()
    doc_files = [
        "https://raw.githubusercontent.com/user/repo/main/README.md",
        "https://example.com/docs/installation.txt",
        "https://example.com/api-guide.md"
    ]
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        for file_url in doc_files:
            result = await service.crawl_webpage(crawler, file_url)
            
            # Verify text file detection
            if result.crawl_type == CrawlType.TEXT_FILE:
                print(f"✅ Text file detected: {file_url}")
                
                if result.successful_count > 0:
                    content = result.results[0].markdown
                    print(f"   Content length: {len(content)} characters")
                    print(f"   Preview:\n{content[:300]}...\n")
                else:
                    print(f"   ⚠️  Failed to crawl text file")
            else:
                print(f"⚠️  Not detected as text file: {file_url}")
                print(f"   Detected as: {result.crawl_type.value}")

if __name__ == "__main__":
    asyncio.run(crawl_readme_files())
```

### Example 6: Practical Usage Pattern

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from database.utility_services.crawling_service import CrawlingService, CrawlConfig
from typing import List

class DocumentationCrawler:
    """
    Practical wrapper for documentation crawling.
    """
    
    def __init__(self, max_depth: int = 3, max_concurrent: int = 10):
        self.config = CrawlConfig(
            max_depth=max_depth,
            max_concurrent=max_concurrent,
            memory_threshold=75.0
        )
        self.service = CrawlingService(self.config)
    
    async def crawl_url(self, url: str) -> List[dict]:
        """
        Crawl a single URL and return results as dictionaries.
        
        Returns:
            List of dicts with 'url' and 'content' keys
        """
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await self.service.crawl_webpage(crawler, url)
            
            if result.successful_count == 0:
                print(f"⚠️  No content retrieved from {url}")
                return []
            
            # Convert to simple dict format
            return [
                {
                    'url': cr.url,
                    'content': cr.markdown,
                    'length': len(cr.markdown)
                }
                for cr in result.results
            ]
    
    async def crawl_multiple(self, urls: List[str]) -> dict:
        """
        Crawl multiple URLs and return aggregated results.
        
        Returns:
            Dict with statistics and all crawled documents
        """
        all_documents = []
        stats = {
            'total_urls': len(urls),
            'successful_sites': 0,
            'total_pages': 0,
            'failed_sites': 0
        }
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for url in urls:
                result = await self.service.crawl_webpage(crawler, url)
                
                if result.successful_count > 0:
                    stats['successful_sites'] += 1
                    stats['total_pages'] += result.successful_count
                    
                    for cr in result.results:
                        all_documents.append({
                            'url': cr.url,
                            'content': cr.markdown,
                            'source': url
                        })
                else:
                    stats['failed_sites'] += 1
        
        return {
            'stats': stats,
            'documents': all_documents
        }


# Usage
async def main():
    crawler = DocumentationCrawler(max_depth=2, max_concurrent=5)
    
    # Single URL
    docs = await crawler.crawl_url("https://docs.python.org/3/tutorial/")
    print(f"Crawled {len(docs)} pages")
    
    # Multiple URLs
    result = await crawler.crawl_multiple([
        "https://docs.python.org/3/",
        "https://fastapi.tiangolo.com/"
    ])
    print(f"Statistics: {result['stats']}")
    print(f"Total documents: {len(result['documents'])}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Best Practices for Technical Documentation

### 1. Understanding URL Type Detection

The `CrawlingService` uses `UrlService` for automatic URL type detection:

```python
from database.utility_services.url_service import UrlService

url_service = UrlService()

# Automatic detection methods
if url_service.is_txt(url):
    # Detects: .txt, .md, .markdown extensions
    print("Text file detected")
elif url_service.is_sitemap(url):
    # Detects: ends with 'sitemap.xml' or 'sitemap' in path
    print("Sitemap detected")
else:
    # Default to webpage with recursive crawling
    print("Standard webpage")

# Utility methods
domain = url_service.get_domain(url)
normalized = url_service.normalize_url(url)  # Removes fragments
sitemap_urls = url_service.parse_sitemap(sitemap_url)  # Extracts URLs from sitemap
```

### 2. Optimal Configuration for Documentation Sites

Choose configuration based on your documentation site size and structure:

```python
from database.utility_services.crawling_service import CrawlConfig

# For comprehensive documentation (e.g., official language docs)
comprehensive_config = CrawlConfig(
    max_depth=3,              # Balance depth vs. time
    max_concurrent=10,        # Moderate concurrency
    memory_threshold=75.0     # Safe threshold
)

# For large documentation sites (e.g., AWS, Azure docs)
large_docs_config = CrawlConfig(
    max_depth=2,              # Limit depth due to size
    max_concurrent=15,        # Higher concurrency for faster completion
    memory_threshold=70.0     # More conservative memory usage
)

# For small, focused documentation (e.g., library docs)
focused_config = CrawlConfig(
    max_depth=5,              # Can go deeper
    max_concurrent=5,         # Lower concurrency sufficient
    memory_threshold=80.0     # Can use more memory
)
```

### 3. AsyncWebCrawler Context Management

Always use `async with` to properly manage browser resources:

```python
from crawl4ai import AsyncWebCrawler

# ✅ CORRECT: Context manager ensures cleanup
async with AsyncWebCrawler(verbose=True) as crawler:
    result = await service.crawl_webpage(crawler, url)
    # Crawler automatically cleaned up after block

# ❌ INCORRECT: Manual management (not recommended)
crawler = AsyncWebCrawler(verbose=True)
await crawler.__aenter__()
result = await service.crawl_webpage(crawler, url)
await crawler.__aexit__(None, None, None)
```

### 4. Error Handling Best Practices

Implement comprehensive error handling:

```python
from database.utility_services.crawling_service import CrawlingService, CrawlConfig
from pydantic import ValidationError
from crawl4ai import AsyncWebCrawler

async def robust_crawl(url: str, max_retries: int = 3):
    """Crawl with retry logic and proper error handling"""
    service = CrawlingService(CrawlConfig(max_depth=2, max_concurrent=5))
    
    for attempt in range(max_retries):
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await service.crawl_webpage(crawler, url)
                
                # Check for successful results
                if result.successful_count > 0:
                    print(f"✅ Success: {result.successful_count} pages crawled")
                    return result
                else:
                    print(f"⚠️  Attempt {attempt + 1}: No successful results")
                    print(f"   Failed count: {result.failed_count}")
                    
        except ValidationError as e:
            print(f"❌ Validation error on attempt {attempt + 1}: {e}")
        except Exception as e:
            print(f"❌ Error on attempt {attempt + 1}: {e}")
        
        # Exponential backoff
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            print(f"   Retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    print(f"❌ Failed after {max_retries} attempts")
    return None
```

### 5. Result Validation and Filtering

Validate crawled content before storage:

```python
from database.utility_services.crawling_service import CrawlResult, CrawlBatchResult

def validate_crawl_result(crawl_result: CrawlResult) -> bool:
    """
    Validate crawled content quality.
    Note: Basic validation is already done by Pydantic in CrawlResult.
    """
    # Content length check
    if len(crawl_result.markdown) < 100:
        print(f"⚠️  Content too short: {crawl_result.url}")
        return False
    
    # Check for error pages (common patterns)
    content_lower = crawl_result.markdown.lower()
    error_indicators = [
        "404", "not found", "page not found",
        "error", "access denied", "forbidden"
    ]
    if any(indicator in content_lower[:500] for indicator in error_indicators):
        print(f"⚠️  Error page detected: {crawl_result.url}")
        return False
    
    # Check for meaningful content (not just navigation)
    if content_lower.count('\n') < 5:
        print(f"⚠️  Insufficient content structure: {crawl_result.url}")
        return False
    
    return True

# Usage
async def crawl_and_validate(service, crawler, url):
    result = await service.crawl_webpage(crawler, url)
    
    if result.successful_count == 0:
        print("No pages crawled")
        return []
    
    # Filter valid results
    valid_results = [
        cr for cr in result.results
        if validate_crawl_result(cr)
    ]
    
    print(f"Valid results: {len(valid_results)}/{len(result.results)}")
    return valid_results
```

### 6. Memory and Performance Optimization

The `CrawlingService` automatically manages memory through the `MemoryAdaptiveDispatcher`:

```python
# The service internally creates a dispatcher with your config:
# dispatcher = MemoryAdaptiveDispatcher(
#     memory_threshold_percent=config.memory_threshold,  # Your configured threshold
#     check_interval=1.0,                                 # Checks every second
#     max_session_permit=config.max_concurrent,          # Your max concurrent sessions
# )

# For better performance:
config = CrawlConfig(
    max_depth=2,              # Reduce depth for speed
    max_concurrent=15,        # Increase concurrency
    memory_threshold=75.0     # Adjust based on your system
)

# Monitor results
result = await service.crawl_webpage(crawler, url)
print(f"Efficiency: {result.successful_count}/{result.total_urls_attempted}")
```

---

## Advanced Features

### 1. Understanding Internal Implementation

The `CrawlingService` internally uses these methods based on URL type:

```python
# For standard webpages (detected by default):
# - Uses _crawl_recursive_internal_links()
# - Follows internal links up to max_depth levels
# - Uses MemoryAdaptiveDispatcher for concurrency control

# For sitemaps (detected by is_sitemap()):
# - Uses _crawl_batch() after parsing sitemap with url_service.parse_sitemap()
# - Crawls all URLs from sitemap in parallel

# For text files (detected by is_txt()):
# - Uses _crawl_text_file()
# - Single page crawl with direct content extraction
```

### 2. Extending the CrawlingService

You can extend the service for custom behavior:

```python
from database.utility_services.crawling_service import CrawlingService, CrawlConfig
from crawl4ai import AsyncWebCrawler

class CustomCrawlingService(CrawlingService):
    """Extended crawling service with custom preprocessing"""
    
    def __init__(self, config: CrawlConfig = None):
        super().__init__(config)
        self.crawl_history = []
    
    async def crawl_webpage(self, crawler: AsyncWebCrawler, url: str):
        """Override to add custom logging"""
        print(f"[CustomService] Starting crawl for: {url}")
        
        # Call parent method
        result = await super().crawl_webpage(crawler, url)
        
        # Custom post-processing
        self.crawl_history.append({
            'url': url,
            'type': result.crawl_type.value,
            'success_count': result.successful_count,
            'failed_count': result.failed_count
        })
        
        print(f"[CustomService] Completed: {result.successful_count} successful")
        return result
    
    def get_statistics(self):
        """Get crawling statistics"""
        total_success = sum(h['success_count'] for h in self.crawl_history)
        total_failed = sum(h['failed_count'] for h in self.crawl_history)
        return {
            'total_crawls': len(self.crawl_history),
            'total_successful_pages': total_success,
            'total_failed_pages': total_failed,
            'history': self.crawl_history
        }


# Usage
async def main():
    service = CustomCrawlingService(CrawlConfig(max_depth=2))
    
    async with AsyncWebCrawler(verbose=False) as crawler:
        await service.crawl_webpage(crawler, "https://docs.python.org/3/")
        await service.crawl_webpage(crawler, "https://fastapi.tiangolo.com/")
    
    stats = service.get_statistics()
    print(f"Statistics: {stats}")
```

### 3. Direct Crawl4AI Usage for Advanced Features

For features not supported by `CrawlingService`, use Crawl4AI directly:

```python
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    CacheMode,
    LLMConfig,
    LLMContentFilter,
    DefaultMarkdownGenerator
)

async def advanced_llm_filtered_crawl():
    """
    Use LLM-powered content filtering (not available in CrawlingService)
    """
    # Configure LLM for content filtering
    llm_config = LLMConfig(
        provider="openai/gpt-4",
        api_token="env:OPENAI_API_KEY"
    )
    
    # Define filtering instructions
    content_filter = LLMContentFilter(
        llm_config=llm_config,
        instruction="""
        Extract only technical API documentation content.
        Include: endpoints, parameters, examples, return values
        Exclude: navigation, footers, ads, sidebars
        """,
        chunk_token_threshold=500,
        verbose=True
    )
    
    # Create markdown generator with filter
    md_generator = DefaultMarkdownGenerator(
        content_filter=content_filter,
        options={"ignore_links": False}
    )
    
    # Configure crawler
    run_config = CrawlerRunConfig(
        markdown_generator=md_generator,
        cache_mode=CacheMode.BYPASS
    )
    
    # Use crawler directly
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://docs.example.com/api",
            config=run_config
        )
        
        if result.success:
            print("LLM-filtered content:")
            print(result.markdown[:500])
```

### 4. Combining CrawlingService with Adaptive Crawling

For intelligent, query-focused crawling:

```python
from crawl4ai import AsyncWebCrawler, AdaptiveCrawler, AdaptiveConfig
from database.utility_services.crawling_service import CrawlingService, CrawlConfig

async def hybrid_crawling_approach():
    """
    Use AdaptiveCrawler for initial intelligent discovery,
    then CrawlingService for systematic crawling
    """
    
    # Step 1: Use AdaptiveCrawler to find relevant pages
    adaptive_config = AdaptiveConfig(
        confidence_threshold=0.85,
        max_depth=3,
        max_pages=20,
        strategy="statistical"
    )
    
    relevant_urls = []
    
    async with AsyncWebCrawler() as crawler:
        adaptive = AdaptiveCrawler(crawler, adaptive_config)
        
        result = await adaptive.digest(
            start_url="https://api.example.com/docs",
            query="authentication endpoints webhooks rate limits"
        )
        
        relevant_urls = result.crawled_urls
        print(f"Adaptive crawl found {len(relevant_urls)} relevant pages")
    
    # Step 2: Use CrawlingService to systematically crawl discovered pages
    service = CrawlingService(CrawlConfig(max_depth=1, max_concurrent=10))
    
    all_results = []
    async with AsyncWebCrawler(verbose=False) as crawler:
        for url in relevant_urls:
            result = await service.crawl_webpage(crawler, url)
            if result.successful_count > 0:
                all_results.extend(result.results)
    
    print(f"Total pages crawled: {len(all_results)}")
    return all_results
```

### 5. Batch Processing Pattern

Efficiently process multiple documentation sites:

```python
from database.utility_services.crawling_service import CrawlingService, CrawlConfig
from crawl4ai import AsyncWebCrawler
from typing import List, Dict
import asyncio

async def batch_documentation_crawl(sites: List[str]) -> Dict[str, any]:
    """
    Crawl multiple documentation sites efficiently.
    
    Args:
        sites: List of documentation URLs to crawl
        
    Returns:
        Dictionary with results per site
    """
    service = CrawlingService(CrawlConfig(
        max_depth=2,
        max_concurrent=10,
        memory_threshold=75.0
    ))
    
    results_by_site = {}
    
    # Reuse single crawler instance for all sites
    async with AsyncWebCrawler(verbose=False) as crawler:
        for site_url in sites:
            print(f"\n{'='*80}")
            print(f"Processing: {site_url}")
            
            try:
                result = await service.crawl_webpage(crawler, site_url)
                
                results_by_site[site_url] = {
                    'success': result.successful_count > 0,
                    'crawl_type': result.crawl_type.value,
                    'pages_crawled': result.successful_count,
                    'pages_failed': result.failed_count,
                    'results': [
                        {
                            'url': cr.url,
                            'content_length': len(cr.markdown),
                            'markdown': cr.markdown
                        }
                        for cr in result.results
                    ]
                }
                
                print(f"✅ Success: {result.successful_count} pages")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                results_by_site[site_url] = {
                    'success': False,
                    'error': str(e)
                }
    
    return results_by_site


# Usage
async def main():
    sites = [
        "https://docs.python.org/3/",
        "https://fastapi.tiangolo.com/",
        "https://docs.djangoproject.com/en/stable/"
    ]
    
    results = await batch_documentation_crawl(sites)
    
    # Print summary
    total_pages = sum(
        r.get('pages_crawled', 0)
        for r in results.values()
    )
    successful_sites = sum(
        1 for r in results.values()
        if r.get('success', False)
    )
    
    print(f"\n{'='*80}")
    print(f"Batch Crawl Summary:")
    print(f"  Total sites: {len(sites)}")
    print(f"  Successful: {successful_sites}")
    print(f"  Total pages crawled: {total_pages}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. No Results Returned

**Problem**: `crawl_webpage()` returns `CrawlBatchResult` with `successful_count=0`.

**Solution**:
```python
# Check the result details
result = await service.crawl_webpage(crawler, url)

if result.successful_count == 0:
    print(f"Failed count: {result.failed_count}")
    print(f"Crawl type: {result.crawl_type.value}")
    
    # For webpages: might be too deep or no internal links
    # For sitemaps: check if sitemap parsed correctly
    # For text files: check if URL is accessible

# Troubleshooting steps:
# 1. Verify URL is accessible in browser
# 2. Check if URL type is detected correctly
# 3. Try with increased max_depth
# 4. Check crawler verbose output for errors
```

#### 2. Memory Issues

**Problem**: Crawler runs out of memory during large crawls.

**Solution**:
```python
# Reduce concurrency and lower memory threshold
config = CrawlConfig(
    max_depth=2,              # Reduce depth
    max_concurrent=5,         # Lower concurrency
    memory_threshold=65.0     # More conservative (starts throttling earlier)
)

# The service will automatically throttle when memory exceeds threshold
service = CrawlingService(config)
```

#### 3. Slow Crawling Performance

**Problem**: Crawling takes too long for documentation sites.

**Solution**:
```python
# Increase concurrency
config = CrawlConfig(
    max_depth=2,              # Reduce depth if not needed
    max_concurrent=20,        # Increase concurrent sessions
    memory_threshold=80.0     # Allow higher memory usage
)

# For sitemaps, this will process more URLs in parallel
# For webpages, this will crawl more pages concurrently at each depth level
```

#### 4. Empty or Incomplete Content

**Problem**: Crawled pages return empty markdown or incomplete content.

**Solution**:
```python
# The CrawlingService uses default CrawlerRunConfig internally
# which should work for most cases, but some pages may need:

# 1. Check if content is actually present
async with AsyncWebCrawler(verbose=True) as crawler:
    # Verbose mode will show what's happening
    result = await service.crawl_webpage(crawler, url)

# 2. For JavaScript-heavy sites, you may need to use crawler directly
# with custom wait conditions (not currently supported by CrawlingService)

# 3. Verify the content with validation
for cr in result.results:
    if len(cr.markdown) < 100:
        print(f"Short content warning: {cr.url}")
```

#### 5. ValidationError Exceptions

**Problem**: Pydantic `ValidationError` raised when creating `CrawlResult`.

**Solution**:
```python
# This happens when:
# 1. URL doesn't start with http:// or https://
# 2. Markdown content is empty or only whitespace

# The service catches these internally, but if you see them:
from pydantic import ValidationError

try:
    result = await service.crawl_webpage(crawler, url)
except ValidationError as e:
    print(f"Validation error: {e}")
    # Check URL format and ensure content is being extracted

# The service should return failed_count instead of raising
# If you see ValidationError, there may be a bug in internal processing
```

#### 6. Sitemap Not Detected or Parsed

**Problem**: Sitemap URL not automatically detected or parsing fails.

**Solution**:
```python
from database.utility_services.url_service import UrlService

url_service = UrlService()

# Verify detection
sitemap_url = "https://example.com/sitemap.xml"
if url_service.is_sitemap(sitemap_url):
    print("✅ Sitemap detected")
else:
    print("❌ Not detected as sitemap")
    # Ensure URL ends with 'sitemap.xml' or has 'sitemap' in path

# Test parsing manually
urls = url_service.parse_sitemap(sitemap_url)
print(f"Found {len(urls)} URLs in sitemap")

# If parsing fails:
# 1. Check if sitemap is valid XML
# 2. Verify sitemap is accessible (not blocked)
# 3. Check for network/timeout issues
```

#### 7. AsyncWebCrawler Context Issues

**Problem**: Errors related to browser context or session management.

**Solution**:
```python
# ✅ ALWAYS use async with
async with AsyncWebCrawler(verbose=True) as crawler:
    result = await service.crawl_webpage(crawler, url)
    # Context properly managed

# ❌ DON'T reuse crawler outside context
crawler = None
async with AsyncWebCrawler() as crawler:
    result1 = await service.crawl_webpage(crawler, url1)
    
# crawler is now closed, don't use it again
# Create new context for more crawls:
async with AsyncWebCrawler() as crawler:
    result2 = await service.crawl_webpage(crawler, url2)
```

---

## Performance Optimization Checklist

- [ ] Choose appropriate `max_depth` based on site structure (2-3 for large sites)
- [ ] Set optimal `max_concurrent` based on system resources and memory
- [ ] Adjust `memory_threshold` based on available system memory
- [ ] Validate results before storage using custom validation logic
- [ ] Reuse `AsyncWebCrawler` context for multiple URLs
- [ ] Handle errors gracefully with try-except blocks
- [ ] Implement retry logic for failed crawls
- [ ] Monitor `successful_count` and `failed_count` for quality assurance
- [ ] Use sitemap URLs when available for faster discovery
- [ ] Filter results to remove error pages and short content

---

## API Reference

### CrawlConfig

```python
class CrawlConfig(BaseModel):
    max_depth: int = Field(3, ge=1, le=10)
    max_concurrent: int = Field(10, ge=1, le=50)
    memory_threshold: float = Field(70.0, ge=10.0, le=95.0)
    chunk_size: int = Field(4000, ge=500, le=8000)  # Currently unused
```

### CrawlResult

```python
class CrawlResult(BaseModel):
    url: str          # Validated: must start with http:// or https://
    markdown: str     # Validated: must not be empty
```

### CrawlBatchResult

```python
class CrawlBatchResult(BaseModel):
    results: List[CrawlResult]     # List of successful results
    crawl_type: CrawlType          # WEBPAGE, SITEMAP, or TEXT_FILE
    total_urls_attempted: int      # Total URLs tried
    successful_count: int          # Number of successful crawls
    failed_count: int              # Number of failed crawls
```

### CrawlType

```python
class CrawlType(str, Enum):
    TEXT_FILE = "text_file"    # .txt, .md, .markdown files
    SITEMAP = "sitemap"        # sitemap.xml files
    WEBPAGE = "webpage"        # Standard HTML pages
```

### CrawlingService

```python
class CrawlingService:
    def __init__(self, config: Optional[CrawlConfig] = None)
    
    async def crawl_webpage(
        self,
        crawler: AsyncWebCrawler,
        url: str
    ) -> CrawlBatchResult
```

### UrlService

```python
class UrlService:
    @staticmethod
    def is_sitemap(url: str) -> bool
    
    @staticmethod
    def is_txt(url: str) -> bool
    
    @staticmethod
    def get_domain(url: str) -> Optional[str]
    
    @staticmethod
    def normalize_url(url: str) -> str
    
    @staticmethod
    def parse_sitemap(sitemap_url: str) -> List[str]
```

---

## Additional Resources

- **Crawl4AI Documentation**: https://docs.crawl4ai.com
- **GitHub Repository**: https://github.com/unclecode/crawl4ai
- **Discord Community**: https://discord.gg/jP8KfhDhyN

---

## Summary

The `CrawlingService` provides a powerful, unified interface for crawling technical documentation with:

### Key Features

- ✅ **Automatic URL type detection** (webpage, sitemap, text file)
- ✅ **Unified configuration** via `CrawlConfig`
- ✅ **Built-in memory management** via `MemoryAdaptiveDispatcher`
- ✅ **Runtime configuration** (max_depth applied at crawl time)
- ✅ **Robust error handling** (returns `CrawlBatchResult` even on errors)
- ✅ **Pydantic validation** for results (URL and content validation)

### Basic Usage Pattern

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from database.utility_services.crawling_service import CrawlingService, CrawlConfig

async def main():
    # 1. Configure the service
    config = CrawlConfig(
        max_depth=3,              # How deep to crawl
        max_concurrent=10,        # Concurrent sessions
        memory_threshold=75.0     # Memory management
    )
    
    # 2. Initialize service
    service = CrawlingService(config)
    
    # 3. Crawl with AsyncWebCrawler context
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await service.crawl_webpage(crawler, "https://docs.python.org/3/")
        
        # 4. Check results
        if result.successful_count > 0:
            print(f"✅ Crawled {result.successful_count} pages")
            
            # 5. Process results
            for crawl_result in result.results:
                print(f"URL: {crawl_result.url}")
                print(f"Content: {len(crawl_result.markdown)} chars")
        else:
            print(f"❌ No pages crawled ({result.failed_count} failed)")

if __name__ == "__main__":
    asyncio.run(main())
```

### Important Notes

1. **AsyncWebCrawler Required**: The service requires an `AsyncWebCrawler` instance passed to `crawl_webpage()`
2. **Context Manager**: Always use `async with AsyncWebCrawler() as crawler:`
3. **Error Handling**: The service catches exceptions and returns a result object
4. **Validation**: Results are validated by Pydantic (URL format, non-empty content)
5. **chunk_size**: Currently unused in the implementation
6. **Custom CrawlerRunConfig**: Not currently supported; service uses internal defaults

This design provides a balance between simplicity and power for technical documentation crawling.
