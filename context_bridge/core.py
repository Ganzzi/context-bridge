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
from context_bridge.services.reprocessing_service import ReprocessingService
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

    async def add_tags_to_document(self, document_id: int, tag_ids: List[int]) -> int:
        """
        Add one or more tags to a document.

        Args:
            document_id: Document ID
            tag_ids: List of tag IDs to add

        Returns:
            Number of tags successfully added

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If document_id is invalid
        """
        self._check_initialized()
        return await self._tag_repository.add_tags_to_document(document_id, tag_ids)

    async def remove_tag_from_document(self, document_id: int, tag_id: int) -> bool:
        """
        Remove a tag from a document.

        Args:
            document_id: Document ID
            tag_id: Tag ID to remove

        Returns:
            True if successful, False otherwise

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._tag_repository.remove_tag_from_document(document_id, tag_id)

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

    async def remove_all_tags_from_document(self, document_id: int) -> int:
        """
        Remove all tags from a document.

        Args:
            document_id: Document ID

        Returns:
            Number of tags removed

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._tag_repository.remove_all_tags_from_document(document_id)

    async def get_documents_by_tag(
        self, tag_id: int, limit: int = 100, offset: int = 0
    ) -> List[Document]:
        """
        Get all documents with a specific tag.

        Args:
            tag_id: Tag ID to filter by
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            List of Document objects with the tag

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        document_ids = await self._tag_repository.get_documents_by_tag(
            tag_id=tag_id, limit=limit, offset=offset
        )

        # Fetch full document objects
        async with self._db_manager.connection() as conn:
            doc_repo = DocumentRepository(self._db_manager)
            documents = []
            for doc_id in document_ids:
                doc = await doc_repo.get_by_id(doc_id)
                if doc:
                    doc_tags = await self._tag_repository.get_document_tags(doc_id)
                    doc.tags = [t.id for t in doc_tags]
                    documents.append(doc)
            return documents

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

    async def get_group_info(self, group_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific group.

        Args:
            group_id: UUID of the group (as string)

        Returns:
            Dictionary with group information including:
            - id: UUID of the group
            - name: Optional human-readable name
            - description: Optional description
            - context_enabled: Whether context generation is enabled
            - context_model: Model used for context generation
            - total_pages: Number of pages in group
            - total_chunks: Number of chunks in group
            - combined_content_length: Total character count of all content
            - processing_status: Current status
            - created_at: Creation timestamp
            - processed_at: Processing completion timestamp
            - statistics: Additional statistics including:
              - chunk_count: Number of chunks
              - avg_chunk_size: Average chunk size
              - total_content_length: Total content length

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If group not found

        """
        self._check_initialized()

        # Parse UUID from string
        try:
            parsed_group_id = UUID(group_id)
        except ValueError:
            raise ValueError(f"Invalid group ID format: {group_id}")

        # Get group
        group = await self._group_repository.get_group_by_id(parsed_group_id)
        if not group:
            raise ValueError(f"Group not found: {group_id}")

        # Get group statistics
        stats = await self._group_repository.get_group_statistics(parsed_group_id)

        return {
            "id": str(group.id),
            "document_id": group.document_id,
            "name": group.name,
            "description": group.description,
            "context_enabled": group.context_enabled,
            "context_model": group.context_model,
            "total_pages": group.total_pages,
            "total_chunks": group.total_chunks,
            "combined_content_length": group.combined_content_length,
            "processing_status": group.processing_status,
            "created_at": group.created_at.isoformat(),
            "processed_at": group.processed_at.isoformat() if group.processed_at else None,
            "statistics": stats,
        }

    async def generate_context_for_group(
        self,
        group_id: str,
        context_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI context for a group's chunks.

        This method processes all chunks in a group and generates AI-powered
        contextual summaries using the specified LLM model. Contexts are
        prepended to chunk content to improve search relevance.

        Args:
            group_id: UUID of the group as string
            context_model: Optional model override. If not provided, uses config default.

        Returns:
            Dictionary with context generation results:
            - status: "success" or "failed"
            - chunks_processed: Number of chunks with context generated
            - chunks_failed: Number of chunks that failed
            - context_model: Model used for generation
            - timestamp: When generation occurred

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If group not found or invalid ID format
        """
        self._check_initialized()

        try:
            parsed_group_id = UUID(group_id)
        except ValueError:
            raise ValueError(f"Invalid group ID format: {group_id}")

        # Get group
        group = await self._group_repository.get_group_by_id(parsed_group_id)
        if not group:
            raise ValueError(f"Group not found: {group_id}")

        # Use provided model or config default
        model = context_model or self.config.context_agent_model

        # Delegate to DocManager for actual processing
        result = await self._doc_manager.process_group(
            parsed_group_id, context_enabled=True, context_model=model
        )

        return {
            "status": result.get("status", "unknown"),
            "chunks_processed": result.get("chunks_created", 0),
            "chunks_failed": result.get("errors", 0),
            "context_model": model,
            "timestamp": datetime.now().isoformat(),
        }

    async def list_non_context_groups(
        self,
        document_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List groups that do not have context generation enabled.

        Useful for finding groups that could benefit from context generation
        to improve search relevance.

        Args:
            document_id: Optional document ID to filter by

        Returns:
            List of group dictionaries with basic info

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()

        non_context_groups = await self._group_repository.get_non_context_groups(document_id)

        return [
            {
                "id": str(group.id),
                "document_id": group.document_id,
                "name": group.name,
                "total_pages": group.total_pages,
                "total_chunks": group.total_chunks,
                "processing_status": group.processing_status,
                "created_at": group.created_at.isoformat(),
            }
            for group in non_context_groups
        ]

    async def reprocess_group_with_context(
        self,
        group_id: UUID,
        context_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Re-process a group with AI-generated context.

        This method is used to:
        - Regenerate chunks for existing groups
        - Add AI context to chunks that didn't have it before
        - Update group processing status

        The operation:
        1. Validates the group exists and is not already context-enabled
        2. Marks group as REPROCESSING
        3. Deletes existing chunks for the group
        4. Retrieves pages for the group
        5. Combines page content
        6. Chunks the combined content
        7. Generates AI context for chunks (if context_model provided)
        8. Creates embeddings
        9. Stores chunks with context
        10. Updates group to COMPLETED

        Args:
            group_id: UUID of the group to re-process
            context_model: Optional context model (e.g., "anthropic:claude-3-5-sonnet-20241022")
                          If None, skips context generation

        Returns:
            Dictionary containing:
            - success: bool - Whether re-processing succeeded
            - group_id: UUID - The group ID
            - chunks_created: int - Number of new chunks created
            - processing_status: str - Final status (COMPLETED or FAILED)
            - error: str - Error message if failed (optional)

        Raises:
            RuntimeError: If ContextBridge not initialized or group not found

        Example:
            ```python
            async with ContextBridge() as bridge:
                result = await bridge.reprocess_group_with_context(
                    group_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                    context_model="anthropic:claude-3-5-sonnet-20241022"
                )
                print(f"Re-processed {result['chunks_created']} chunks")
            ```
        """
        self._check_initialized()
        logger.info(f"Starting re-processing for group {group_id}")

        try:
            # Create ReprocessingService
            reprocessing_service = ReprocessingService(
                group_repo=self._doc_manager.group_repo,
                chunk_repo=self._doc_manager.chunk_repo,
                page_repo=self._doc_manager.page_repo,
                chunking_service=self._doc_manager.chunking_service,
                embedding_service=self._doc_manager.embedding_service,
                context_generation_agent=self._doc_manager.context_agent,
                config=self.config,
            )

            # Perform re-processing
            result = await reprocessing_service.reprocess_group(
                group_id=group_id,
                context_model=context_model,
                delete_existing_chunks=True,
            )

            logger.info(f"Re-processed group {group_id}: {result['chunks_stored']} chunks stored")
            return {
                "success": True,
                "group_id": group_id,
                "chunks_created": result["chunks_stored"],
                "processing_status": "COMPLETED",
            }

        except Exception as e:
            logger.error(f"Failed to re-process group {group_id}: {e}")
            return {
                "success": False,
                "group_id": group_id,
                "chunks_created": 0,
                "processing_status": "FAILED",
                "error": str(e),
            }

    async def list_reprocessable_groups(
        self,
        document_id: int,
    ) -> List[Dict[str, Any]]:
        """
        List all groups in a document that can be re-processed.

        Reprocessable groups are those that:
        - Have processing_status = COMPLETED (already processed)
        - Have context_enabled = False (don't have context yet)

        This allows users to select which groups to re-process with context.

        Args:
            document_id: Document ID to list groups from

        Returns:
            List of group dictionaries, each containing:
            - id: UUID - Group ID
            - name: str - Group name (if set)
            - total_pages: int - Number of pages in group
            - total_chunks: int - Number of existing chunks
            - processing_status: str - Current status
            - created_at: str - ISO timestamp

        Raises:
            RuntimeError: If ContextBridge not initialized or document not found

        Example:
            ```python
            async with ContextBridge() as bridge:
                reprocessable = await bridge.list_reprocessable_groups(
                    document_id=42
                )
                for group in reprocessable:
                    print(f"{group['name']}: {group['total_chunks']} chunks")
            ```
        """
        self._check_initialized()
        logger.debug(f"Listing reprocessable groups for document {document_id}")

        try:
            # Create ReprocessingService
            reprocessing_service = ReprocessingService(
                group_repo=self._doc_manager.group_repo,
                chunk_repo=self._doc_manager.chunk_repo,
                page_repo=self._doc_manager.page_repo,
                chunking_service=self._doc_manager.chunking_service,
                embedding_service=self._doc_manager.embedding_service,
                context_generation_agent=self._doc_manager.context_agent,
                config=self.config,
            )

            # Get reprocessable groups
            groups = await reprocessing_service.list_reprocessable_groups(document_id=document_id)

            # Format for response
            return [
                {
                    "id": group.id,
                    "name": group.name,
                    "total_pages": group.total_pages,
                    "total_chunks": group.total_chunks,
                    "processing_status": group.processing_status,
                    "created_at": group.created_at.isoformat(),
                }
                for group in groups
            ]

        except Exception as e:
            logger.error(f"Failed to list reprocessable groups for document {document_id}: {e}")
            raise

    async def reprocess_multiple_groups_with_context(
        self,
        group_ids: List[UUID],
        context_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Re-process multiple groups with AI-generated context in batch.

        This method performs batch re-processing of multiple groups,
        handling errors for individual groups and continuing with others.

        The operation for each group:
        1. Validates the group exists
        2. Marks group as REPROCESSING
        3. Deletes existing chunks
        4. Chunks content and generates AI context
        5. Stores chunks with context
        6. Updates group status

        Args:
            group_ids: List of UUIDs of groups to re-process
            context_model: Optional context model (e.g., "anthropic:claude-3-5-sonnet-20241022")

        Returns:
            Dictionary containing:
            - success: bool - Whether batch operation succeeded overall
            - total_groups: int - Total groups to process
            - successful: int - Number successfully processed
            - failed: int - Number that failed
            - results: List[Dict] - Individual results for each group:
              - group_id: UUID
              - success: bool
              - chunks_created: int - Chunks created (if successful)
              - error: str - Error message (if failed)

        Example:
            ```python
            async with ContextBridge() as bridge:
                result = await bridge.reprocess_multiple_groups_with_context(
                    group_ids=[uuid1, uuid2, uuid3],
                    context_model="anthropic:claude-3-5-sonnet-20241022"
                )
                print(f"Processed {result['successful']}/{result['total_groups']} groups")
            ```
        """
        self._check_initialized()
        logger.info(f"Starting batch re-processing for {len(group_ids)} groups")

        results = {
            "success": True,
            "total_groups": len(group_ids),
            "successful": 0,
            "failed": 0,
            "results": [],
        }

        if not group_ids:
            logger.warning("No groups provided for batch re-processing")
            return results

        try:
            # Create ReprocessingService
            reprocessing_service = ReprocessingService(
                group_repo=self._doc_manager.group_repo,
                chunk_repo=self._doc_manager.chunk_repo,
                page_repo=self._doc_manager.page_repo,
                chunking_service=self._doc_manager.chunking_service,
                embedding_service=self._doc_manager.embedding_service,
                context_generation_agent=self._doc_manager.context_agent,
                config=self.config,
            )

            # Perform batch re-processing
            for group_id in group_ids:
                try:
                    result = await reprocessing_service.reprocess_group(
                        group_id=group_id,
                        context_model=context_model,
                        delete_existing_chunks=True,
                    )

                    results["results"].append(
                        {
                            "group_id": group_id,
                            "success": True,
                            "chunks_created": result.get("chunks_stored", 0),
                        }
                    )
                    results["successful"] += 1
                    logger.info(
                        f"Re-processed group {group_id}: {result.get('chunks_stored', 0)} chunks"
                    )

                except Exception as e:
                    logger.error(f"Failed to re-process group {group_id}: {e}")
                    results["results"].append(
                        {
                            "group_id": group_id,
                            "success": False,
                            "chunks_created": 0,
                            "error": str(e),
                        }
                    )
                    results["failed"] += 1

            if results["failed"] > 0:
                results["success"] = False
                logger.warning(f"Batch re-processing completed with {results['failed']} failures")
            else:
                logger.info(f"Successfully re-processed all {results['successful']} groups")

            return results

        except Exception as e:
            logger.error(f"Batch re-processing operation failed: {e}")
            return {
                "success": False,
                "total_groups": len(group_ids),
                "successful": 0,
                "failed": len(group_ids),
                "results": [],
                "error": str(e),
            }

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
