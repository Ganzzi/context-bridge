"""Crawling service for web content extraction using Crawl4AI.

This module provides a unified interface for crawling different types of web content
including webpages, sitemaps, and text files, with automatic URL type detection
and memory-adaptive crawling.
"""

from typing import List, Optional
from enum import Enum
import logging
import asyncio
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from pydantic import BaseModel, field_validator

from context_bridge.service.url_service import UrlService, UrlType

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class CrawlType(str, Enum):
    """Enumeration of crawl types."""

    TEXT_FILE = "text_file"  # .txt, .md, .markdown files
    SITEMAP = "sitemap"  # sitemap.xml files
    WEBPAGE = "webpage"  # Standard HTML pages


class CrawlConfig(BaseModel):
    """Configuration for crawling operations."""

    max_depth: int = 3
    max_concurrent: int = 10
    memory_threshold: float = 70.0

    @field_validator("max_depth")
    def validate_depth(cls, v):
        if not 1 <= v <= 10:
            raise ValueError("max_depth must be between 1 and 10")
        return v

    @field_validator("max_concurrent")
    def validate_concurrent(cls, v):
        if not 1 <= v <= 50:
            raise ValueError("max_concurrent must be between 1 and 50")
        return v

    @field_validator("memory_threshold")
    def validate_memory_threshold(cls, v):
        if not 10.0 <= v <= 95.0:
            raise ValueError("memory_threshold must be between 10.0 and 95.0")
        return v


class CrawlResult(BaseModel):
    """Result of a single crawl operation."""

    url: str
    markdown: str

    @field_validator("url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("markdown")
    def validate_markdown(cls, v):
        if not v or not v.strip():
            raise ValueError("markdown content must not be empty")
        return v


class CrawlBatchResult(BaseModel):
    """Result of a batch crawl operation."""

    results: List[CrawlResult]
    crawl_type: CrawlType
    total_urls_attempted: int
    successful_count: int
    failed_count: int


class CrawlingService:
    """Service for orchestrating web crawling operations.

    Provides a unified interface for crawling different types of web content
    with automatic URL type detection and memory-adaptive crawling.
    """

    def __init__(self, config: CrawlConfig, url_service: UrlService):
        """Initialize the crawling service.

        Args:
            config: Crawling configuration
            url_service: URL processing service
        """
        self.config = config
        self.url_service = url_service

    async def crawl_webpage(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        depth: Optional[int] = None,
        follow_links: bool = True,
    ) -> CrawlBatchResult:
        """Crawl a webpage with automatic type detection and dispatch.

        Args:
            crawler: AsyncWebCrawler instance to use for crawling
            url: URL to crawl
            depth: Optional override for max_depth from config (1-10)
            follow_links: Whether to follow internal links recursively

        Returns:
            CrawlBatchResult: Results of the crawl operation
        """
        logger.info(f"Starting crawl for URL: {url}")

        try:
            # Validate URL first
            if not url or not isinstance(url, str):
                raise ValueError("URL must be a non-empty string")

            # Validate and set depth
            if depth is not None:
                if not 1 <= depth <= 10:
                    raise ValueError("depth must be between 1 and 10")
                crawl_depth = depth
                logger.info(f"Using custom depth: {crawl_depth}")
            else:
                crawl_depth = self.config.max_depth
                logger.info(f"Using config depth: {crawl_depth}")

            # Normalize URL first
            normalized_url = await self.url_service.normalize_url(url)
            logger.debug(f"Normalized URL: {normalized_url}")

            # Detect URL type
            url_type_str = await self.url_service.detect_url_type(normalized_url)
            logger.info(f"Detected URL type: {url_type_str}")

            # Map UrlType to CrawlType
            crawl_type_mapping = {
                UrlType.WEBPAGE: CrawlType.WEBPAGE,
                UrlType.SITEMAP: CrawlType.SITEMAP,
                UrlType.TEXT_FILE: CrawlType.TEXT_FILE,
            }
            crawl_type = crawl_type_mapping.get(url_type_str, CrawlType.WEBPAGE)

            # Dispatch to appropriate crawling method
            if crawl_type == CrawlType.WEBPAGE:
                logger.info("Dispatching to webpage crawler")
                return await self._crawl_recursive_internal_links(
                    crawler, normalized_url, crawl_depth, follow_links
                )
            elif crawl_type == CrawlType.SITEMAP:
                logger.info("Dispatching to sitemap crawler")
                return await self._crawl_batch(crawler, normalized_url)
            elif crawl_type == CrawlType.TEXT_FILE:
                logger.info("Dispatching to text file crawler")
                return await self._crawl_text_file(crawler, normalized_url)
            else:
                # Fallback to webpage crawling
                logger.warning(f"Unknown crawl type {crawl_type}, falling back to webpage")
                return await self._crawl_recursive_internal_links(
                    crawler, normalized_url, crawl_depth, follow_links
                )

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            # Return empty result on error
            return CrawlBatchResult(
                results=[],
                crawl_type=CrawlType.WEBPAGE,
                total_urls_attempted=1,
                successful_count=0,
                failed_count=1,
            )

    async def _crawl_recursive_internal_links(
        self, crawler: AsyncWebCrawler, url: str, max_depth: int, follow_links: bool = True
    ) -> CrawlBatchResult:
        """Crawl a webpage recursively following internal links.

        Args:
            crawler: AsyncWebCrawler instance
            url: Starting URL to crawl
            max_depth: Maximum depth to follow links
            follow_links: Whether to follow internal links

        Returns:
            CrawlBatchResult: Results of the recursive crawl
        """
        logger.info(f"Starting recursive crawl from {url} with max_depth={max_depth}")

        # Normalize URL by removing fragment
        url = url.split("#")[0]
        visited = set()
        to_visit = [url]
        results = []
        successful_count = 0
        failed_count = 0

        for depth in range(max_depth + 1):
            if not to_visit:
                break

            logger.info(f"Crawling depth {depth}: {len(to_visit)} URLs")
            current_level_urls = to_visit[:]
            to_visit = []

            # Crawl all URLs at current depth concurrently
            semaphore = asyncio.Semaphore(self.config.max_concurrent)

            async def crawl_single_page(page_url: str) -> tuple:
                async with semaphore:
                    if page_url in visited:
                        return None, None

                    visited.add(page_url)

                    try:
                        result = await crawler.arun(url=page_url)
                        if result.success and result.markdown:
                            # Extract the markdown content
                            markdown_str = None
                            if hasattr(result.markdown, "markdown"):
                                markdown_str = result.markdown.markdown
                            elif hasattr(result.markdown, "content"):
                                markdown_str = result.markdown.content
                            else:
                                markdown_str = str(result.markdown)

                            # Extract internal links for next depth
                            internal_links = self._extract_internal_links(markdown_str, page_url)
                            return (
                                CrawlResult(url=page_url, markdown=markdown_str),
                                internal_links,
                            )
                        else:
                            return None, []
                    except Exception as e:
                        logger.error(f"Error crawling {page_url}: {e}")
                        return None, []

            # Crawl current level
            tasks = [crawl_single_page(page_url) for page_url in current_level_urls]
            crawl_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result_tuple in crawl_results:
                if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
                    crawl_result, internal_links = result_tuple
                    if crawl_result:
                        results.append(crawl_result)
                        successful_count += 1
                        # Add new internal links for next depth if following links
                        if follow_links:
                            for link in internal_links:
                                if link not in visited and link not in to_visit:
                                    to_visit.append(link)
                    else:
                        failed_count += 1
                else:
                    failed_count += 1

        logger.info(
            f"Recursive crawl completed: {successful_count} successful, {failed_count} failed"
        )
        return CrawlBatchResult(
            results=results,
            crawl_type=CrawlType.WEBPAGE,
            total_urls_attempted=len(visited),
            successful_count=successful_count,
            failed_count=failed_count,
        )

    def _extract_internal_links(self, markdown: str, base_url: str) -> List[str]:
        """Extract internal links from markdown content.

        Args:
            markdown: Markdown content
            base_url: Base URL for resolving relative links

        Returns:
            List of internal URLs
        """
        import re
        from urllib.parse import urljoin, urlparse

        links = []
        base_parsed = urlparse(base_url)
        base_domain = f"{base_parsed.scheme}://{base_parsed.netloc}"

        # Extract markdown links [text](url)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        matches = re.findall(link_pattern, markdown)
        for _, url in matches:
            # Skip anchor links
            if url.startswith("#"):
                continue

            # Resolve relative URLs
            if not url.startswith(("http://", "https://")):
                url = urljoin(base_url, url)

            # Normalize by removing fragment
            url = url.split("#")[0]

            # Only include links from the same domain
            if urlparse(url).netloc == base_parsed.netloc:
                links.append(url)

        return links

    async def _crawl_batch(self, crawler: AsyncWebCrawler, url: str) -> CrawlBatchResult:
        """Crawl multiple URLs from a sitemap.

        Args:
            crawler: AsyncWebCrawler instance
            url: Sitemap URL

        Returns:
            CrawlBatchResult: Results of the batch crawl
        """
        try:
            # First, fetch and parse the sitemap
            sitemap_result = await crawler.arun(url=url)
            if not sitemap_result.success:
                return CrawlBatchResult(
                    results=[],
                    crawl_type=CrawlType.SITEMAP,
                    total_urls_attempted=1,
                    successful_count=0,
                    failed_count=1,
                )

            # Parse URLs from sitemap content
            urls = self._parse_sitemap_urls(sitemap_result.markdown, url)

            if not urls:
                return CrawlBatchResult(
                    results=[],
                    crawl_type=CrawlType.SITEMAP,
                    total_urls_attempted=1,
                    successful_count=0,
                    failed_count=1,
                )

            # Crawl all URLs from the sitemap
            results = []
            successful_count = 0
            failed_count = 0

            # Limit concurrent requests based on config
            semaphore = asyncio.Semaphore(self.config.max_concurrent)

            async def crawl_single_url(crawl_url: str) -> Optional[CrawlResult]:
                async with semaphore:
                    try:
                        result = await crawler.arun(url=crawl_url)
                        if result.success and result.markdown:
                            # Try different ways to get the content
                            markdown_str = None
                            if hasattr(result.markdown, "markdown"):
                                markdown_str = result.markdown.markdown
                            elif hasattr(result.markdown, "content"):
                                markdown_str = result.markdown.content
                            else:
                                markdown_str = str(result.markdown)

                            return CrawlResult(url=crawl_url, markdown=markdown_str)
                        return None
                    except Exception as e:
                        logger.error(f"Error crawling {crawl_url}: {e}")
                        return None

            # Crawl all URLs concurrently (limit to 50 for now)
            tasks = [crawl_single_url(crawl_url) for crawl_url in urls[:50]]
            crawl_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in crawl_results:
                if isinstance(result, CrawlResult):
                    results.append(result)
                    successful_count += 1
                else:
                    failed_count += 1

            return CrawlBatchResult(
                results=results,
                crawl_type=CrawlType.SITEMAP,
                total_urls_attempted=len(urls),
                successful_count=successful_count,
                failed_count=failed_count,
            )

        except Exception as e:
            logger.error(f"Error crawling sitemap {url}: {e}")
            return CrawlBatchResult(
                results=[],
                crawl_type=CrawlType.SITEMAP,
                total_urls_attempted=1,
                successful_count=0,
                failed_count=1,
            )

    def _parse_sitemap_urls(self, sitemap_content: str, base_url: str) -> List[str]:
        """Parse URLs from sitemap XML content.

        Args:
            sitemap_content: Raw sitemap XML content
            base_url: Base URL for resolving relative URLs

        Returns:
            List of URLs found in the sitemap
        """
        import re
        from urllib.parse import urljoin

        urls = []
        # Simple regex to extract URLs from sitemap XML
        # Look for <loc> tags
        loc_pattern = r"<loc[^>]*>([^<]+)</loc>"
        matches = re.findall(loc_pattern, sitemap_content, re.IGNORECASE)

        base_parsed = urlparse(base_url)
        base_domain = f"{base_parsed.scheme}://{base_parsed.netloc}"

        for match in matches:
            url = match.strip()
            # Resolve relative URLs
            if not url.startswith(("http://", "https://")):
                url = urljoin(base_domain, url)

            # Only include URLs from the same domain
            if urlparse(url).netloc == base_parsed.netloc:
                urls.append(url)

        return urls

    async def _crawl_text_file(self, crawler: AsyncWebCrawler, url: str) -> CrawlBatchResult:
        """Crawl a text/markdown file directly.

        Args:
            crawler: AsyncWebCrawler instance
            url: Text file URL

        Returns:
            CrawlBatchResult: Results of the text file crawl
        """
        try:
            # For text files, we can use the crawler directly
            result = await crawler.arun(url=url)
            if result.success and result.markdown:
                # Extract the markdown content
                markdown_str = None
                if hasattr(result.markdown, "markdown"):
                    markdown_str = result.markdown.markdown
                elif hasattr(result.markdown, "content"):
                    markdown_str = result.markdown.content
                else:
                    markdown_str = str(result.markdown)

                crawl_result = CrawlResult(url=url, markdown=markdown_str)
                return CrawlBatchResult(
                    results=[crawl_result],
                    crawl_type=CrawlType.TEXT_FILE,
                    total_urls_attempted=1,
                    successful_count=1,
                    failed_count=0,
                )
            else:
                return CrawlBatchResult(
                    results=[],
                    crawl_type=CrawlType.TEXT_FILE,
                    total_urls_attempted=1,
                    successful_count=0,
                    failed_count=1,
                )
        except Exception as e:
            logger.error(f"Error crawling text file {url}: {e}")
            return CrawlBatchResult(
                results=[],
                crawl_type=CrawlType.TEXT_FILE,
                total_urls_attempted=1,
                successful_count=0,
                failed_count=1,
            )
