"""
Context Bridge - Unified Public API

This module provides the main ContextBridge class, which serves as the unified
entry point for all Context Bridge functionality including document crawling,
page management, chunking, embedding generation, and search operations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging
import asyncio
from datetime import datetime
from uuid import UUID

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
from context_bridge.service.reprocessing_service import ReprocessingService
from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.database.repositories.tag_repository import TagRepository
from context_bridge.database.repositories.group_repository import GroupRepository
from context_bridge.database.models.tag_models import Tag, TagCreate, TagUpdate, TagCategory

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

    Configuration supports three patterns:

    **Pattern 1: Direct Python (Recommended for PyPI users)**
    ```python
    from context_bridge import ContextBridge, Config

    config = Config(
        postgres_host="localhost",
        postgres_password="secure_pass",
        embedding_model="nomic-embed-text:latest"
    )

    async with ContextBridge(config=config) as bridge:
        result = await bridge.crawl_documentation(
            name="psqlpy",
            version="0.9.0",
            source_url="https://psqlpy.readthedocs.io"
        )
        pages = await bridge.list_pages(result.document_id)
        chunk_result = await bridge.process_pages(result.document_id, [p.id for p in pages[:10]])
        results = await bridge.search(
            query="connection pooling",
            document_id=result.document_id
        )
    ```

    **Pattern 2: Environment Variables (Recommended for Docker/K8s)**
    ```bash
    export POSTGRES_HOST=localhost
    export POSTGRES_PASSWORD=secure_pass
    export EMBEDDING_MODEL=nomic-embed-text:latest
    ```
    ```python
    from context_bridge import ContextBridge

    async with ContextBridge() as bridge:
        result = await bridge.crawl_documentation(...)
    ```

    **Pattern 3: .env File (Convenient for local development)**
    ```bash
    # .env (git-ignored)
    POSTGRES_HOST=localhost
    POSTGRES_PASSWORD=devpass
    EMBEDDING_MODEL=nomic-embed-text:latest
    ```
    ```python
    # Automatically loaded if python-dotenv is available
    from context_bridge import ContextBridge

    async with ContextBridge() as bridge:
        result = await bridge.crawl_documentation(...)
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
            config: Optional Config object. If not provided, creates a new Config
                   that loads from environment variables and .env file (if available).

        Example:
            ```python
            # With explicit config
            config = Config(postgres_host="localhost", ...)
            bridge = ContextBridge(config=config)

            # With environment variables / .env
            bridge = ContextBridge()
            ```
        """
        self.config = config or Config()
        self._db_manager: Optional[PostgreSQLManager] = None
        self._doc_manager: Optional[DocManager] = None
        self._search_service: Optional[SearchService] = None
        self._tag_repository: Optional[TagRepository] = None
        self._group_repository: Optional[GroupRepository] = None
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
            self._tag_repository = TagRepository(self._db_manager)
            self._group_repository = GroupRepository(self._db_manager)

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
        additional_urls: Optional[List[str]] = None,
    ) -> CrawlAndStoreResult:
        """
        Crawl and store documentation from a URL.

        Args:
            name: Document name
            version: Document version
            source_url: Primary URL to crawl
            description: Optional description
            max_depth: Optional crawl depth override (1-10)
            additional_urls: Optional list of additional URLs to crawl with the same depth

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
            additional_urls=additional_urls,
        )

    async def find_documents(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        name: Optional[str] = None,
        version: Optional[str] = None,
        id: Optional[int] = None,
        tags: Optional[List[int]] = None,
        tag_match_all: bool = False,
    ) -> List[Document]:
        """
        Find documents by query or filters, or list all documents.
        If query is provided, searches document name, description, and metadata.
        If name/version/id filters are provided, filters by those fields.
        If tags are provided, filters documents by tags.
        If no filters, returns all documents with pagination.
        Returns documents sorted by relevance (for search) or creation date.

        Args:
            query: Optional search query string
            limit: Maximum number of results to return
            offset: Pagination offset
            name: Optional name filter (exact match)
            version: Optional version filter (exact match)
            id: Optional ID filter (exact match)
            tags: Optional list of tag IDs to filter by
            tag_match_all: If True, return only documents with ALL tags;
                          if False, return documents with ANY tag (default)

        Returns:
            List of Document objects with tags populated

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        if query is not None:
            search_results = await self._search_service.find_documents(query=query, limit=limit)
            docs = [result.document for result in search_results]
        else:
            # Use repository for filtering/listing
            async with self._db_manager.connection() as conn:
                doc_repo = DocumentRepository(self._db_manager)
                if id is not None:
                    doc = await doc_repo.get_by_id(id)
                    docs = [doc] if doc else []
                elif name is not None or version is not None:
                    # For now, implement simple filtering - could be enhanced
                    all_docs = await doc_repo.list_all(
                        limit=1000, offset=0
                    )  # Get all for filtering
                    filtered = []
                    for doc in all_docs:
                        if name and doc.name != name:
                            continue
                        if version and doc.version != version:
                            continue
                        filtered.append(doc)
                    # Apply pagination
                    start = offset
                    end = offset + limit
                    docs = filtered[start:end]
                else:
                    docs = await doc_repo.list_all(limit=limit, offset=offset)

        # Filter by tags if provided
        if tags:
            tag_filtered_docs = []
            for doc in docs:
                doc_tags = await self._tag_repository.get_document_tags(doc.id)
                doc_tag_ids = [t.id for t in doc_tags]

                if tag_match_all:
                    # All requested tags must be present
                    if all(tag_id in doc_tag_ids for tag_id in tags):
                        doc.tags = doc_tag_ids
                        tag_filtered_docs.append(doc)
                else:
                    # At least one requested tag must be present
                    if any(tag_id in doc_tag_ids for tag_id in tags):
                        doc.tags = doc_tag_ids
                        tag_filtered_docs.append(doc)

            return tag_filtered_docs
        else:
            # Populate tags for all documents
            for doc in docs:
                doc_tags = await self._tag_repository.get_document_tags(doc.id)
                doc.tags = [t.id for t in doc_tags]

            return docs

    async def list_documents(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Document]:
        """
        List all documents with pagination.

        Args:
            limit: Maximum number of results to return
            offset: Pagination offset

        Returns:
            List of Document objects ordered by creation date (newest first)

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        async with self._db_manager.connection() as conn:
            doc_repo = DocumentRepository(self._db_manager)
            return await doc_repo.list_all(limit=limit, offset=offset)

    async def get_document(self, name: str, version: str) -> Optional[Document]:
        """
        Get a specific document by name and version.

        Args:
            name: Document name
            version: Document version

        Returns:
            Document object or None if not found

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        async with self._db_manager.connection() as conn:
            doc_repo = DocumentRepository(conn)
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
        return await self._doc_manager.delete_document(document_id)

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
        self,
        document_id: int,
        page_ids: List[int],
        chunk_size: Optional[int] = None,
        context_enabled: bool = False,
        context_model: Optional[str] = None,
        run_async: bool = True,
    ) -> ChunkProcessingResult:
        """
        Process pages for chunking and embedding with optional AI context generation.

        Validates pages, combines content, chunks, generates embeddings,
        and stores chunks with source page tracking. Optionally generates AI-powered
        context for each chunk to improve search relevance.

        Args:
            document_id: Document ID
            page_ids: List of page IDs to process together
            chunk_size: Optional chunk size override
            context_enabled: Whether to generate AI context for chunks
            context_model: The model to use for context generation
                          (e.g., "anthropic:claude-3-5-sonnet-20241022")
            run_async: If True, run in background task. If False, run synchronously.

        Returns:
            ChunkProcessingResult with summary

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If page validation fails
        """
        self._check_initialized()
        return await self._doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            chunk_size=chunk_size,
            context_enabled=context_enabled,
            context_model=context_model or self.config.context_agent_model,
            run_async=run_async,
        )

    async def wait_for_chunking_completion(
        self,
        document_id: int,
        page_ids: List[int],
        timeout_seconds: int = 60,
        poll_interval: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Wait for chunking processing to complete for specified pages.

        Polls the page status until all pages are either 'chunked' or 'deleted',
        or timeout is reached.

        Args:
            document_id: Document ID
            page_ids: List of page IDs that were submitted for processing
            timeout_seconds: Maximum time to wait in seconds
            poll_interval: How often to check status in seconds

        Returns:
            Dictionary with completion status and statistics

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()

        import time

        start_time = time.time()

        logger.info(
            f"⏳ Waiting for chunking completion of {len(page_ids)} pages in document {document_id}"
        )

        while time.time() - start_time < timeout_seconds:
            # Check status of all pages
            all_pages = await self.list_pages(document_id)
            page_status_map = {p.id: p.status for p in all_pages if p.id in page_ids}

            # Count statuses
            processing = sum(1 for status in page_status_map.values() if status == "processing")
            chunked = sum(1 for status in page_status_map.values() if status == "chunked")
            deleted = sum(1 for status in page_status_map.values() if status == "deleted")
            pending = sum(1 for status in page_status_map.values() if status == "pending")

            total_accounted = processing + chunked + deleted + pending

            logger.debug(
                f"Chunking status: processing={processing}, chunked={chunked}, deleted={deleted}, pending={pending}, total={total_accounted}/{len(page_ids)}"
            )

            # Check if all pages are done processing
            if processing == 0 and total_accounted == len(page_ids):
                # Get chunk count
                chunk_repo = ChunkRepository(self._db_manager)
                chunk_count = await chunk_repo.count_by_document(document_id)

                elapsed = time.time() - start_time
                result = {
                    "completed": True,
                    "elapsed_seconds": elapsed,
                    "pages_processed": len(page_ids),
                    "pages_chunked": chunked,
                    "pages_deleted": deleted,
                    "pages_pending": pending,
                    "chunks_created": chunk_count,
                    "timeout": False,
                }

                logger.info(
                    f"✅ Chunking completed in {elapsed:.1f}s: {chunked} pages chunked, {chunk_count} chunks created"
                )
                return result

            await asyncio.sleep(poll_interval)

        # Timeout reached
        elapsed = time.time() - start_time
        logger.warning(f"⏰ Chunking wait timeout after {elapsed:.1f}s")

        # Get final status
        all_pages = await self.list_pages(document_id)
        page_status_map = {p.id: p.status for p in all_pages if p.id in page_ids}

        processing = sum(1 for status in page_status_map.values() if status == "processing")
        chunked = sum(1 for status in page_status_map.values() if status == "chunked")
        deleted = sum(1 for status in page_status_map.values() if status == "deleted")
        pending = sum(1 for status in page_status_map.values() if status == "pending")

        chunk_repo = ChunkRepository(self._db_manager)
        chunk_count = await chunk_repo.count_by_document(document_id)

        return {
            "completed": False,
            "elapsed_seconds": elapsed,
            "pages_processed": len(page_ids),
            "pages_chunked": chunked,
            "pages_deleted": deleted,
            "pages_pending": pending,
            "pages_still_processing": processing,
            "chunks_created": chunk_count,
            "timeout": True,
        }

    async def get_chunk_stats(self, document_id: int) -> Dict[str, Any]:
        """
        Get chunk statistics for a document.

        Args:
            document_id: Document ID

        Returns:
            Dictionary with chunk statistics

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()

        chunk_repo = ChunkRepository(self._db_manager)
        chunk_count = await chunk_repo.count_by_document(document_id)

        # Get page status counts
        all_pages = await self.list_pages(document_id)
        page_stats = {}
        for page in all_pages:
            page_stats[page.status] = page_stats.get(page.status, 0) + 1

        return {
            "document_id": document_id,
            "total_chunks": chunk_count,
            "page_status_counts": page_stats,
        }

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
            document_name: Name of the document to search across versions
            limit_per_version: Maximum results per version

        Returns:
            Dictionary mapping version strings to lists of ContentSearchResult

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._search_service.search_across_versions(
            query=query, document_name=document_name, limit_per_version=limit_per_version
        )

    # Tag Operations

    async def list_tags(self, category: Optional[TagCategory] = None) -> List[Tag]:
        """
        List all available tags, optionally filtered by category.

        Args:
            category: Optional TagCategory to filter by

        Returns:
            List of Tag objects

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._tag_repository.list_tags(category=category)

    async def get_document_tags(self, document_id: int) -> List[Tag]:
        """
        Get all tags for a document.

        Args:
            document_id: Document ID

        Returns:
            List of Tag objects associated with the document

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._tag_repository.get_document_tags(document_id)

    # Group Management Operations

    async def list_groups(
        self, document_id: Optional[int] = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List groups for a document or all groups across all documents.

        Args:
            document_id: Optional document ID to filter by. If None, lists all groups.
            limit: Maximum number of results to return
            offset: Pagination offset

        Returns:
            List of group dictionaries with metadata:
            - id: UUID of the group
            - name: Optional human-readable name
            - description: Optional description
            - context_enabled: Whether context generation is enabled
            - total_pages: Number of pages in group
            - total_chunks: Number of chunks in group
            - processing_status: Current status (pending, processing, completed, failed, reprocessing)
            - created_at: Creation timestamp
            - processed_at: Processing completion timestamp

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()

        if document_id is None:
            # List all groups across all documents
            all_groups = await self._group_repository.list_groups(
                document_id=None, limit=limit, offset=offset
            )
        else:
            # List groups for specific document
            all_groups = await self._group_repository.list_groups(
                document_id=document_id, limit=limit, offset=offset
            )

        # Convert Pydantic models to dictionaries
        result = []
        for group in all_groups:
            result.append(
                {
                    "id": str(group.id),
                    "document_id": group.document_id,
                    "name": group.name,
                    "description": group.description,
                    "context_enabled": group.context_enabled,
                    "context_model": group.context_model,
                    "total_pages": group.total_pages,
                    "total_chunks": group.total_chunks,
                    "processing_status": group.processing_status,
                    "created_at": group.created_at.isoformat(),
                    "processed_at": group.processed_at.isoformat() if group.processed_at else None,
                }
            )

        return result

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
