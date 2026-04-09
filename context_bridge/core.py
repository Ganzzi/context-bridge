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

from pydantic_ai import RunUsage

from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.usage_processor import UsageProcessor
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
from context_bridge.service.llm_model_provider import LLMExecutor
from context_bridge.service.url_service import UrlService
from context_bridge.service.reprocessing_service import ReprocessingService
from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.database.repositories.tag_repository import TagRepository
from context_bridge.database.repositories.group_repository import GroupRepository
from context_bridge.database.models.tag_models import Tag, TagCreate, TagUpdate, TagCategory
from context_bridge.database.models.group_models import (
    ProcessingStatus,
    GroupInfo,
    GroupStats,
    GroupCreationResult,
    ReprocessingResult,
)

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

    # -------------------------------------------------------------------------
    # Lifecycle Methods
    # -------------------------------------------------------------------------

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
        self._usage_processor: Optional[UsageProcessor] = None
        self._llm_executor: Optional[LLMExecutor] = None
        self._llm_backend_mode: bool = False
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
            usage_processor=self._usage_processor,
            llm_executor=self._llm_executor,
            llm_backend_mode=self._llm_backend_mode,
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

    def is_initialized(self) -> bool:
        """
        Check if ContextBridge is initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    def get_config(self) -> Config:
        """
        Get the current configuration.

        Returns:
            Config object
        """
        return self.config

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of all services.

        Returns:
            Dictionary with health status of each component
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

    def set_usage_processor(self, processor: Optional[UsageProcessor]) -> None:
        """
        Register a usage processor for tracking LLM token consumption.

        The processor receives RunUsage data whenever a Pydantic AI agent completes
        a run (e.g., during context generation). This enables applications to:

        - Track token consumption per agent or operation
        - Monitor costs based on LLM pricing
        - Implement usage quotas or limits
        - Collect analytics and metrics

        The processor is called after each agent run and should handle errors
        gracefully to avoid blocking agent operations.

        Args:
            processor: Async callable receiving RunUsage, or None to disable

        Example:
            ```python
            # Simple logging processor
            async def log_usage(usage: RunUsage) -> None:
                print(f"Used {usage.input_tokens + usage.output_tokens} tokens")

            bridge.set_usage_processor(log_usage)

            # With state via closure
            def create_counter():
                stats = {"total": 0}
                async def counter(usage: RunUsage) -> None:
                    stats["total"] += usage.input_tokens + usage.output_tokens
                return counter, stats

            counter, stats = create_counter()
            bridge.set_usage_processor(counter)
            ```

        Note:
            Can be called before or after initialize(). If called after initialize(),
            updates the DocManager's processor reference immediately.
        """
        self._usage_processor = processor
        # Update DocManager's reference if already initialized
        if self._doc_manager:
            self._doc_manager.usage_processor = processor
        if processor:
            logger.debug(f"Usage processor registered: {processor}")
        else:
            logger.debug("Usage processor cleared")

    def set_llm_executor(
        self,
        executor: Optional[LLMExecutor],
        *,
        backend_mode: bool = True,
    ) -> None:
        """
        Register or clear the LLM executor used for context generation calls.

        In backend mode, context generation must run through an injected executor
        so all requests are attributed and routed consistently.
        """
        self._llm_executor = executor
        self._llm_backend_mode = backend_mode
        if self._doc_manager:
            self._doc_manager.llm_executor = executor
            self._doc_manager.llm_backend_mode = backend_mode
        if executor:
            logger.info("LLM executor registered for ContextBridge")
        else:
            logger.info("LLM executor cleared for ContextBridge")

    # -------------------------------------------------------------------------
    # Document Operations
    # -------------------------------------------------------------------------

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
                        # Store tag names instead of IDs for token efficiency
                        doc.tags = [t.name for t in doc_tags]
                        tag_filtered_docs.append(doc)
                else:
                    # At least one requested tag must be present
                    if any(tag_id in doc_tag_ids for tag_id in tags):
                        # Store tag names instead of IDs for token efficiency
                        doc.tags = [t.name for t in doc_tags]
                        tag_filtered_docs.append(doc)

            return tag_filtered_docs
        else:
            # Populate tags for all documents with tag names
            for doc in docs:
                doc_tags = await self._tag_repository.get_document_tags(doc.id)
                # Use tag names instead of IDs for better readability and token efficiency
                doc.tags = [t.name for t in doc_tags]

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

    # -------------------------------------------------------------------------
    # Page Operations
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Group Management Operations
    # -------------------------------------------------------------------------

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
            List of GroupInfo objects with metadata:
            - id: UUID of the group (as string)
            - document_id: Associated document ID
            - name: Optional human-readable name
            - description: Optional description
            - context_enabled: Whether context generation is enabled
            - context_model: Optional model used for context generation
            - total_pages: Number of pages in group
            - total_chunks: Number of chunks in group
            - processing_status: Current status (pending, processing, completed, failed, reprocessing)
            - created_at: Creation timestamp (ISO format)
            - processed_at: Processing completion timestamp (ISO format or None)

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

        # Return dictionaries for backward compatibility with existing callers/tests.
        return [GroupInfo.from_group(group).model_dump() for group in all_groups]

    async def get_group_stats(self, group_id: UUID) -> GroupStats:
        """
        Get detailed statistics for a specific group.

        Provides comprehensive information about a group including its processing
        status, content size, chunk count, and context generation settings.

        Args:
            group_id: UUID of the group

        Returns:
            GroupStats object with group statistics:
            - group_id: UUID as string
            - document_id: Associated document ID
            - name: Optional group name
            - description: Optional description
            - status: Processing status (pending, processing, completed, failed, reprocessing)
            - context_enabled: Whether context generation is enabled
            - context_model: Optional model used for context generation
            - total_pages: Number of pages in group
            - total_chunks: Number of chunks in group
            - chunks_by_status: Dict mapping status names to counts (e.g., {"completed": 10, "pending": 5})
            - total_content_size: Total characters in all chunks
            - created_at: Creation timestamp (ISO format)
            - processed_at: Processing completion timestamp (ISO format or None)

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If group not found

        Example:
            ```python
            async with ContextBridge() as bridge:
                stats = await bridge.get_group_stats(UUID("550e8400-e29b-41d4-a716-446655440000"))
                print(f"Group {stats.name}: {stats.status}")
                print(f"Pages: {stats.total_pages}, Chunks: {stats.total_chunks}")
            ```
        """
        self._check_initialized()

        try:
            # Get group info from repository
            group = await self._group_repository.get_group_by_id(group_id)
            if not group:
                raise ValueError(f"Group {group_id} not found")

            # Get chunk statistics
            chunk_repo = ChunkRepository(self._db_manager)
            chunk_stats = await chunk_repo.get_group_chunk_statistics(group_id)

            # Calculate total content size
            total_content_size = await chunk_repo.get_group_content_size(group_id)

            return GroupStats(
                group_id=str(group.id),
                document_id=group.document_id,
                name=group.name,
                description=group.description,
                status=group.processing_status,
                context_enabled=group.context_enabled,
                context_model=group.context_model,
                total_pages=group.total_pages,
                total_chunks=group.total_chunks,
                chunks_by_status=chunk_stats.get("by_status", {}),
                total_content_size=total_content_size or 0,
                created_at=group.created_at.isoformat(),
                processed_at=group.processed_at.isoformat() if group.processed_at else None,
            )

        except Exception as e:
            logger.error(f"Failed to get group stats for {group_id}: {e}")
            raise

    # -------------------------------------------------------------------------
    # Chunking Operations
    # -------------------------------------------------------------------------

    async def create_group(
        self,
        document_id: int,
        page_ids: List[int],
        name: Optional[str] = None,
        chunk_size: Optional[int] = None,
        context_enabled: bool = False,
        context_model: Optional[str] = None,
    ) -> ChunkProcessingResult:
        """
        Create a group from selected pages and process them for chunking and embedding.

        This is the main workflow method that:
        1. Groups selected pages together
        2. Combines their content
        3. Splits content into chunks
        4. Generates embeddings for each chunk
        5. Optionally generates AI-powered context for each chunk
        6. Stores chunks in the database with group tracking

        This operation runs asynchronously in the background. Use list_groups() to
        monitor processing status.

        Args:
            document_id: Document ID
            page_ids: List of page IDs to process together in one group
            chunk_size: Optional chunk size override (characters). Default from config.
            context_enabled: Whether to generate AI-powered context summaries for each chunk
            context_model: LLM model for context generation (e.g., "anthropic:claude-3-5-sonnet-20241022")
                          Only used if context_enabled=True. Default from config.

        Returns:
            ChunkProcessingResult with processing details:
            - document_id: The document ID being processed
            - pages_processed: Number of pages selected for processing

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If page validation fails (e.g., pages from different documents)

        Example:
            ```python
            async with ContextBridge() as bridge:
                # Crawl documentation
                result = await bridge.crawl_documentation("mylib", "1.0.0", "https://docs.example.com")

                # List pages
                pages = await bridge.list_pages(result.document_id)
                page_ids = [p.id for p in pages[:10]]

                # Create group and process
                group_result = await bridge.create_group(
                    document_id=result.document_id,
                    page_ids=page_ids,
                    context_enabled=True,
                    context_model="anthropic:claude-3-5-sonnet-20241022"
                )

                # Monitor progress
                groups = await bridge.list_groups(result.document_id)
                for group in groups:
                    print(f"Group {group.id}: {group.processing_status}")
            ```
        """
        self._check_initialized()
        effective_context_model = context_model or self.config.context_agent_model

        # `name` is currently accepted for API compatibility and future use.
        _ = name

        return await self._doc_manager.process_chunking(
            document_id=document_id,
            page_ids=page_ids,
            chunk_size=chunk_size,
            context_enabled=context_enabled,
            context_model=effective_context_model,
            run_async=True,  # Always async in background
        )

    async def process_pages(
        self,
        document_id: int,
        page_ids: List[int],
        chunk_size: Optional[int] = None,
        context_enabled: bool = False,
        context_model: Optional[str] = None,
    ) -> ChunkProcessingResult:
        """Backward-compatible alias for `create_group()`.

        Historically, `process_pages` was the public API for triggering
        chunking. Keep this method so existing integrations and tests continue
        to work while routing through the newer group-oriented implementation.
        """
        return await self.create_group(
            document_id=document_id,
            page_ids=page_ids,
            chunk_size=chunk_size,
            context_enabled=context_enabled,
            context_model=context_model,
        )

    async def list_reprocessable_groups(
        self, document_id: Optional[int] = None, limit: int = 100, offset: int = 0
    ) -> List[GroupInfo]:
        """
        List groups that can be re-processed with context generation.

        Groups are eligible for re-processing if:
        - They have completed processing (processing_status='completed')
        - They don't have context enabled yet (context_enabled=False)

        Re-processing allows you to:
        - Add AI-generated context to previously processed groups
        - Update context generation settings (model, temperature)
        - Fix failed processing with new settings

        Args:
            document_id: Optional document ID to filter groups. If None, lists all reprocessable groups.
            limit: Maximum number of results to return
            offset: Pagination offset

        Returns:
            List of GroupInfo objects with metadata:
            - id: UUID of the group (as string)
            - document_id: Associated document ID
            - name: Optional group name
            - description: Optional description
            - total_pages: Number of pages in group
            - total_chunks: Number of chunks in group
            - processing_status: Always "completed" for reprocessable groups
            - context_enabled: Always False for reprocessable groups
            - created_at: Creation timestamp (ISO format)
            - processed_at: Processing completion timestamp (ISO format or None)

        Raises:
            RuntimeError: If ContextBridge not initialized

        Example:
            ```python
            async with ContextBridge() as bridge:
                # Find groups that need context generation
                reprocessable = await bridge.list_reprocessable_groups(document_id=123)

                for group in reprocessable:
                    print(f"Group {group.name}: {group.total_chunks} chunks, no context yet")

                    # Re-process with context
                    result = await bridge.reprocess_group(
                        group_id=UUID(group.id),
                        context_enabled=True,
                        context_model="anthropic:claude-3-5-sonnet-20241022"
                    )
                    print(f"Re-processing complete: {result.chunks_created} chunks")
            ```
        """
        self._check_initialized()

        # Get reprocessable groups from the group repository
        # Filter for: completed status + no context enabled yet
        reprocessable_groups = await self._group_repository.list_groups(
            document_id=document_id,
            processing_status=ProcessingStatus.COMPLETED,
            context_enabled=False,
            limit=limit,
            offset=offset,
        )

        # Convert to GroupInfo format
        return [GroupInfo.from_group(group) for group in reprocessable_groups]

    async def reprocess_group(
        self,
        group_id: UUID,
        context_enabled: bool = True,
        context_model: Optional[str] = None,
    ) -> ReprocessingResult:
        """
        Re-process an existing group with new context generation settings.

        Re-processing deletes all existing chunks for the group and regenerates them
        with the specified new settings. This is useful for:
        - Adding AI context generation to groups that were processed without it
        - Updating context models or generation settings
        - Fixing failed processing with new configuration

        WARNING: This deletes all existing chunks for the group. Make sure you have
        reviewed the current processing status before re-processing.

        Args:
            group_id: UUID of the group to re-process
            context_enabled: Whether to enable context generation (default: True)
            context_model: LLM model for context (e.g., "anthropic:claude-3-5-sonnet-20241022")
                          Default: uses config.context_agent_model

        Returns:
            ReprocessingResult with re-processing results:
            - status: "success", "failed", or "partial"
            - group_id: UUID as string
            - chunks_deleted: Number of chunks deleted (0 if not tracked)
            - chunks_created: Number of new chunks created
            - contexts_generated: Number of contexts generated (if enabled)
            - context_enabled: Whether context generation was enabled
            - context_model: Model used for context generation (or None)
            - errors: Number of errors during processing (0 if successful)

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If group not found or cannot be reprocessed

        Example:
            ```python
            async with ContextBridge() as bridge:
                # List groups needing context
                reprocessable = await bridge.list_reprocessable_groups(document_id=123)

                if reprocessable:
                    # Re-process the first group with context
                    result = await bridge.reprocess_group(
                        group_id=UUID(reprocessable[0].id),
                        context_enabled=True,
                        context_model="anthropic:claude-3-5-sonnet-20241022"
                    )

                    if result.status == 'success':
                        print(f"✅ Re-processed: {result.chunks_created} chunks with {result.contexts_generated} contexts")
                    else:
                        print(f"⚠️  Partial success: {result.errors} errors")
            ```
        """
        self._check_initialized()

        # Delegate to reprocessing service
        reprocessing_service = ReprocessingService(
            db_manager=self._db_manager,
            chunking_service=ChunkingService(default_chunk_size=self.config.chunk_size),
            embedding_service=EmbeddingService(self.config),
            config=self.config,
            llm_executor=self._llm_executor,
            llm_backend_mode=self._llm_backend_mode,
        )

        try:
            result_dict = await reprocessing_service.reprocess_group(
                group_id=group_id,
                context_enabled=context_enabled,
                context_model=context_model or self.config.context_agent_model,
                force_delete_chunks=True,
            )

            # Convert dict to ReprocessingResult model
            result = ReprocessingResult(
                status=result_dict.get("status", "unknown"),
                group_id=result_dict.get("group_id", str(group_id)),
                chunks_deleted=result_dict.get("chunks_deleted", 0),
                chunks_created=result_dict.get("chunks_created", 0),
                contexts_generated=result_dict.get("contexts_generated", 0),
                context_enabled=result_dict.get("context_enabled", context_enabled),
                context_model=result_dict.get("context_model"),
                errors=result_dict.get("errors", 0),
            )

            logger.info(f"✅ Re-processed group {group_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to reprocess group {group_id}: {e}")
            raise

    # -------------------------------------------------------------------------
    # Search Operations
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Tag Operations
    # -------------------------------------------------------------------------

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

    async def add_tag_to_document(self, document_id: int, tag_id: int) -> bool:
        """
        Add a tag to a document.

        Args:
            document_id: Document ID
            tag_id: Tag ID to add

        Returns:
            True if tag was added, False if relationship already exists

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._tag_repository.add_tag_to_document(document_id, tag_id)

    async def add_tags_to_document(self, document_id: int, tag_ids: List[int]) -> int:
        """
        Add multiple tags to a document.

        Args:
            document_id: Document ID
            tag_ids: List of tag IDs to add

        Returns:
            Number of tags successfully added

        Raises:
            RuntimeError: If ContextBridge not initialized
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
            True if tag was removed, False if it wasn't assigned

        Raises:
            RuntimeError: If ContextBridge not initialized
        """
        self._check_initialized()
        return await self._tag_repository.remove_tag_from_document(document_id, tag_id)

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

    async def create_tag(
        self,
        name: str,
        category: TagCategory,
        description: Optional[str] = None,
    ) -> Tag:
        """
        Create a new custom tag.

        Args:
            name: Tag name (must be unique)
            category: TagCategory enum value
            description: Optional tag description

        Returns:
            Created Tag object

        Raises:
            RuntimeError: If ContextBridge not initialized
            ValueError: If tag name already exists
        """
        self._check_initialized()
        tag_create = TagCreate(name=name, category=category, description=description)
        return await self._tag_repository.create_tag(tag_create)
