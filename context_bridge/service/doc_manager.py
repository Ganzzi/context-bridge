"""Document Manager Service for context_bridge.

This module provides high-level orchestration for document operations including
crawling, storage, chunking, and management of documentation sources.
"""

from typing import List, Optional
from datetime import datetime
import logging
import hashlib
import asyncio
import traceback
from uuid import uuid4, UUID

from pydantic import BaseModel
from crawl4ai import CrawlerRunConfig

from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.service.crawling_service import CrawlingService
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService
from context_bridge.agents.context_generator import ContextGenerator
from context_bridge.service.llm_model_provider import LLMExecutor

logger = logging.getLogger(__name__)


class CrawlAndStoreResult(BaseModel):
    """Result of crawl and store operation."""

    document_id: int
    document_name: str
    document_version: str
    pages_crawled: int
    pages_stored: int
    duplicates_skipped: int
    errors: int


class ChunkProcessingResult(BaseModel):
    """Result of chunking operation initiation.

    Since chunking runs asynchronously, this only indicates that processing
    has been queued. Actual results are logged when processing completes.
    """

    document_id: int
    pages_processed: int


class PageInfo(BaseModel):
    """Simplified page information for listing."""

    id: int
    url: str
    content_length: int
    status: str
    crawled_at: datetime


class DocManager:
    """High-level document management service."""

    def __init__(
        self,
        db_manager: PostgreSQLManager,
        crawling_service: CrawlingService,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        config: Config,
        usage_processor=None,
        llm_executor: Optional[LLMExecutor] = None,
        llm_backend_mode: bool = False,
    ):
        """Initialize the document manager.

        Args:
            db_manager: PostgreSQL connection manager
            crawling_service: Web crawling service
            chunking_service: Markdown chunking service
            embedding_service: Text embedding service
            config: Application configuration
            usage_processor: Optional processor for tracking LLM token usage
        """
        self.db_manager = db_manager
        self.crawling_service = crawling_service
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.config = config
        self.usage_processor = usage_processor
        self.llm_executor = llm_executor
        self.llm_backend_mode = llm_backend_mode

        # Initialize repositories
        self.doc_repo = DocumentRepository(db_manager)
        self.page_repo = PageRepository(db_manager)
        self.chunk_repo = ChunkRepository(db_manager)

        logger.info("DocManager initialized")

    async def crawl_and_store(
        self,
        name: str,
        version: str,
        source_url: str,
        description: Optional[str] = None,
        max_depth: Optional[int] = None,
        additional_urls: Optional[List[str]] = None,
    ) -> CrawlAndStoreResult:
        """
        Crawl documentation and store pages.

        Workflow:
        1. Create or get document
        2. Crawl source URL and additional URLs with optional depth override
        3. Store pages (skip duplicates)
        4. Return detailed results

        Args:
            name: Document name
            version: Version string
            source_url: Primary source URL to crawl
            description: Optional document description
            max_depth: Optional crawl depth override
            additional_urls: Optional list of additional URLs to crawl

        Returns:
            CrawlAndStoreResult with operation details
        """
        logger.info(f"Starting crawl_and_store for {name} v{version} from {source_url}")
        if additional_urls:
            logger.info(f"Additional URLs: {additional_urls}")

        # Get or create document
        doc = await self.doc_repo.get_by_name_version(name, version)
        if not doc:
            doc_id = await self.doc_repo.create(
                name=name, version=version, source_url=source_url, description=description
            )
        else:
            doc_id = doc.id

        # Prepare list of URLs to crawl
        urls_to_crawl = [source_url]
        if additional_urls:
            urls_to_crawl.extend(additional_urls)

        # Determine if we should follow internal links:
        # - Follow links when max_depth > 1 (regardless of additional URLs)
        # - Don't follow when max_depth = 1 (single page only)
        should_follow_links = True
        if max_depth is not None and max_depth == 1:
            # Explicitly set to depth 1 - don't follow links
            should_follow_links = False
        elif max_depth is None and self.config.crawl_max_depth == 1:
            # Default depth is 1 - don't follow links
            should_follow_links = False
        # Note: Fragment duplication is prevented by URL normalization in crawling_service

        # Crawl all URLs. Let CrawlingService decide how to provision crawler
        # resources (this keeps unit tests free of Playwright/browser deps).
        all_crawl_results = []
        for url in urls_to_crawl:
            logger.info(
                f"Crawling URL: {url} (follow_links={should_follow_links}, depth={max_depth or self.config.crawl_max_depth})"
            )
            crawl_result = await self.crawling_service.crawl_webpage(
                None, url, depth=max_depth, follow_links=should_follow_links
            )
            all_crawl_results.append(crawl_result)

        # Combine all results
        combined_results = []
        total_attempted = 0
        total_successful = 0
        total_failed = 0

        for result in all_crawl_results:
            combined_results.extend(result.results)
            total_attempted += result.total_urls_attempted
            total_successful += result.successful_count
            total_failed += result.failed_count

        # Store pages
        stored = 0
        duplicates = 0
        errors = 0

        for page in combined_results:
            try:
                content_hash = hashlib.sha256(page.markdown.encode()).hexdigest()
                normalized_url = page.url.split("#")[0]
                existing = await self.page_repo.get_by_url(normalized_url)

                if existing:
                    duplicates += 1
                    continue

                await self.page_repo.create(
                    document_id=doc_id,
                    url=normalized_url,
                    content=page.markdown,
                    content_hash=content_hash,
                )
                stored += 1

            except Exception as e:
                logger.error(f"Error storing page {page.url}: {e}")
                errors += 1

        logger.info(
            f"Crawl complete: {stored} stored, " f"{duplicates} duplicates, {errors} errors"
        )

        return CrawlAndStoreResult(
            document_id=doc_id,
            document_name=name,
            document_version=version,
            pages_crawled=len(combined_results),
            pages_stored=stored,
            duplicates_skipped=duplicates,
            errors=errors,
        )

    async def list_pages(
        self, document_id: int, status: Optional[str] = None, offset: int = 0, limit: int = 100
    ) -> List[PageInfo]:
        """
        List pages for a document with pagination.

        Args:
            document_id: Document ID
            status: Optional status filter ('pending', 'processing', 'chunked', 'deleted')
            offset: Pagination offset
            limit: Maximum results

        Returns:
            List of PageInfo objects
        """
        pages = await self.page_repo.list_by_document(
            document_id, status=status, offset=offset, limit=limit
        )

        return [
            PageInfo(
                id=p.id,
                url=p.url,
                content_length=p.content_length,
                status=p.status,
                crawled_at=p.crawled_at,
            )
            for p in pages
        ]

    async def delete_page(self, page_id: int) -> bool:
        """
        Delete a page (soft delete - marks as 'deleted').

        Args:
            page_id: Page ID to delete

        Returns:
            True if successful
        """
        return await self.page_repo.delete(page_id)

    async def delete_document(self, document_id: int) -> bool:
        """
        Delete a document and all related data (pages, chunks).

        Args:
            document_id: Document ID to delete

        Returns:
            True if successful
        """
        return await self.doc_repo.delete(document_id)

    async def process_chunking(
        self,
        document_id: int,
        page_ids: List[int],
        chunk_size: Optional[int] = None,
        context_enabled: bool = False,
        context_model: Optional[str] = None,
        batch_enabled: bool = True,
        run_async: bool = True,
    ) -> ChunkProcessingResult:
        """
        Process pages for chunking and embedding.

        Workflow:
        1. Validate pages (same document, status='pending', size constraints)
        2. Generate a group UUID for this chunking operation
        3. Update pages with group_id and status to 'processing'
        4. Either start async background task OR run synchronously
        5. Return result (immediate for sync, queued for async)

        Args:
            document_id: Document ID
            page_ids: List of page IDs to process
            chunk_size: Optional chunk size override
            context_enabled: Reserved for compatibility; context generation is
                currently applied via group processing/reprocessing flows.
            context_model: Reserved for compatibility with core API.
            batch_enabled: Whether to use batch processing for embeddings
            run_async: If True, run in background task. If False, run synchronously.

        Returns:
            ChunkProcessingResult with processing details
        """
        logger.info(
            f"Starting process_chunking for doc {document_id}, {len(page_ids)} pages "
            f"(context_enabled={context_enabled}, context_model={context_model})"
        )

        chunk_size = chunk_size or self.config.chunk_size
        min_size = self.config.min_combined_content_size
        max_size = self.config.max_combined_content_size

        # Validate pages
        is_valid, error_msg, total_size = await self.page_repo.validate_pages_for_chunking(
            page_ids, min_size=min_size, max_size=max_size
        )

        if not is_valid:
            raise ValueError(f"Page validation failed: {error_msg}")

        logger.info(f"Validated {len(page_ids)} pages, total size: {total_size} chars")

        # Generate a group UUID for this chunking operation
        group_id = uuid4()
        logger.info(f"Generated group_id: {group_id} for {len(page_ids)} pages")

        # Update pages with group_id and status to 'processing'
        await self.page_repo.update_group_id_bulk(page_ids, group_id)
        await self.page_repo.update_status_bulk(page_ids, "processing")

        if run_async:
            # Start background processing task
            logger.info(f"Starting async background chunking task for {len(page_ids)} pages")
            asyncio.create_task(
                self._process_chunking_background(
                    document_id, page_ids, group_id, chunk_size, batch_enabled
                )
            )

            # Return immediately with processing started result
            return ChunkProcessingResult(
                document_id=document_id,
                pages_processed=len(page_ids),
            )
        else:
            # Run synchronously
            logger.info(f"Starting synchronous chunking for {len(page_ids)} pages")
            await self._process_chunking_background(
                document_id, page_ids, group_id, chunk_size, batch_enabled
            )

            # Return result with actual processing details
            return ChunkProcessingResult(
                document_id=document_id,
                pages_processed=len(page_ids),
            )

    async def _process_chunking_background(
        self,
        document_id: int,
        page_ids: List[int],
        group_id: UUID,
        chunk_size: int,
        batch_enabled: bool,
    ) -> None:
        """
        Background task for chunking and embedding processing.

        Args:
            document_id: Document ID
            page_ids: List of page IDs to process
            group_id: UUID for this chunking group
            chunk_size: Chunk size to use
            batch_enabled: Whether to use batch processing
        """
        logger.info(
            f"🚀 Starting background chunking task for document {document_id}, {len(page_ids)} pages, group_id={group_id}, batch={batch_enabled}"
        )

        try:
            # Get the current max chunk_index for this document to continue from
            max_chunk_index = await self.chunk_repo.get_max_chunk_index(document_id)
            start_index = max_chunk_index + 1
            logger.info(
                f"📊 Current max chunk_index: {max_chunk_index}, starting from: {start_index}"
            )

            # Get combined content
            logger.debug(f"📖 Getting combined content for {len(page_ids)} pages")
            combined_content = await self.page_repo.get_combined_content(page_ids)
            content_length = len(combined_content)
            logger.info(f"📖 Retrieved combined content: {content_length} characters")

            # Chunk
            logger.debug(f"✂️  Chunking content with size {chunk_size}")
            chunks = self.chunking_service.smart_chunk_markdown(
                combined_content, chunk_size=chunk_size
            )
            logger.info(f"✂️  Created {len(chunks)} chunks from combined content")

            # Generate embeddings and store chunks
            if batch_enabled:
                logger.debug("🔄 Starting batch processing for embeddings and chunks")
                # Use batch processing for both embeddings and chunks
                try:
                    logger.debug(f"🧮 Generating embeddings for {len(chunks)} chunks")
                    embeddings = await self.embedding_service.get_embeddings_batch(chunks)
                    logger.info(f"🧮 Generated {len(embeddings)} embeddings in batch")
                except Exception as e:
                    logger.error(f"❌ Error generating embeddings in batch: {e}")
                    raise

                # Create chunk data for batch insertion
                chunk_data = []
                for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_data.append(
                        {
                            "document_id": document_id,
                            "chunk_index": start_index + i,
                            "content": chunk_text,
                            "embedding": embedding,
                            "group_id": group_id,
                        }
                    )

                try:
                    logger.debug(f"💾 Storing {len(chunk_data)} chunks in batch")
                    chunk_ids = await self.chunk_repo.create_batch(chunk_data)
                    chunks_created = len(chunk_ids)
                    errors = 0
                    logger.info(
                        f"💾 Successfully stored {chunks_created} chunks in batch (indices {start_index} to {start_index + chunks_created - 1})"
                    )
                except Exception as e:
                    logger.error(f"❌ Error storing chunks in batch: {e}")
                    errors = 1
                    chunks_created = 0
            else:
                logger.debug("🔄 Starting individual processing for embeddings and chunks")
                # Process one by one: generate embedding and create chunk for each chunk
                chunks_created = 0
                errors = 0
                for i, chunk_text in enumerate(chunks):
                    try:
                        # Generate embedding for this chunk
                        embedding = await self.embedding_service.get_embedding(chunk_text)

                        # Create chunk immediately with proper index
                        await self.chunk_repo.create(
                            document_id=document_id,
                            chunk_index=start_index + i,
                            content=chunk_text,
                            embedding=embedding,
                            group_id=group_id,
                        )
                        chunks_created += 1

                        if (i + 1) % 10 == 0:  # Log progress every 10 chunks
                            logger.debug(f"📦 Processed {i + 1}/{len(chunks)} chunks")

                    except Exception as e:
                        logger.error(f"❌ Error processing chunk {start_index + i}: {e}")
                        errors += 1

                logger.info(
                    f"📦 Completed individual processing: {chunks_created} chunks created (indices {start_index} to {start_index + chunks_created - 1}), {errors} errors"
                )

            # Update page status to 'chunked'
            logger.debug(f"🔄 Updating status for {len(page_ids)} pages to 'chunked'")
            await self.page_repo.update_status_bulk(page_ids, "chunked")
            logger.info(f"✅ Updated {len(page_ids)} pages to 'chunked' status")

            logger.info(
                f"🎉 Chunking background task complete: {chunks_created} chunks created, "
                f"{errors} errors for document {document_id}, group_id {group_id}"
            )

        except Exception as e:
            logger.error(
                f"💥 Background chunking task failed for document {document_id}, group_id {group_id}: {e}"
            )
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Update page status to 'pending' on failure
            try:
                logger.debug(
                    f"🔄 Resetting status for {len(page_ids)} pages to 'pending' due to error"
                )
                await self.page_repo.update_status_bulk(page_ids, "pending")
                logger.info(f"✅ Reset {len(page_ids)} pages to 'pending' status after error")
            except Exception as status_error:
                logger.error(f"❌ Failed to reset page status on error: {status_error}")

    async def process_group(
        self,
        group_id: UUID,
        context_enabled: bool = False,
        context_model: Optional[str] = None,
    ) -> dict:
        """
        Process a specific group through chunking and optional context generation.

        This method retrieves all pages in a group, chunks them, generates embeddings,
        and optionally creates AI-generated context for each chunk.

        Args:
            group_id: UUID of the group to process
            context_enabled: Whether to generate context for chunks
            context_model: The model to use for context generation (e.g., "anthropic:claude-3-5-sonnet")

        Returns:
            Dictionary with processing results:
            - status: "success" or "failed"
            - total_pages: Number of pages in group
            - pages_processed: Number of pages successfully processed
            - chunks_created: Number of chunks created
            - errors: Number of processing errors

        Raises:
            ValueError: If group not found or invalid
            Exception: If processing fails
        """
        logger.info(f"🔄 Processing group {group_id}")

        try:
            # Retrieve all pages in the group
            pages = await self.page_repo.get_pages_for_group(group_id)
            if not pages:
                logger.warning(f"⚠️  No pages found for group {group_id}")
                return {
                    "status": "success",
                    "total_pages": 0,
                    "pages_processed": 0,
                    "chunks_created": 0,
                    "errors": 0,
                }

            logger.info(f"📋 Found {len(pages)} pages in group {group_id}")

            # Combine all page content for context generation (if needed)
            combined_content = ""
            if context_enabled:
                combined_content = "\n\n".join([page.content for page in pages])
                logger.debug(
                    f"📖 Combined {len(pages)} pages ({len(combined_content)} chars) for context generation"
                )

            # Initialize context agent if needed
            context_agent = None
            if context_enabled and context_model:
                context_agent = ContextGenerator(
                    self.config,
                    usage_processor=getattr(self, "usage_processor", None),
                    executor=getattr(self, "llm_executor", None),
                    backend_mode=getattr(self, "llm_backend_mode", False),
                )
                logger.info(f"🤖 Initialized context agent with model {context_model}")

            # Process each page
            total_chunks = 0
            errors = 0
            all_chunk_texts = []  # For batch context generation

            for page in pages:
                try:
                    # Extract chunks from page content
                    chunks = self.chunking_service.smart_chunk_markdown(page.content)
                    logger.debug(f"📦 Generated {len(chunks)} chunks from page {page.id}")

                    if not chunks:
                        logger.warning(f"⚠️  No chunks generated from page {page.id}")
                        continue

                    # Collect chunk texts for batch context generation
                    if context_enabled:
                        all_chunk_texts.extend(chunks)

                    # Generate embeddings
                    embeddings = await self.embedding_service.get_embeddings_batch(chunks)
                    logger.debug(f"🧮 Generated embeddings for {len(chunks)} chunks")

                    # Create chunk records
                    chunk_data = []
                    for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                        chunk_entry = {
                            "document_id": page.document_id,
                            "chunk_index": i,
                            "content": chunk_text,
                            "embedding": embedding,
                            "group_id": group_id,
                        }
                        chunk_data.append(chunk_entry)

                    # Batch create chunks
                    chunk_ids = await self.chunk_repo.create_batch(chunk_data)
                    total_chunks += len(chunk_ids)
                    logger.info(f"✅ Created {len(chunk_ids)} chunks for page {page.id}")

                except Exception as e:
                    logger.error(f"❌ Error processing page {page.id}: {e}")
                    errors += 1

            # Generate contexts for all chunks if enabled
            if context_enabled and context_agent and all_chunk_texts:
                try:
                    logger.info(f"🤖 Generating contexts for {len(all_chunk_texts)} chunks...")
                    contexts = await context_agent.generate_contexts_batch(
                        all_chunk_texts, combined_content
                    )

                    # Update chunks with contexts
                    updated = 0
                    for i, context in enumerate(contexts):
                        if context:  # Only update if context was generated
                            try:
                                await self.chunk_repo.prepend_context_to_chunk(i, context)
                                updated += 1
                            except Exception as e:
                                logger.warning(f"⚠️  Failed to update chunk {i} with context: {e}")

                    logger.info(
                        f"✅ Updated {updated}/{len(contexts)} chunks with generated context"
                    )

                except Exception as e:
                    logger.error(f"❌ Failed to generate contexts: {e}")
                    # Continue processing even if context generation fails

            logger.info(
                f"🎉 Group {group_id} processing complete: {total_chunks} chunks created, {errors} errors"
            )

            return {
                "status": "success" if errors == 0 else "partial",
                "total_pages": len(pages),
                "pages_processed": len(pages) - errors,
                "chunks_created": total_chunks,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"💥 Failed to process group {group_id}: {e}")
            raise

    async def get_document_groups(self, document_id: int) -> List[dict]:
        """
        Retrieve all groups associated with a document.

        Args:
            document_id: The document ID

        Returns:
            List of group information dictionaries, each containing:
            - id: Group UUID
            - name: Optional group name
            - context_enabled: Whether context generation is enabled
            - total_pages: Number of pages in group
            - total_chunks: Number of chunks in group
            - processing_status: Current processing status

        Raises:
            Exception: If database query fails
        """
        logger.debug(f"📋 Retrieving groups for document {document_id}")

        try:
            # Query groups table for this document
            # This would normally use a repository method, but for now we'll use a direct query
            query = """
                SELECT 
                    id,
                    name,
                    context_enabled,
                    total_pages,
                    total_chunks,
                    processing_status
                FROM groups
                WHERE document_id = $1
                ORDER BY created_at DESC
            """

            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [document_id])
                rows = result.result()

            groups = [
                {
                    "id": row["id"],
                    "name": row.get("name"),
                    "context_enabled": row["context_enabled"],
                    "total_pages": row["total_pages"],
                    "total_chunks": row["total_chunks"],
                    "processing_status": row["processing_status"],
                }
                for row in rows
            ]

            logger.info(f"📋 Found {len(groups)} groups for document {document_id}")
            return groups

        except Exception as e:
            logger.error(f"❌ Failed to retrieve groups for document {document_id}: {e}")
            raise

    async def reprocess_group(
        self,
        group_id: UUID,
        force_rechunk: bool = False,
        context_enabled: bool = False,
        context_model: Optional[str] = None,
    ) -> dict:
        """
        Re-process an existing group with optional new settings.

        This method deletes existing chunks for the group and re-processes all pages
        with the new settings. Useful for updating context settings or fixing errors.

        Args:
            group_id: UUID of the group to reprocess
            force_rechunk: If True, delete existing chunks before re-chunking
            context_enabled: Enable context generation for new chunks
            context_model: Model to use for context generation

        Returns:
            Dictionary with reprocessing results:
            - status: "success" or "failed"
            - chunks_deleted: Number of chunks deleted
            - chunks_created: Number of new chunks created
            - errors: Number of processing errors

        Raises:
            ValueError: If group not found
            Exception: If reprocessing fails
        """
        logger.info(f"🔄 Reprocessing group {group_id} (force_rechunk={force_rechunk})")

        try:
            # Delete existing chunks if requested
            chunks_deleted = 0
            if force_rechunk:
                try:
                    logger.debug(f"🗑️  Deleting existing chunks for group {group_id}")
                    chunks_deleted = await self.chunk_repo.delete_by_group(group_id)
                    logger.info(f"✅ Deleted {chunks_deleted} chunks for group {group_id}")
                except Exception as e:
                    logger.error(f"❌ Error deleting chunks for group {group_id}: {e}")
                    raise

            # Re-process the group with new settings
            result = await self.process_group(
                group_id=group_id,
                context_enabled=context_enabled,
                context_model=context_model,
            )

            result["chunks_deleted"] = chunks_deleted

            logger.info(
                f"🎉 Group {group_id} reprocessing complete: {chunks_deleted} deleted, "
                f"{result['chunks_created']} created"
            )

            return result

        except Exception as e:
            logger.error(f"💥 Failed to reprocess group {group_id}: {e}")
            raise
