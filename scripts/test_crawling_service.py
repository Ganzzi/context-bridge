#!/usr/bin/env python3
"""
Quick test of the CrawlingService implementation.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge.service import CrawlingService, UrlService
from context_bridge.service.crawling_service import CrawlConfig
from crawl4ai import AsyncWebCrawler


async def test_crawling_service():
    """Test basic CrawlingService functionality."""
    print("🧪 Testing CrawlingService...")

    # Create config
    config = CrawlConfig(max_depth=2, max_concurrent=5, memory_threshold=75.0)
    print(
        f"✅ Created config: max_depth={config.max_depth}, max_concurrent={config.max_concurrent}"
    )

    # Create URL service
    url_service = UrlService()
    print("✅ Created URL service")

    # Create crawling service
    crawling_service = CrawlingService(config, url_service)
    print("✅ Created crawling service")

    # Test URL type detection
    test_urls = [
        "https://example.com/page",
        "https://example.com/sitemap.xml",
        "https://example.com/README.md",
    ]

    for url in test_urls:
        url_type = await url_service.detect_url_type(url)
        print(f"✅ URL {url} detected as: {url_type}")

    print("🎉 All basic tests passed!")


async def test_real_crawling():
    """Test crawling with real URLs."""
    print("\n🌐 Testing real URL crawling...")

    # Create config with conservative settings for testing
    config = CrawlConfig(max_depth=1, max_concurrent=2, memory_threshold=80.0)
    print(
        f"✅ Created config: max_depth={config.max_depth}, max_concurrent={config.max_concurrent}"
    )

    # Create services
    url_service = UrlService()
    crawling_service = CrawlingService(config, url_service)
    print("✅ Created crawling service")

    # Test URLs - using reliable, lightweight sites
    test_urls = [
        "https://httpbin.org/html",  # Simple HTML page
        "https://raw.githubusercontent.com/microsoft/vscode/main/README.md",  # Text file
    ]

    async with AsyncWebCrawler(verbose=False) as crawler:
        for i, url in enumerate(test_urls, 1):
            print(f"\n📄 Test {i}: Crawling {url}")
            try:
                result = await crawling_service.crawl_webpage(crawler, url)

                print(f"   ✅ Crawl Type: {result.crawl_type.value}")
                print(f"   ✅ URLs Attempted: {result.total_urls_attempted}")
                print(f"   ✅ Successful: {result.successful_count}")
                print(f"   ✅ Failed: {result.failed_count}")

                if result.successful_count > 0:
                    print(f"   📝 Sample content (first 200 chars):")
                    content = result.results[0].markdown[:200]
                    print(
                        f"      {content}{'...' if len(result.results[0].markdown) > 200 else ''}"
                    )
                else:
                    print("   ❌ No successful results")

            except Exception as e:
                print(f"   ❌ Error crawling {url}: {e}")

    print("\n🎉 Real crawling tests completed!")


async def main():
    """Run all tests."""
    await test_crawling_service()
    await test_real_crawling()


if __name__ == "__main__":
    asyncio.run(main())
