"""Tests for the CrawlingService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from context_bridge.service.crawling_service import (
    CrawlingService,
    CrawlConfig,
    CrawlResult,
    CrawlBatchResult,
    CrawlType,
)
from context_bridge.service.url_service import UrlService, UrlType


class TestCrawlType:
    """Test CrawlType enum."""

    def test_crawl_type_values(self):
        """Test CrawlType enum values."""
        assert CrawlType.TEXT_FILE == "text_file"
        assert CrawlType.SITEMAP == "sitemap"
        assert CrawlType.WEBPAGE == "webpage"

    def test_crawl_type_is_str(self):
        """Test CrawlType inherits from str."""
        assert isinstance(CrawlType.WEBPAGE, str)


class TestCrawlConfig:
    """Test CrawlConfig model."""

    def test_valid_config(self):
        """Test creating valid config."""
        config = CrawlConfig(max_depth=3, max_concurrent=10, memory_threshold=70.0)
        assert config.max_depth == 3
        assert config.max_concurrent == 10
        assert config.memory_threshold == 70.0

    def test_default_config(self):
        """Test default config values."""
        config = CrawlConfig()
        assert config.max_depth == 3
        assert config.max_concurrent == 10
        assert config.memory_threshold == 70.0

    def test_invalid_max_depth(self):
        """Test validation of max_depth."""
        with pytest.raises(ValidationError):
            CrawlConfig(max_depth=0)
        with pytest.raises(ValidationError):
            CrawlConfig(max_depth=11)

    def test_invalid_max_concurrent(self):
        """Test validation of max_concurrent."""
        with pytest.raises(ValidationError):
            CrawlConfig(max_concurrent=0)
        with pytest.raises(ValidationError):
            CrawlConfig(max_concurrent=51)

    def test_invalid_memory_threshold(self):
        """Test validation of memory_threshold."""
        with pytest.raises(ValidationError):
            CrawlConfig(memory_threshold=5.0)
        with pytest.raises(ValidationError):
            CrawlConfig(memory_threshold=100.0)


class TestCrawlResult:
    """Test CrawlResult model."""

    def test_valid_result(self):
        """Test creating valid crawl result."""
        result = CrawlResult(url="https://example.com", markdown="# Hello World")
        assert result.url == "https://example.com"
        assert result.markdown == "# Hello World"

    def test_invalid_url(self):
        """Test validation of URL."""
        with pytest.raises(ValidationError):
            CrawlResult(url="not-a-url", markdown="content")
        with pytest.raises(ValidationError):
            CrawlResult(url="ftp://example.com", markdown="content")

    def test_empty_markdown(self):
        """Test validation of markdown content."""
        with pytest.raises(ValidationError):
            CrawlResult(url="https://example.com", markdown="")
        with pytest.raises(ValidationError):
            CrawlResult(url="https://example.com", markdown="   ")


class TestCrawlBatchResult:
    """Test CrawlBatchResult model."""

    def test_valid_batch_result(self):
        """Test creating valid batch result."""
        results = [
            CrawlResult(url="https://example.com/page1", markdown="# Page 1"),
            CrawlResult(url="https://example.com/page2", markdown="# Page 2"),
        ]
        batch = CrawlBatchResult(
            results=results,
            crawl_type=CrawlType.WEBPAGE,
            total_urls_attempted=2,
            successful_count=2,
            failed_count=0,
        )
        assert len(batch.results) == 2
        assert batch.crawl_type == CrawlType.WEBPAGE
        assert batch.successful_count == 2
        assert batch.failed_count == 0


class TestCrawlingService:
    """Test CrawlingService functionality."""

    @pytest.fixture
    def mock_url_service(self):
        """Create a mock URL service."""
        service = MagicMock(spec=UrlService)
        service.normalize_url = AsyncMock(return_value="https://example.com")
        service.detect_url_type = AsyncMock(return_value=UrlType.WEBPAGE)
        return service

    @pytest.fixture
    def mock_crawler(self):
        """Create a mock AsyncWebCrawler."""
        crawler = MagicMock()
        crawler.arun = AsyncMock()
        return crawler

    @pytest.fixture
    def config(self):
        """Create test config."""
        return CrawlConfig(max_depth=2, max_concurrent=5, memory_threshold=75.0)

    @pytest.fixture
    def service(self, config, mock_url_service):
        """Create CrawlingService instance."""
        return CrawlingService(config, mock_url_service)

    @pytest.mark.asyncio
    async def test_init(self, config, mock_url_service):
        """Test service initialization."""
        service = CrawlingService(config, mock_url_service)
        assert service.config == config
        assert service.url_service == mock_url_service

    @pytest.mark.asyncio
    async def test_crawl_webpage_invalid_url(self, service, mock_crawler):
        """Test crawling with invalid URL."""
        result = await service.crawl_webpage(mock_crawler, "")
        assert result.successful_count == 0
        assert result.failed_count == 1
        assert result.crawl_type == CrawlType.WEBPAGE

    @pytest.mark.asyncio
    async def test_crawl_webpage_invalid_depth(self, service, mock_crawler):
        """Test crawling with invalid depth parameter."""
        result = await service.crawl_webpage(mock_crawler, "https://example.com", depth=0)
        assert result.successful_count == 0
        assert result.failed_count == 1

        result = await service.crawl_webpage(mock_crawler, "https://example.com", depth=11)
        assert result.successful_count == 0
        assert result.failed_count == 1

    @pytest.mark.asyncio
    async def test_crawl_webpage_webpage_type(self, service, mock_crawler, mock_url_service):
        """Test crawling webpage type."""
        # Setup mocks
        mock_url_service.detect_url_type.return_value = UrlType.WEBPAGE
        mock_crawler.arun.return_value = MagicMock(success=True, markdown="# Test content")

        result = await service.crawl_webpage(mock_crawler, "https://example.com")

        assert result.crawl_type == CrawlType.WEBPAGE
        assert result.successful_count == 1
        assert result.failed_count == 0
        assert len(result.results) == 1
        assert result.results[0].url == "https://example.com"
        assert result.results[0].markdown == "# Test content"

    @pytest.mark.asyncio
    async def test_crawl_webpage_sitemap_type(self, service, mock_crawler, mock_url_service):
        """Test crawling sitemap type."""
        # Setup mocks
        mock_url_service.detect_url_type.return_value = UrlType.SITEMAP
        mock_crawler.arun.return_value = MagicMock(
            success=True, markdown="<loc>https://example.com/page1</loc>"
        )

        result = await service.crawl_webpage(mock_crawler, "https://example.com/sitemap.xml")

        assert result.crawl_type == CrawlType.SITEMAP
        # Sitemap parsing will be tested separately

    @pytest.mark.asyncio
    async def test_crawl_webpage_text_file_type(self, service, mock_crawler, mock_url_service):
        """Test crawling text file type."""
        # Setup mocks
        mock_url_service.detect_url_type.return_value = UrlType.TEXT_FILE
        mock_crawler.arun.return_value = MagicMock(success=True, markdown="# README content")

        result = await service.crawl_webpage(mock_crawler, "https://example.com/README.md")

        assert result.crawl_type == CrawlType.TEXT_FILE
        assert result.successful_count == 1
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_crawl_webpage_custom_depth(self, service, mock_crawler, mock_url_service):
        """Test crawling with custom depth parameter."""
        # Setup mocks
        mock_url_service.detect_url_type.return_value = UrlType.WEBPAGE
        mock_crawler.arun.return_value = MagicMock(success=True, markdown="# Test content")

        result = await service.crawl_webpage(mock_crawler, "https://example.com", depth=1)

        assert result.successful_count == 1
        # Verify that the custom depth was used (would need deeper mocking for full verification)

    @pytest.mark.asyncio
    async def test_crawl_webpage_crawler_failure(self, service, mock_crawler, mock_url_service):
        """Test crawling when crawler fails."""
        # Setup mocks
        mock_url_service.detect_url_type.return_value = UrlType.WEBPAGE
        mock_crawler.arun.return_value = MagicMock(success=False, markdown="")

        result = await service.crawl_webpage(mock_crawler, "https://example.com")

        assert result.successful_count == 0
        assert result.failed_count == 1

    @pytest.mark.asyncio
    async def test_crawl_webpage_exception_handling(self, service, mock_crawler, mock_url_service):
        """Test exception handling in crawl_webpage."""
        # Setup mocks to raise exception
        mock_url_service.normalize_url.side_effect = Exception("Network error")

        result = await service.crawl_webpage(mock_crawler, "https://example.com")

        assert result.successful_count == 0
        assert result.failed_count == 1

    def test_extract_internal_links(self, service):
        """Test internal link extraction."""
        markdown = """
        # Main Page

        [Link 1](https://example.com/page1)
        [Link 2](/page2)
        [Link 3](page3)
        [External](https://other.com/page)
        [Anchor](#section)
        """

        links = service._extract_internal_links(markdown, "https://example.com")

        expected_links = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]

        assert set(links) == set(expected_links)

    def test_parse_sitemap_urls(self, service):
        """Test sitemap URL parsing."""
        sitemap_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/page1</loc>
            </url>
            <url>
                <loc>https://example.com/page2</loc>
            </url>
            <url>
                <loc>https://other.com/page3</loc>
            </url>
        </urlset>
        """

        urls = service._parse_sitemap_urls(sitemap_content, "https://example.com/sitemap.xml")

        expected_urls = ["https://example.com/page1", "https://example.com/page2"]

        assert set(urls) == set(expected_urls)

    @pytest.mark.asyncio
    async def test_crawl_text_file_success(self, service, mock_crawler):
        """Test successful text file crawling."""
        mock_crawler.arun.return_value = MagicMock(success=True, markdown="# Markdown content")

        result = await service._crawl_text_file(mock_crawler, "https://example.com/README.md")

        assert result.crawl_type == CrawlType.TEXT_FILE
        assert result.successful_count == 1
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_crawl_text_file_failure(self, service, mock_crawler):
        """Test failed text file crawling."""
        mock_crawler.arun.return_value = MagicMock(success=False, markdown="")

        result = await service._crawl_text_file(mock_crawler, "https://example.com/README.md")

        assert result.crawl_type == CrawlType.TEXT_FILE
        assert result.successful_count == 0
        assert result.failed_count == 1

    @pytest.mark.asyncio
    async def test_crawl_batch_sitemap_failure(self, service, mock_crawler):
        """Test sitemap batch crawling when sitemap fetch fails."""
        mock_crawler.arun.return_value = MagicMock(success=False, markdown="")

        result = await service._crawl_batch(mock_crawler, "https://example.com/sitemap.xml")

        assert result.crawl_type == CrawlType.SITEMAP
        assert result.successful_count == 0
        assert result.failed_count == 1
