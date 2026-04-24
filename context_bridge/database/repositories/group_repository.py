"""
GroupRepository for managing groups in the database.

Provides async CRUD operations and statistics for groups, which represent
collections of pages processed together for chunking and context generation.
"""

import logging
from uuid import UUID
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
from contextlib import asynccontextmanager

from psqlpy import ConnectionPool, Connection

from context_bridge.database.models.group_models import (
    Group,
    GroupCreate,
    GroupUpdate,
    ProcessingStatus,
    GroupStatistics,
)

logger = logging.getLogger(__name__)


class GroupRepository:
    """
    Repository for managing groups in the database.

    Provides async methods for CRUD operations, statistics, and queries
    related to groups of pages that are processed together.
    """

    def __init__(self, connection_pool: ConnectionPool):
        """
        Initialize the GroupRepository.

        Args:
            connection_pool: PSQLPy connection pool for database access
        """
        self.pool = connection_pool

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[Connection, None]:
        """
        Get a connection from the pool (context manager).

        Handles both PostgreSQLManager (returns @asynccontextmanager) and
        raw psqlpy ConnectionPool (returns a coroutine) transparently.

        Usage:
            async with repository.connection() as conn:
                result = await conn.fetch("SELECT * FROM table")

        Yields:
            Connection from the pool
        """
        result = self.pool.connection()
        if hasattr(result, '__aenter__'):
            # PostgreSQLManager returns an async context manager
            async with result as conn:
                yield conn
        else:
            # Raw ConnectionPool.connection() returns a coroutine
            conn = await result
            try:
                yield conn
            finally:
                pass  # Connection auto-returns to pool

    # CRUD Operations

    async def create_group(self, group_data: GroupCreate) -> Group:
        """
        Create a new group in the database.

        Args:
            group_data: GroupCreate model with group information

        Returns:
            Created Group model

        Raises:
            ValueError: If document_id doesn't exist
            Exception: If database operation fails
        """
        logger.debug(f"Creating group for document {group_data.document_id}")

        async with self.connection() as conn:
            # Verify document exists
            doc_check = await conn.fetch(
                "SELECT id FROM documents WHERE id = $1", [group_data.document_id]
            )

            if not doc_check.result():
                raise ValueError(f"Document with ID {group_data.document_id} not found")

            # Create group
            query = """
                INSERT INTO groups
                (document_id, name, description, context_enabled, context_model, processing_status, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, document_id, name, description, context_enabled, context_model,
                          combined_content_length, total_pages, total_chunks, created_at,
                          processed_at, processing_status, metadata
            """

            result = await conn.fetch(
                query,
                [
                    group_data.document_id,
                    group_data.name,
                    group_data.description,
                    group_data.context_enabled,
                    group_data.context_model,
                    ProcessingStatus.PENDING.value,
                    group_data.metadata or {},
                ],
            )

            rows = result.result()
            if not rows:
                raise Exception("Failed to create group")

            row = rows[0]
            logger.info(f"Created group {row['id']} for document {group_data.document_id}")

            return Group(
                id=row["id"],
                document_id=row["document_id"],
                name=row["name"],
                description=row["description"],
                context_enabled=row["context_enabled"],
                context_model=row["context_model"],
                combined_content_length=row["combined_content_length"],
                total_pages=row["total_pages"],
                total_chunks=row["total_chunks"],
                created_at=row["created_at"],
                processed_at=row["processed_at"],
                processing_status=ProcessingStatus(row["processing_status"]),
                metadata=row["metadata"] or {},
            )

    async def get_group_by_id(self, group_id: UUID) -> Optional[Group]:
        """
        Get a group by its ID.

        Args:
            group_id: UUID of the group

        Returns:
            Group model if found, None otherwise
        """
        logger.debug(f"Getting group {group_id}")

        async with self.connection() as conn:
            result = await conn.fetch(
                """
                SELECT id, document_id, name, description, context_enabled, context_model,
                       combined_content_length, total_pages, total_chunks, created_at,
                       processed_at, processing_status, metadata
                FROM groups
                WHERE id = $1
                """,
                [group_id],
            )

            rows = result.result()
            if not rows:
                return None

            row = rows[0]
            return Group(
                id=row["id"],
                document_id=row["document_id"],
                name=row["name"],
                description=row["description"],
                context_enabled=row["context_enabled"],
                context_model=row["context_model"],
                combined_content_length=row["combined_content_length"],
                total_pages=row["total_pages"],
                total_chunks=row["total_chunks"],
                created_at=row["created_at"],
                processed_at=row["processed_at"],
                processing_status=ProcessingStatus(row["processing_status"]),
                metadata=row["metadata"] or {},
            )

    async def list_groups(
        self,
        document_id: Optional[int] = None,
        context_enabled: Optional[bool] = None,
        processing_status: Optional[ProcessingStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Group]:
        """
        List groups with optional filtering.

        Args:
            document_id: Filter by document ID (optional)
            context_enabled: Filter by context_enabled flag (optional)
            processing_status: Filter by processing status (optional)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of Group models
        """
        logger.debug(
            f"Listing groups: document_id={document_id}, context_enabled={context_enabled}, "
            f"status={processing_status}, limit={limit}, offset={offset}"
        )

        query = (
            "SELECT id, document_id, name, description, context_enabled, context_model, "
            "combined_content_length, total_pages, total_chunks, created_at, "
            "processed_at, processing_status, metadata FROM groups WHERE 1=1"
        )

        params: List[Any] = []
        param_index = 1

        if document_id is not None:
            query += f" AND document_id = ${param_index}"
            params.append(document_id)
            param_index += 1

        if context_enabled is not None:
            query += f" AND context_enabled = ${param_index}"
            params.append(context_enabled)
            param_index += 1

        if processing_status is not None:
            query += f" AND processing_status = ${param_index}"
            params.append(processing_status.value)
            param_index += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_index} OFFSET ${param_index + 1}"
        params.extend([limit, offset])

        async with self.connection() as conn:
            results = await conn.fetch(query, params)

            groups = []
            for row in results.result():
                groups.append(
                    Group(
                        id=row["id"],
                        document_id=row["document_id"],
                        name=row["name"],
                        description=row["description"],
                        context_enabled=row["context_enabled"],
                        context_model=row["context_model"],
                        combined_content_length=row["combined_content_length"],
                        total_pages=row["total_pages"],
                        total_chunks=row["total_chunks"],
                        created_at=row["created_at"],
                        processed_at=row["processed_at"],
                        processing_status=ProcessingStatus(row["processing_status"]),
                        metadata=row["metadata"] or {},
                    )
                )

            return groups

    async def update_group(self, group_id: UUID, updates: GroupUpdate) -> Optional[Group]:
        """
        Update a group with the provided changes.

        Args:
            group_id: UUID of the group to update
            updates: GroupUpdate model with fields to update

        Returns:
            Updated Group model, or None if group not found
        """
        logger.debug(f"Updating group {group_id}")

        # Build dynamic update query
        update_fields = []
        params: List[Any] = []
        param_index = 1

        if updates.name is not None:
            update_fields.append(f"name = ${param_index}")
            params.append(updates.name)
            param_index += 1

        if updates.description is not None:
            update_fields.append(f"description = ${param_index}")
            params.append(updates.description)
            param_index += 1

        if updates.context_enabled is not None:
            update_fields.append(f"context_enabled = ${param_index}")
            params.append(updates.context_enabled)
            param_index += 1

        if updates.context_model is not None:
            update_fields.append(f"context_model = ${param_index}")
            params.append(updates.context_model)
            param_index += 1

        if updates.processing_status is not None:
            update_fields.append(f"processing_status = ${param_index}")
            params.append(updates.processing_status.value)
            param_index += 1

        if updates.processed_at is not None:
            update_fields.append(f"processed_at = ${param_index}")
            params.append(updates.processed_at)
            param_index += 1

        if updates.total_pages is not None:
            update_fields.append(f"total_pages = ${param_index}")
            params.append(updates.total_pages)
            param_index += 1

        if updates.total_chunks is not None:
            update_fields.append(f"total_chunks = ${param_index}")
            params.append(updates.total_chunks)
            param_index += 1

        if updates.combined_content_length is not None:
            update_fields.append(f"combined_content_length = ${param_index}")
            params.append(updates.combined_content_length)
            param_index += 1

        if updates.metadata is not None:
            update_fields.append(f"metadata = ${param_index}")
            params.append(updates.metadata)
            param_index += 1

        if not update_fields:
            # No updates to apply
            return await self.get_group_by_id(group_id)

        params.append(group_id)

        query = f"""
            UPDATE groups
            SET {', '.join(update_fields)}
            WHERE id = ${param_index}
            RETURNING id, document_id, name, description, context_enabled, context_model,
                      combined_content_length, total_pages, total_chunks, created_at,
                      processed_at, processing_status, metadata
        """

        async with self.connection() as conn:
            result = await conn.fetch(query, params)

            rows = result.result()
            if not rows:
                return None

            row = rows[0]
            logger.info(f"Updated group {group_id}")

            return Group(
                id=row["id"],
                document_id=row["document_id"],
                name=row["name"],
                description=row["description"],
                context_enabled=row["context_enabled"],
                context_model=row["context_model"],
                combined_content_length=row["combined_content_length"],
                total_pages=row["total_pages"],
                total_chunks=row["total_chunks"],
                created_at=row["created_at"],
                processed_at=row["processed_at"],
                processing_status=ProcessingStatus(row["processing_status"]),
                metadata=row["metadata"] or {},
            )

    async def delete_group(self, group_id: UUID) -> bool:
        """
        Delete a group by ID.

        Also deletes all associated chunks (via CASCADE foreign key).
        Pages will have their group_id set to NULL (via ON DELETE SET NULL).

        Args:
            group_id: UUID of the group to delete

        Returns:
            True if group was deleted, False if not found
        """
        logger.debug(f"Deleting group {group_id}")

        async with self.connection() as conn:
            result = await conn.fetch("DELETE FROM groups WHERE id = $1 RETURNING id", [group_id])

            rows = result.result()
            deleted = len(rows) > 0

            if deleted:
                logger.info(f"Deleted group {group_id}")

            return deleted

    # Statistics and Analytics

    async def get_group_statistics(self, group_id: UUID) -> Optional[GroupStatistics]:
        """
        Get detailed statistics for a group.

        Args:
            group_id: UUID of the group

        Returns:
            GroupStatistics model with aggregate data, or None if group not found
        """
        logger.debug(f"Getting statistics for group {group_id}")

        async with self.connection() as conn:
            # Get group info
            group_result = await conn.fetch("SELECT id FROM groups WHERE id = $1", [group_id])

            if not group_result.result():
                return None

            # Get page statistics
            page_result = await conn.fetch(
                """
                SELECT COUNT(*) as total_pages, 
                       COALESCE(SUM(length(content)), 0) as total_content_bytes
                FROM pages
                WHERE group_id = $1
                """,
                [group_id],
            )

            page_rows = page_result.result()
            page_row = page_rows[0] if page_rows else {}
            total_pages = page_row.get("total_pages", 0) or 0
            total_content_bytes = page_row.get("total_content_bytes", 0) or 0

            # Get chunk statistics
            chunk_result = await conn.fetch(
                """
                SELECT COUNT(*) as total_chunks,
                       COALESCE(AVG(length(content)), 0) as avg_chunk_size
                FROM chunks
                WHERE group_id = $1
                """,
                [group_id],
            )

            chunk_rows = chunk_result.result()
            chunk_row = chunk_rows[0] if chunk_rows else {}
            total_chunks = chunk_row.get("total_chunks", 0) or 0
            avg_chunk_size = float(chunk_row.get("avg_chunk_size", 0) or 0)

            # Get page IDs
            page_ids_result = await conn.fetch(
                "SELECT id FROM pages WHERE group_id = $1 ORDER BY id", [group_id]
            )

            page_ids = [row["id"] for row in page_ids_result.result()]

            # Calculate average page size
            avg_page_size = total_content_bytes / total_pages if total_pages > 0 else 0.0

            return GroupStatistics(
                group_id=group_id,
                total_pages=total_pages,
                total_chunks=total_chunks,
                total_content_bytes=total_content_bytes,
                avg_page_size=avg_page_size,
                avg_chunk_size=avg_chunk_size,
                page_ids=page_ids,
            )

    async def count_groups_by_document(self, document_id: int) -> int:
        """
        Count total number of groups for a document.

        Args:
            document_id: ID of the document

        Returns:
            Number of groups for the document
        """
        logger.debug(f"Counting groups for document {document_id}")

        async with self.connection() as conn:
            result = await conn.fetch(
                "SELECT COUNT(*) as count FROM groups WHERE document_id = $1", [document_id]
            )

            rows = result.result()
            return rows[0]["count"] if rows else 0

    async def get_non_context_groups(
        self,
        document_id: Optional[int] = None,
    ) -> List[Group]:
        """
        Get all groups that haven't had context generation applied yet.

        Useful for finding groups eligible for re-processing with context generation.

        Args:
            document_id: Optional filter by document ID

        Returns:
            List of Group models with context_enabled=False
        """
        logger.debug(f"Getting non-context groups for document {document_id}")

        query = """
            SELECT id, document_id, name, description, context_enabled, context_model,
                   combined_content_length, total_pages, total_chunks, created_at,
                   processed_at, processing_status, metadata
            FROM groups
            WHERE context_enabled = FALSE
        """

        params: List[Any] = []

        if document_id is not None:
            query += " AND document_id = $1"
            params.append(document_id)

        query += " ORDER BY created_at DESC"

        async with self.connection() as conn:
            results = await conn.fetch(query, params)

            groups = []
            for row in results.result():
                groups.append(
                    Group(
                        id=row["id"],
                        document_id=row["document_id"],
                        name=row["name"],
                        description=row["description"],
                        context_enabled=row["context_enabled"],
                        context_model=row["context_model"],
                        combined_content_length=row["combined_content_length"],
                        total_pages=row["total_pages"],
                        total_chunks=row["total_chunks"],
                        created_at=row["created_at"],
                        processed_at=row["processed_at"],
                        processing_status=ProcessingStatus(row["processing_status"]),
                        metadata=row["metadata"] or {},
                    )
                )

            return groups
