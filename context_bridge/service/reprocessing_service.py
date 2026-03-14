"""
Service for re-processing groups with context generation.

Enables existing document groups to be re-processed with updated settings,
including optional AI-generated context for improved search relevance.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from uuid import UUID

from context_bridge.config import Config
from context_bridge.database.models.group_models import Group, ProcessingStatus
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.database.repositories.group_repository import GroupRepository
from context_bridge.database.repositories.page_repository import PageRepository
from context_bridge.service.chunking_service import ChunkingService
from context_bridge.service.embedding import EmbeddingService
from context_bridge.service.llm_model_provider import LLMExecutor

logger = logging.getLogger(__name__)


class ReprocessingService:
    """Service for re-processing groups with optional context generation."""

    def __init__(
        self,
        db_manager: PostgreSQLManager,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        config: Config,
        llm_executor: Optional[LLMExecutor] = None,
        llm_backend_mode: bool = False,
    ):
        """
        Initialize the reprocessing service.

        Args:
            db_manager: PostgreSQL connection manager
            chunking_service: Service for chunking content
            embedding_service: Service for generating embeddings
            config: Application configuration
        """
        self.db_manager = db_manager
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.config = config
        self.llm_executor = llm_executor
        self.llm_backend_mode = llm_backend_mode

        # Initialize repositories
        self.group_repo = GroupRepository(db_manager)
        self.chunk_repo = ChunkRepository(db_manager)
        self.page_repo = PageRepository(db_manager)

        # Import here to avoid circular imports
        try:
            from context_bridge.agents.context_generator import ContextGenerator

            self.context_agent = ContextGenerator(
                config,
                executor=self.llm_executor,
                backend_mode=self.llm_backend_mode,
            )
        except ImportError:
            self.context_agent = None
            logger.warning("ContextGenerator not available, context generation disabled")

    async def reprocess_group(
        self,
        group_id: UUID,
        context_enabled: bool = False,
        context_model: Optional[str] = None,
        force_delete_chunks: bool = False,
    ) -> Dict:
        """
        Re-process a group with optional context generation.

        Args:
            group_id: UUID of the group to reprocess
            context_enabled: Whether to generate context for chunks
            context_model: Model to use for context generation
            force_delete_chunks: If True, delete existing chunks before reprocessing

        Returns:
            Dictionary with reprocessing results and statistics

        Raises:
            ValueError: If group not found or is already context-enabled
            RuntimeError: If reprocessing fails
        """
        logger.info(f"Starting reprocessing for group {group_id}")

        try:
            # Step 1: Validate group exists and can be reprocessed
            group = await self.group_repo.get_group_by_id(group_id)
            if not group:
                raise ValueError(f"Group {group_id} not found")

            logger.debug(f"Retrieved group: {group.name or group.id}")

            # Step 2: Mark group as reprocessing
            await self.group_repo.update_group(
                group_id=group_id,
                updates={"processing_status": ProcessingStatus.REPROCESSING},
            )

            # Step 3: Delete existing chunks if requested
            if force_delete_chunks:
                logger.info(f"Deleting existing chunks for group {group_id}")
                deleted_count = await self.chunk_repo.delete_by_group(group_id)
                logger.debug(f"Deleted {deleted_count} chunks")

            # Step 4: Retrieve pages for the group
            pages = await self.page_repo.get_pages_for_group(group_id)
            if not pages:
                raise ValueError(f"No pages found for group {group_id}")

            logger.info(f"Retrieved {len(pages)} pages for group")

            # Step 5: Combine page content
            combined_content = await self._combine_page_content(pages)
            logger.debug(f"Combined content length: {len(combined_content)} characters")

            # Step 6: Chunk the content
            chunks = await self.chunking_service.chunk_markdown(
                combined_content,
                chunk_size=self.config.chunk_size,
            )
            logger.info(f"Created {len(chunks)} chunks")

            # Step 7: Generate contexts if enabled
            contexts = []
            if context_enabled and self.context_agent:
                logger.info(f"Generating contexts for {len(chunks)} chunks")
                contexts = await self.context_agent.generate_contexts_batch(
                    chunks=[c.content for c in chunks],
                    document_content=combined_content,
                )
                logger.debug(f"Generated {len([c for c in contexts if c])} non-empty contexts")

                # Prepend context to chunk content
                for i, chunk in enumerate(chunks):
                    if i < len(contexts) and contexts[i]:
                        chunk.content = f"{contexts[i]}\n\n{chunk.content}"

            # Step 8: Generate embeddings
            chunk_contents = [c.content for c in chunks]
            embeddings = await self.embedding_service.embed_batch(chunk_contents)
            logger.info(f"Generated embeddings for {len(embeddings)} chunks")

            # Step 9: Store chunks with metadata
            stored_count = await self._store_reprocessed_chunks(
                group_id=group_id,
                chunks=chunks,
                embeddings=embeddings,
                contexts=contexts,
            )
            logger.info(f"Stored {stored_count} chunks")

            # Step 10: Update group status
            await self.group_repo.update_group(
                group_id=group_id,
                updates={
                    "processing_status": ProcessingStatus.COMPLETED,
                    "context_enabled": context_enabled,
                    "context_model": context_model or group.context_model,
                    "total_chunks": stored_count,
                    "processed_at": None,  # Will be set by trigger
                },
            )

            result = {
                "status": "success",
                "group_id": str(group_id),
                "chunks_created": stored_count,
                "contexts_generated": len([c for c in contexts if c]) if context_enabled else 0,
                "context_enabled": context_enabled,
                "context_model": context_model or group.context_model,
            }

            logger.info(f"Successfully reprocessed group {group_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to reprocess group {group_id}: {e}", exc_info=True)

            # Mark group as failed
            try:
                await self.group_repo.update_group(
                    group_id=group_id,
                    updates={"processing_status": ProcessingStatus.FAILED},
                )
            except Exception as update_error:
                logger.error(f"Failed to update group status to FAILED: {update_error}")

            raise RuntimeError(f"Group reprocessing failed: {e}") from e

    async def reprocess_multiple_groups(
        self,
        group_ids: List[UUID],
        context_enabled: bool = False,
        context_model: Optional[str] = None,
        continue_on_error: bool = True,
    ) -> Dict:
        """
        Re-process multiple groups in parallel.

        Args:
            group_ids: List of group UUIDs to reprocess
            context_enabled: Whether to generate context for chunks
            context_model: Model to use for context generation
            continue_on_error: If True, continue processing other groups on error

        Returns:
            Dictionary with overall results and per-group statistics

        Raises:
            RuntimeError: If all groups fail and continue_on_error is False
        """
        logger.info(f"Starting batch reprocessing for {len(group_ids)} groups")

        results = {
            "status": "success",
            "total_groups": len(group_ids),
            "successful": 0,
            "failed": 0,
            "group_results": [],
        }

        # Process groups concurrently
        tasks = [
            self.reprocess_group(
                group_id=group_id,
                context_enabled=context_enabled,
                context_model=context_model,
            )
            for group_id in group_ids
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Process responses
        for i, response in enumerate(responses):
            group_id = group_ids[i]

            if isinstance(response, Exception):
                logger.warning(f"Error reprocessing group {group_id}: {response}")
                results["group_results"].append(
                    {
                        "group_id": str(group_id),
                        "status": "error",
                        "error": str(response),
                    }
                )
                results["failed"] += 1

                if not continue_on_error:
                    results["status"] = "failed"
                    raise RuntimeError(f"Batch reprocessing failed at group {group_id}")
            else:
                logger.info(f"Successfully reprocessed group {group_id}")
                results["group_results"].append(response)
                results["successful"] += 1

        logger.info(
            f"Batch reprocessing complete: {results['successful']} successful, "
            f"{results['failed']} failed"
        )

        return results

    async def list_reprocessable_groups(
        self,
        document_id: Optional[int] = None,
    ) -> List[Dict]:
        """
        List groups that can be reprocessed.

        Groups are reprocessable if they either:
        1. Don't have context enabled yet
        2. Are completed but not currently processing

        Args:
            document_id: Optional document ID to filter groups

        Returns:
            List of reprocessable groups with metadata
        """
        logger.info(f"Listing reprocessable groups for document {document_id or 'all'}")

        try:
            # Get all groups for the document(s)
            groups = await self.group_repo.list_groups(
                document_id=document_id,
                processing_status=ProcessingStatus.COMPLETED,
            )

            # Filter for reprocessable groups (not already context-enabled)
            reprocessable = [
                {
                    "id": str(g.id),
                    "document_id": g.document_id,
                    "name": g.name,
                    "description": g.description,
                    "context_enabled": g.context_enabled,
                    "total_pages": g.total_pages,
                    "total_chunks": g.total_chunks,
                    "processing_status": g.processing_status.value,
                    "created_at": g.created_at.isoformat(),
                    "processed_at": g.processed_at.isoformat() if g.processed_at else None,
                }
                for g in groups
                if not g.context_enabled  # Only non-context-enabled groups
            ]

            logger.info(f"Found {len(reprocessable)} reprocessable groups")
            return reprocessable

        except Exception as e:
            logger.error(f"Failed to list reprocessable groups: {e}", exc_info=True)
            raise RuntimeError(f"Failed to list reprocessable groups: {e}") from e

    # Helper methods

    async def _combine_page_content(self, pages: List) -> str:
        """
        Combine content from multiple pages.

        Args:
            pages: List of Page objects

        Returns:
            Combined markdown content
        """
        contents = [f"# {page.title}\n\n{page.content}" for page in pages if page.content]
        return "\n\n---\n\n".join(contents)

    async def _store_reprocessed_chunks(
        self,
        group_id: UUID,
        chunks: List,
        embeddings: List,
        contexts: Optional[List[str]] = None,
    ) -> int:
        """
        Store reprocessed chunks with proper metadata.

        Args:
            group_id: Group UUID
            chunks: List of chunk objects
            embeddings: List of embedding vectors
            contexts: Optional list of context strings

        Returns:
            Number of chunks stored
        """
        stored_count = 0

        for i, chunk in enumerate(chunks):
            try:
                # Get embedding for this chunk
                if i < len(embeddings):
                    embedding = embeddings[i]
                else:
                    logger.warning(f"Missing embedding for chunk {i}, skipping")
                    continue

                # Store chunk via repository
                await self.chunk_repo.create_chunk(
                    document_id=None,  # Will be fetched from group
                    group_id=group_id,
                    content=chunk.content,
                    embedding=embedding,
                    source_page_ids=[],  # Will be populated from pages
                )
                stored_count += 1

            except Exception as e:
                logger.error(f"Failed to store chunk {i}: {e}")
                continue

        return stored_count
