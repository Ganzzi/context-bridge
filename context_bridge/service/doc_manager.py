"""Document Manager Service for context_bridge.

This module provides high-level orchestration for document operations including
crawling, storage, chunking, and management of documentation sources.
"""

from typing import List, Optional
from datetime import datetime
import logging
import hashlib
import asyncio

from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler

from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.document_repository import DocumentRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.service.crawling_service import CrawlingService
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService

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
    ):
        """Initialize the document manager.

        Args:
            db_manager: PostgreSQL connection manager
            crawling_service: Web crawling service
            chunking_service: Markdown chunking service
            embedding_service: Text embedding service
            config: Application configuration
        """
        self.db_manager = db_manager
        self.crawling_service = crawling_service
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.config = config

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
    ) -> CrawlAndStoreResult:
        """
        Crawl documentation and store pages.

        Workflow:
        1. Create or get document
        2. Crawl source URL with optional depth override
        3. Store pages (skip duplicates)
        4. Return detailed results

        Args:
            name: Document name
            version: Version string
            source_url: Source URL to crawl
            description: Optional document description
            max_depth: Optional crawl depth override

        Returns:
            CrawlAndStoreResult with operation details
        """
        logger.info(f"Starting crawl_and_store for {name} v{version} from {source_url}")

        # Get or create document
        doc = await self.doc_repo.get_by_name_version(name, version)
        if not doc:
            doc_id = await self.doc_repo.create(
                name=name, version=version, source_url=source_url, description=description
            )
        else:
            doc_id = doc.id

        # Crawl with optional depth override
        async with AsyncWebCrawler(verbose=True) as crawler:
            crawl_result = await self.crawling_service.crawl_webpage(
                crawler, source_url, depth=max_depth
            )

        # Store pages
        stored = 0
        duplicates = 0
        errors = 0

        for page in crawl_result.results:
            try:
                content_hash = hashlib.sha256(page.markdown.encode()).hexdigest()
                existing = await self.page_repo.get_by_url(page.url)

                if existing:
                    duplicates += 1
                    continue

                await self.page_repo.create(
                    document_id=doc_id,
                    url=page.url,
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
            pages_crawled=len(crawl_result.results),
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

    async def process_chunking(
        self,
        document_id: int,
        page_ids: List[int],
        chunk_size: Optional[int] = None,
        batch_enabled: bool = True,
    ) -> ChunkProcessingResult:
        """
        Process pages for chunking and embedding asynchronously.

        Workflow:
        1. Validate pages (same document, status='pending', size constraints)
        2. Update page status to 'processing'
        3. Start async background task for chunking process
        4. Return immediately with processing started result

        Args:
            document_id: Document ID
            page_ids: List of page IDs to process
            chunk_size: Optional chunk size override
            batch_enabled: Whether to use batch processing for embeddings

        Returns:
            ChunkProcessingResult indicating processing has started (actual results logged later)
        """
        logger.info(f"Starting process_chunking for doc {document_id}, {len(page_ids)} pages")

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

        # Update page status to 'processing'
        await self.page_repo.update_status_bulk(page_ids, "processing")

        # Start background processing task
        asyncio.create_task(
            self._process_chunking_background(document_id, page_ids, chunk_size, batch_enabled)
        )

        # Return immediately with processing started result
        return ChunkProcessingResult(
            document_id=document_id,
            pages_processed=len(page_ids),
        )

    async def _process_chunking_background(
        self,
        document_id: int,
        page_ids: List[int],
        chunk_size: int,
        batch_enabled: bool,
    ) -> None:
        """
        Background task for chunking and embedding processing.

        Args:
            document_id: Document ID
            page_ids: List of page IDs to process
            chunk_size: Chunk size to use
            batch_enabled: Whether to use batch processing
        """
        try:
            # Get combined content
            combined_content = await self.page_repo.get_combined_content(page_ids)

            # Chunk
            chunks = self.chunking_service.smart_chunk_markdown(
                combined_content, chunk_size=chunk_size
            )

            logger.info(f"Created {len(chunks)} chunks from combined content")

            # Generate embeddings and store chunks
            if batch_enabled:
                # Use batch processing for both embeddings and chunks
                try:
                    embeddings = await self.embedding_service.get_embeddings_batch(chunks)
                except Exception as e:
                    logger.error(f"Error generating embeddings in batch: {e}")
                    raise

                # Create chunk data for batch insertion
                chunk_data = []
                for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_data.append(
                        {
                            "document_id": document_id,
                            "chunk_index": i,
                            "content": chunk_text,
                            "embedding": embedding,
                        }
                    )

                try:
                    chunk_ids = await self.chunk_repo.create_batch(chunk_data)
                    chunks_created = len(chunk_ids)
                    errors = 0
                except Exception as e:
                    logger.error(f"Error storing chunks in batch: {e}")
                    errors = 1
                    chunks_created = 0
            else:
                # Process one by one: generate embedding and create chunk for each chunk
                chunks_created = 0
                errors = 0
                for i, chunk_text in enumerate(chunks):
                    try:
                        # Generate embedding for this chunk
                        embedding = await self.embedding_service.get_embedding(chunk_text)

                        # Create chunk immediately
                        await self.chunk_repo.create(
                            document_id=document_id,
                            chunk_index=i,
                            content=chunk_text,
                            embedding=embedding,
                        )
                        chunks_created += 1
                    except Exception as e:
                        logger.error(f"Error processing chunk {i}: {e}")
                        errors += 1

            # Update page status to 'chunked'
            await self.page_repo.update_status_bulk(page_ids, "chunked")

            logger.info(
                f"Chunking background task complete: {chunks_created} chunks created, "
                f"{errors} errors for document {document_id}"
            )

        except Exception as e:
            logger.error(f"Background chunking task failed for document {document_id}: {e}")
            # Update page status to 'pending' on failure
            try:
                await self.page_repo.update_status_bulk(page_ids, "pending")
            except Exception as status_error:
                logger.error(f"Failed to reset page status on error: {status_error}")
