"""URL processing, validation, and type detection utilities for context_bridge.

This module provides utilities for handling URLs in the crawling pipeline,
including normalization, validation, and type detection.
"""

from typing import Optional
from urllib.parse import urlparse, urljoin
import re
from pydantic import BaseModel, field_validator

from context_bridge.config import get_config


class UrlType(str):
    """Enumeration of supported URL types for crawling."""

    WEBPAGE = "WEBPAGE"
    SITEMAP = "SITEMAP"
    TEXT_FILE = "TEXT_FILE"


class UrlService:
    """Service for URL processing, validation, and type detection.

    Provides utilities for normalizing URLs, validating documentation URLs,
    and detecting URL types for crawling operations.
    """

    def __init__(self, config: Optional[BaseModel] = None) -> None:
        """Initialize UrlService with configuration.

        Args:
            config: Configuration instance. If None, uses get_config().
        """
        self.config = config or get_config()

    async def normalize_url(self, url: str) -> str:
        """Normalize a URL to a consistent format.

        Args:
            url: The URL to normalize.

        Returns:
            str: The normalized URL.

        Raises:
            ValueError: If URL is invalid.
        """
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")

        # Basic validation - URL should not start with ://
        if url.startswith("://"):
            raise ValueError("Invalid URL format")

        # Parse the URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")

        # Ensure scheme is present
        if not parsed.scheme:
            # Assume https if no scheme
            url = f"https://{url}"
            parsed = urlparse(url)

        # Validate scheme
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

        # Validate that we have a netloc (hostname)
        if not parsed.netloc or parsed.netloc == ":":
            raise ValueError("URL must include a valid hostname")

        # Normalize the URL
        normalized = parsed.geturl()

        return normalized

    async def is_valid_documentation_url(self, url: str) -> bool:
        """Check if a URL is valid for documentation crawling.

        Args:
            url: The URL to validate.

        Returns:
            bool: True if URL is valid for documentation crawling.
        """
        try:
            # First normalize to check validity
            normalized = await self.normalize_url(url)

            # Additional validation rules for documentation URLs
            parsed = urlparse(normalized)

            # Check for common documentation domains or patterns
            # This is a basic implementation - could be extended with config
            hostname = parsed.hostname
            if not hostname:
                return False

            # Basic hostname validation (should contain dot or be localhost)
            if "." not in hostname and hostname != "localhost":
                return False

            # Exclude common non-documentation sites
            excluded_domains = [
                "facebook.com",
                "twitter.com",
                "instagram.com",
                "youtube.com",
                "linkedin.com",
                "tiktok.com",
                "reddit.com",
                "pinterest.com",
            ]

            if any(excluded in hostname for excluded in excluded_domains):
                return False

            # Check path for common documentation patterns
            path = parsed.path.lower()
            doc_patterns = [
                "/docs",
                "/documentation",
                "/guide",
                "/manual",
                "/api",
                "/reference",
                "/tutorial",
                "/help",
                "/wiki",
            ]

            # Allow if path contains documentation patterns or if it's a known doc site
            doc_sites = [
                "github.com",
                "gitlab.com",
                "bitbucket.org",
                "readthedocs.org",
                "docs.microsoft.com",
                "developer.mozilla.org",
                "docs.oracle.com",
            ]

            has_doc_path = any(pattern in path for pattern in doc_patterns)
            is_doc_site = any(site in hostname for site in doc_sites)

            return has_doc_path or is_doc_site or True  # Default allow for now

        except ValueError:
            return False

    async def detect_url_type(self, url: str) -> str:
        """Detect the type of URL for crawling.

        Args:
            url: The URL to analyze.

        Returns:
            UrlType: The detected URL type.
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            query = parsed.query.lower()

            # Check for sitemap patterns
            sitemap_patterns = [
                r"/sitemap\.xml",
                r"/sitemap\.xml\.gz",
                r"/sitemap_index\.xml",
                r".*sitemap.*\.xml",
                r"/robots\.txt",  # Often contains sitemap references
            ]

            for pattern in sitemap_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return UrlType.SITEMAP

            # Check for text file patterns
            text_file_patterns = [
                r"\.txt$",
                r"\.md$",
                r"\.rst$",
                r"\.markdown$",
                r"/readme",
                r"/changelog",
                r"/license",
                r"/authors",
            ]

            for pattern in text_file_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    return UrlType.TEXT_FILE

            # Default to webpage for HTML content
            return UrlType.WEBPAGE

        except Exception:
            # If parsing fails, default to webpage
            return UrlType.WEBPAGE

    async def is_sitemap(self, url: str) -> bool:
        """Check if a URL points to a sitemap file.

        Args:
            url: The URL to check.

        Returns:
            bool: True if the URL appears to be a sitemap.
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            query = parsed.query.lower()

            # Check for sitemap patterns
            sitemap_patterns = [
                r"/sitemap\.xml",
                r"/sitemap\.xml\.gz",
                r"/sitemap_index\.xml",
                r".*sitemap.*\.xml",
                r"/robots\.txt",  # Often contains sitemap references
            ]

            for pattern in sitemap_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return True

            return False

        except Exception:
            return False

    async def is_txt(self, url: str) -> bool:
        """Check if a URL points to a text file.

        Args:
            url: The URL to check.

        Returns:
            bool: True if the URL appears to point to a text file.
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()

            # Check for text file patterns
            text_file_patterns = [
                r"\.txt$",
                r"\.md$",
                r"\.rst$",
                r"\.markdown$",
                r"/readme",
                r"/changelog",
                r"/license",
                r"/authors",
            ]

            for pattern in text_file_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    return True

            return False

        except Exception:
            return False

    async def get_domain(self, url: str) -> Optional[str]:
        """Extract the domain from a URL.

        Args:
            url: The URL to extract domain from.

        Returns:
            Optional[str]: The domain (hostname) if valid, None otherwise.
        """
        try:
            parsed = urlparse(url)
            if parsed.hostname:
                return parsed.hostname.lower()
            return None
        except Exception:
            return None
