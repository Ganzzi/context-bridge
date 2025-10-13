"""
Context Bridge - Unified Public API

This module provides the main ContextBridge class, which serves as the unified
entry point for all Context Bridge functionality including document crawling,
page management, chunking, embedding generation, and search operations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.service.doc_manager import (
    DocManager,
    CrawlAndStoreResult,
    ChunkProcessingResult,
    PageInfo,
)
from context_bridge.service.search_service import SearchService, ContentSearchResult
from context_bridge.service.crawling_service import CrawlingService, CrawlConfig
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService
from context_bridge.service.url_service import UrlService
from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from context_bridge.database.repositories.chunk_repository import ChunkRepository

logger = logging.getLogger(__name__)


class ContextBridge:
    """
    Unified API for Context Bridge functionality.

    This class provides a simple interface for:
    - Crawling and storing documentation
    - Managing pages
    - Processing chunks with embeddings
    - Searching documentation content
    - Managing documents

    Example:
        ```python
        from context_bridge import ContextBridge

        # Initialize
        bridge = ContextBridge()
        await bridge.initialize()

        # Crawl documentation
        result = await bridge.crawl_documentation(
            name="psqlpy",
            version="0.9.0",
            source_url="https://psqlpy.readthedocs.io"
        )

        # List pages
        pages = await bridge.list_pages(result.document_id)

        # Process chunking
        page_ids = [p.id for p in pages[:10]]
        chunk_result = await bridge.process_pages(result.document_id, page_ids)

        # Search
        results = await bridge.search(
            query="connection pooling",
            document_id=result.document_id
        )

        # Cleanup
        await bridge.close()
        ```

    Context Manager Support:
        ```python
        async with ContextBridge() as bridge:
            result = await bridge.crawl_documentation("mylib", "1.0.0", "https://docs.example.com")
            pages = await bridge.list_pages(result.document_id)
        ```
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize ContextBridge.

        Args:
            config: Optional configuration. If not provided, loads from environment.
        """
        self.config = config or Config()
        self._db_manager: Optional[PostgreSQLManager] = None
        self._doc_manager: Optional[DocManager] = None
        self._search_service: Optional[SearchService] = None
        self._initialized = False

        logger.info("ContextBridge instance created")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def initialize(self) -> None:
        """
        Initialize database connections and services.
        Must be called before using any other methods.
        """
        if self._initialized:
            logger.warning("ContextBridge already initialized")
            return

        logger.info("Initializing ContextBridge...")

        # Initialize database
        self._db_manager = PostgreSQLManager(self.config)
        await self._db_manager.initialize()

        # Initialize services
        url_service = UrlService()
        crawl_config = CrawlConfig(
            max_depth=self.config.crawl_max_depth, max_concurrent=self.config.crawl_max_concurrent
        )
        crawling_service = CrawlingService(crawl_config, url_service)
        chunking_service = ChunkingService(default_chunk_size=self.config.chunk_size)
        embedding_service = EmbeddingService(self.config)

        # Initialize high-level services
        self._doc_manager = DocManager(
            db_manager=self._db_manager,
            crawling_service=crawling_service,
            chunking_service=chunking_service,
            embedding_service=embedding_service,
            config=self.config,
        )

        async with self._db_manager.connection() as conn:
            doc_repo = DocumentRepository(self._db_manager)
            chunk_repo = ChunkRepository(self._db_manager)
            self._search_service = SearchService(
                document_repo=doc_repo, chunk_repo=chunk_repo, embedding_service=embedding_service
            )

        self._initialized = True
        logger.info("ContextBridge initialized successfully")

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        if self._db_manager:
            await self._db_manager.close()
        self._initialized = False
        logger.info("ContextBridge closed")

    def _check_initialized(self) -> None:
        """Verify that initialize() has been called."""
        if not self._initialized:
            raise RuntimeError(
                "ContextBridge not initialized. Call await bridge.initialize() first."
            )

    # Document Operations

    async def crawl_documentation(
        self,
        name: str,
        version: str,
        source_url: str,
        description: Optional[str] = None,
        max_depth: Optional[int] = None,
    ) -> CrawlAndStoreResult:
        """
        Crawl and store documentation from a URL.

        Args:
            name: Document name
            version: Document version
            source_url: URL to crawl
            description: Optional description
            max_depth: Optional crawl depth override (1-10)

        Returns:
            CrawlAndStoreResult with summary

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If parameters are invalid
        """
        self._check_initialized()
        return await self._doc_manager.crawl_and_store(
            name=name,
            version=version,
            source_url=source_url,
            description=description,
            max_depth=max_depth,
        )

    async def list_documents(self, offset: int = 0, limit: int = 100) -> List[Document]:
        """
        List all documents with pagination.

        Args:
            offset: Pagination offset
            limit: Maximum results

        Returns:
            List of Document objects

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        doc_repo = DocumentRepository(self._db_manager)
        return await doc_repo.list_all(offset=offset, limit=limit)

    async def get_document(self, name: str, version: str) -> Optional[Document]:
        """
        Get a specific document by name and version.

        Args:
            name: Document name
            version: Document version

        Returns:
            Document or None if not found

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        doc_repo = DocumentRepository(self._db_manager)
        return await doc_repo.get_by_name_version(name, version)

    async def delete_document(self, document_id: int) -> bool:
        """
        Delete a document and all related data (pages, chunks).

        Args:
            document_id: Document ID to delete

        Returns:
            True if successful

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        doc_repo = DocumentRepository(self._db_manager)
        return await doc_repo.delete(document_id)

    # Page Operations

    async def list_pages(
        self, document_id: int, status: Optional[str] = None, offset: int = 0, limit: int = 100
    ) -> List[PageInfo]:
        """
        List pages for a document.

        Args:
            document_id: Document ID
            status: Optional status filter ('pending', 'chunked', 'deleted')
            offset: Pagination offset
            limit: Maximum results

        Returns:
            List of PageInfo objects

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._doc_manager.list_pages(
            document_id=document_id, status=status, offset=offset, limit=limit
        )

    async def delete_page(self, page_id: int) -> bool:
        """
        Delete a page (soft delete).

        Args:
            page_id: Page ID to delete

        Returns:
            True if successful

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._doc_manager.delete_page(page_id)

    # Chunking Operations

    async def process_pages(
        self, document_id: int, page_ids: List[int], chunk_size: Optional[int] = None
    ) -> ChunkProcessingResult:
        """
        Process pages for chunking and embedding.

        Validates pages, combines content, chunks, generates embeddings,
        and stores chunks with source page tracking.

        Args:
            document_id: Document ID
            page_ids: List of page IDs to process together
            chunk_size: Optional chunk size override

        Returns:
            ChunkProcessingResult with summary

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If page validation fails
        """
        self._check_initialized()
        return await self._doc_manager.process_chunking(
            document_id=document_id, page_ids=page_ids, chunk_size=chunk_size
        )

    # Search Operations

    async def search(
        self,
        query: str,
        document_id: int,
        limit: int = 10,
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None,
    ) -> List[ContentSearchResult]:
        """
        Search within document content using hybrid search.

        Args:
            query: Search query
            document_id: Document ID to search within
            limit: Maximum results
            vector_weight: Optional vector search weight (0-1)
            bm25_weight: Optional BM25 search weight (0-1)

        Returns:
            List of ContentSearchResult objects ranked by relevance

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._search_service.search_content(
            query=query,
            document_id=document_id,
            limit=limit,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )

    async def search_across_versions(
        self, query: str, document_name: str, limit_per_version: int = 5
    ) -> Dict[str, List[ContentSearchResult]]:
        """
        Search across all versions of a document.

        Args:
            query: Search query
            document_name: Document name
            limit_per_version: Maximum results per version

        Returns:
            Dict mapping version -> list of results

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._search_service.search_across_versions(
            query=query, document_name=document_name, limit_per_version=limit_per_version
        )

    # Utility Methods

    def get_config(self) -> Config:
        """
        Get the current configuration.

        Returns:
            Config object
        """
        return self.config

    def is_initialized(self) -> bool:
        """
        Check if ContextBridge is initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of all services.

        Returns:
            Dictionary with health status of each component

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()

        health = {
            "initialized": True,
            "database": False,
            "embedding_service": False,
            "services": {},
        }

        # Check database
        try:
            async with self._db_manager.connection() as conn:
                await conn.execute("SELECT 1")
            health["database"] = True
        except Exception as e:
            health["database_error"] = str(e)

        # Check embedding service
        try:
            health["embedding_service"] = (
                await self._doc_manager.embedding_service.verify_connection()
            )
        except Exception as e:
            health["embedding_service_error"] = str(e)

        # Check services
        health["services"] = {
            "doc_manager": self._doc_manager is not None,
            "search_service": self._search_service is not None,
        }

        return health
