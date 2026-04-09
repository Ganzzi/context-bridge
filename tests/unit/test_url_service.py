"""Tests for the UrlService."""

import pytest
from unittest.mock import patch

from context_bridge.service.url_service import UrlService, UrlType
from context_bridge.config import Config


class TestUrlType:
    """Test UrlType enum."""

    def test_url_type_values(self):
        """Test UrlType enum values."""
        assert UrlType.WEBPAGE == "WEBPAGE"
        assert UrlType.SITEMAP == "SITEMAP"
        assert UrlType.TEXT_FILE == "TEXT_FILE"

    def test_url_type_is_str(self):
        """Test UrlType inherits from str."""
        assert isinstance(UrlType.WEBPAGE, str)


class TestUrlService:
    """Test UrlService functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        return Config()

    @pytest.fixture
    def service(self, mock_config):
        """Create a UrlService instance."""
        return UrlService(config=mock_config)

    def test_init_with_config(self, mock_config):
        """Test initializing service with custom config."""
        service = UrlService(config=mock_config)
        assert service.config == mock_config

    def test_init_without_config(self):
        """Test initializing service without config (uses global)."""
        with patch("context_bridge.service.url_service.get_config") as mock_get_config:
            mock_get_config.return_value = Config()
            service = UrlService()
            assert service.config is not None

    @pytest.mark.asyncio
    async def test_normalize_url_valid_https(self, service):
        """Test normalizing a valid HTTPS URL."""
        url = "https://example.com/path"
        normalized = await service.normalize_url(url)
        assert normalized == "https://example.com/path"

    @pytest.mark.asyncio
    async def test_normalize_url_valid_http(self, service):
        """Test normalizing a valid HTTP URL."""
        url = "http://example.com/path"
        normalized = await service.normalize_url(url)
        assert normalized == "http://example.com/path"

    @pytest.mark.asyncio
    async def test_normalize_url_without_scheme(self, service):
        """Test normalizing URL without scheme (adds https)."""
        url = "example.com/path"
        normalized = await service.normalize_url(url)
        assert normalized == "https://example.com/path"

    @pytest.mark.asyncio
    async def test_normalize_url_with_query_and_fragment(self, service):
        """Test normalizing URL with query and fragment."""
        url = "https://example.com/path?query=value#fragment"
        normalized = await service.normalize_url(url)
        assert normalized == "https://example.com/path?query=value#fragment"

    @pytest.mark.asyncio
    async def test_normalize_url_invalid_scheme(self, service):
        """Test normalizing URL with invalid scheme."""
        url = "ftp://example.com/path"
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            await service.normalize_url(url)

    @pytest.mark.asyncio
    async def test_normalize_url_empty_string(self, service):
        """Test normalizing empty string."""
        with pytest.raises(ValueError, match="URL must be a non-empty string"):
            await service.normalize_url("")

    @pytest.mark.asyncio
    async def test_normalize_url_none(self, service):
        """Test normalizing None."""
        with pytest.raises(ValueError, match="URL must be a non-empty string"):
            await service.normalize_url(None)  # type: ignore

    @pytest.mark.asyncio
    async def test_normalize_url_invalid_format(self, service):
        """Test normalizing invalid URL format."""
        with pytest.raises(ValueError, match="Invalid URL format"):
            await service.normalize_url("://invalid")

    @pytest.mark.asyncio
    async def test_is_valid_documentation_url_valid(self, service):
        """Test validating a valid documentation URL."""
        url = "https://docs.example.com/guide"
        assert await service.is_valid_documentation_url(url) is True

    @pytest.mark.asyncio
    async def test_is_valid_documentation_url_github(self, service):
        """Test validating GitHub documentation URL."""
        url = "https://github.com/user/repo/blob/main/README.md"
        assert await service.is_valid_documentation_url(url) is True

    @pytest.mark.asyncio
    async def test_is_valid_documentation_url_readthedocs(self, service):
        """Test validating Read the Docs URL."""
        url = "https://project.readthedocs.io/en/latest/"
        assert await service.is_valid_documentation_url(url) is True

    @pytest.mark.asyncio
    async def test_is_valid_documentation_url_social_media(self, service):
        """Test validating social media URL (should be invalid)."""
        url = "https://facebook.com/page"
        assert await service.is_valid_documentation_url(url) is False

    @pytest.mark.asyncio
    async def test_is_valid_documentation_url_invalid_url(self, service):
        """Test validating invalid URL."""
        url = "not-a-url"
        assert await service.is_valid_documentation_url(url) is False

    @pytest.mark.asyncio
    async def test_is_valid_documentation_url_empty_hostname(self, service):
        """Test validating URL with empty hostname."""
        url = "https:///path"
        assert await service.is_valid_documentation_url(url) is False

    @pytest.mark.asyncio
    async def test_detect_url_type_webpage(self, service):
        """Test detecting webpage URL type."""
        url = "https://example.com/page.html"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.WEBPAGE

    @pytest.mark.asyncio
    async def test_detect_url_type_sitemap_xml(self, service):
        """Test detecting sitemap XML URL type."""
        url = "https://example.com/sitemap.xml"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.SITEMAP

    @pytest.mark.asyncio
    async def test_detect_url_type_sitemap_gz(self, service):
        """Test detecting compressed sitemap URL type."""
        url = "https://example.com/sitemap.xml.gz"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.SITEMAP

    @pytest.mark.asyncio
    async def test_detect_url_type_robots_txt(self, service):
        """Test detecting robots.txt URL type."""
        url = "https://example.com/robots.txt"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.SITEMAP

    @pytest.mark.asyncio
    async def test_detect_url_type_text_file_md(self, service):
        """Test detecting Markdown file URL type."""
        url = "https://example.com/README.md"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.TEXT_FILE

    @pytest.mark.asyncio
    async def test_detect_url_type_text_file_txt(self, service):
        """Test detecting text file URL type."""
        url = "https://example.com/changelog.txt"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.TEXT_FILE

    @pytest.mark.asyncio
    async def test_detect_url_type_text_file_license(self, service):
        """Test detecting license file URL type."""
        url = "https://example.com/LICENSE"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.TEXT_FILE

    @pytest.mark.asyncio
    async def test_detect_url_type_case_insensitive(self, service):
        """Test URL type detection is case insensitive."""
        url = "https://example.com/SITEMAP.XML"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.SITEMAP

    @pytest.mark.asyncio
    async def test_detect_url_type_invalid_url(self, service):
        """Test URL type detection with invalid URL (defaults to webpage)."""
        url = "not-a-url"
        url_type = await service.detect_url_type(url)
        assert url_type == UrlType.WEBPAGE

    @pytest.mark.asyncio
    async def test_is_sitemap_xml(self, service):
        """Test is_sitemap with sitemap.xml URL."""
        url = "https://example.com/sitemap.xml"
        assert await service.is_sitemap(url) is True

    @pytest.mark.asyncio
    async def test_is_sitemap_gz(self, service):
        """Test is_sitemap with compressed sitemap URL."""
        url = "https://example.com/sitemap.xml.gz"
        assert await service.is_sitemap(url) is True

    @pytest.mark.asyncio
    async def test_is_sitemap_index(self, service):
        """Test is_sitemap with sitemap index URL."""
        url = "https://example.com/sitemap_index.xml"
        assert await service.is_sitemap(url) is True

    @pytest.mark.asyncio
    async def test_is_sitemap_robots_txt(self, service):
        """Test is_sitemap with robots.txt URL."""
        url = "https://example.com/robots.txt"
        assert await service.is_sitemap(url) is True

    @pytest.mark.asyncio
    async def test_is_sitemap_custom_sitemap(self, service):
        """Test is_sitemap with custom sitemap URL."""
        url = "https://example.com/custom-sitemap.xml"
        assert await service.is_sitemap(url) is True

    @pytest.mark.asyncio
    async def test_is_sitemap_case_insensitive(self, service):
        """Test is_sitemap is case insensitive."""
        url = "https://example.com/SITEMAP.XML"
        assert await service.is_sitemap(url) is True

    @pytest.mark.asyncio
    async def test_is_sitemap_not_sitemap(self, service):
        """Test is_sitemap with non-sitemap URL."""
        url = "https://example.com/page.html"
        assert await service.is_sitemap(url) is False

    @pytest.mark.asyncio
    async def test_is_sitemap_invalid_url(self, service):
        """Test is_sitemap with invalid URL."""
        url = "not-a-url"
        assert await service.is_sitemap(url) is False

    @pytest.mark.asyncio
    async def test_is_txt_markdown(self, service):
        """Test is_txt with Markdown file URL."""
        url = "https://example.com/README.md"
        assert await service.is_txt(url) is True

    @pytest.mark.asyncio
    async def test_is_txt_text_file(self, service):
        """Test is_txt with text file URL."""
        url = "https://example.com/changelog.txt"
        assert await service.is_txt(url) is True

    @pytest.mark.asyncio
    async def test_is_txt_rst(self, service):
        """Test is_txt with RST file URL."""
        url = "https://example.com/docs.rst"
        assert await service.is_txt(url) is True

    @pytest.mark.asyncio
    async def test_is_txt_license(self, service):
        """Test is_txt with license file URL."""
        url = "https://example.com/LICENSE"
        assert await service.is_txt(url) is True

    @pytest.mark.asyncio
    async def test_is_txt_readme_path(self, service):
        """Test is_txt with readme in path."""
        url = "https://example.com/some/readme"
        assert await service.is_txt(url) is True

    @pytest.mark.asyncio
    async def test_is_txt_case_insensitive(self, service):
        """Test is_txt is case insensitive."""
        url = "https://example.com/README.MD"
        assert await service.is_txt(url) is True

    @pytest.mark.asyncio
    async def test_is_txt_not_text_file(self, service):
        """Test is_txt with non-text file URL."""
        url = "https://example.com/page.html"
        assert await service.is_txt(url) is False

    @pytest.mark.asyncio
    async def test_is_txt_invalid_url(self, service):
        """Test is_txt with invalid URL."""
        url = "not-a-url"
        assert await service.is_txt(url) is False

    @pytest.mark.asyncio
    async def test_get_domain_valid_url(self, service):
        """Test get_domain with valid URL."""
        url = "https://example.com/path"
        domain = await service.get_domain(url)
        assert domain == "example.com"

    @pytest.mark.asyncio
    async def test_get_domain_with_subdomain(self, service):
        """Test get_domain with subdomain."""
        url = "https://docs.example.com/guide"
        domain = await service.get_domain(url)
        assert domain == "docs.example.com"

    @pytest.mark.asyncio
    async def test_get_domain_http_url(self, service):
        """Test get_domain with HTTP URL."""
        url = "http://example.com/path"
        domain = await service.get_domain(url)
        assert domain == "example.com"

    @pytest.mark.asyncio
    async def test_get_domain_case_preservation(self, service):
        """Test get_domain converts to lowercase."""
        url = "https://EXAMPLE.COM/path"
        domain = await service.get_domain(url)
        assert domain == "example.com"

    @pytest.mark.asyncio
    async def test_get_domain_invalid_url(self, service):
        """Test get_domain with invalid URL."""
        url = "not-a-url"
        domain = await service.get_domain(url)
        assert domain is None

    @pytest.mark.asyncio
    async def test_get_domain_empty_hostname(self, service):
        """Test get_domain with URL that has no hostname."""
        url = "https:///path"
        domain = await service.get_domain(url)
        assert domain is None
