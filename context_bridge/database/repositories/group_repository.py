from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from context_bridge.database.postgres_manager import PostgreSQLManager


logger = logging.getLogger(__name__)


class PageGroup(BaseModel):
    """Page group model."""

    id: int
    document_id: int
    name: Optional[str]
    total_size: int
    page_count: int
    created_at: datetime
    status: str  # eligible, processed


class GroupWithPages(BaseModel):
    """Group with its member pages."""

    group: PageGroup
    page_ids: List[int]


class GroupRepository:
    """Repository for page group operations."""

    def __init__(self, db_manager: PostgreSQLManager):
        """
        Initialize group repository.

        Args:
            db_manager: PostgreSQL connection manager
        """
        self.db_manager = db_manager
        logger.debug("GroupRepository initialized")

    async def create_group(
        self, document_id: int, page_ids: List[int], name: Optional[str] = None
    ) -> int:
        """
        Create a group from pages.
        Validates:
        - All pages belong to the same document
        - All pages have status 'pending'
        - Updates pages to status 'grouped'
        Returns group ID.
        """
        if not page_ids:
            raise ValueError("Cannot create group with empty page list")

        async with self.db_manager.connection() as conn:
            # Validate pages
            page_validation_query = """
                SELECT id, document_id, status, content_length
                FROM pages
                WHERE id = ANY($1)
            """
            page_results = await conn.fetch(page_validation_query, [page_ids])
            page_rows = page_results.result()  # Get the list of rows

            if len(page_rows) != len(page_ids):
                found_ids = {row["id"] for row in page_rows}
                missing_ids = set(page_ids) - found_ids
                raise ValueError(f"Pages not found: {missing_ids}")

            # Check all pages belong to the same document and have pending status
            total_size = 0
            for row in page_rows:
                if row["document_id"] != document_id:
                    raise ValueError(f"Page {row['id']} belongs to different document")
                if row["status"] != "pending":
                    raise ValueError(
                        f"Page {row['id']} has status '{row['status']}', expected 'pending'"
                    )
                total_size += row["content_length"]

            page_count = len(page_rows)

            # Create group first to get ID
            group_query = """
                INSERT INTO page_groups (document_id, name, total_size, page_count, status)
                VALUES ($1, $2, $3, $4, 'eligible')
                RETURNING id
            """
            group_result = await conn.execute(
                group_query, [document_id, name, total_size, page_count]
            )
            group_rows = group_result.result()
            if not group_rows:
                raise RuntimeError("Failed to create group")
            group_id = group_rows[0]["id"]

            # Update pages and create memberships in transaction
            operations = [
                # Update pages to grouped status
                (
                    """
                    UPDATE pages
                    SET status = 'grouped'
                    WHERE id = ANY($1)
                """,
                    [page_ids],
                ),
            ]

            # Add member insertions
            for page_id in page_ids:
                operations.append(
                    (
                        """
                        INSERT INTO page_group_members (group_id, page_id)
                        VALUES ($1, $2)
                    """,
                        [group_id, page_id],
                    )
                )

            # Execute transaction for page updates and memberships
            await self.db_manager.execute_transaction(operations)

            logger.info(
                f"Created group {group_id} with {page_count} pages, total size {total_size}"
            )
            return group_id

    async def get_by_id(self, group_id: int) -> Optional[PageGroup]:
        """Get group by ID."""
        try:
            query = """
                SELECT id, document_id, name, total_size, page_count, created_at, status
                FROM page_groups
                WHERE id = $1
            """
            async with self.db_manager.connection() as conn:
                result = await conn.fetch(query, [group_id])
                rows = result.result()
                if rows:
                    row = rows[0]
                    return PageGroup(
                        id=row["id"],
                        document_id=row["document_id"],
                        name=row["name"],
                        total_size=row["total_size"],
                        page_count=row["page_count"],
                        created_at=row["created_at"],
                        status=row["status"],
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get group {group_id}: {e}")
            raise

    async def get_with_pages(self, group_id: int) -> Optional[GroupWithPages]:
        """Get group with its member page IDs."""
        try:
            # Get group
            group = await self.get_by_id(group_id)
            if not group:
                return None

            # Get page IDs
            query = """
                SELECT page_id
                FROM page_group_members
                WHERE group_id = $1
                ORDER BY page_id
            """
            async with self.db_manager.connection() as conn:
                result = await conn.fetch(query, [group_id])
                rows = result.result()
                page_ids = [row["page_id"] for row in rows]

            return GroupWithPages(group=group, page_ids=page_ids)
        except Exception as e:
            logger.error(f"Failed to get group with pages {group_id}: {e}")
            raise

    async def list_by_document(
        self, document_id: int, status: Optional[str] = None, offset: int = 0, limit: int = 100
    ) -> List[PageGroup]:
        """List groups for a document."""
        try:
            query = """
                SELECT id, document_id, name, total_size, page_count, created_at, status
                FROM page_groups
                WHERE document_id = $1
            """
            params = [document_id]

            if status:
                query += " AND status = $2"
                params.append(status)

            query += " ORDER BY created_at DESC OFFSET $%d LIMIT $%d" % (
                len(params) + 1,
                len(params) + 2,
            )
            params.extend([offset, limit])

            async with self.db_manager.connection() as conn:
                result = await conn.fetch(query, params)
                rows = result.result()
                return [
                    PageGroup(
                        id=row["id"],
                        document_id=row["document_id"],
                        name=row["name"],
                        total_size=row["total_size"],
                        page_count=row["page_count"],
                        created_at=row["created_at"],
                        status=row["status"],
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to list groups for document {document_id}: {e}")
            raise

    async def get_eligible_groups(
        self, document_id: int, min_size: Optional[int] = None, max_size: Optional[int] = None
    ) -> List[PageGroup]:
        """
        Get groups eligible for chunking.
        Filters by status='eligible' and optional size constraints.
        """
        try:
            query = """
                SELECT id, document_id, name, total_size, page_count, created_at, status
                FROM page_groups
                WHERE document_id = $1 AND status = 'eligible'
            """
            params = [document_id]

            if min_size is not None:
                query += " AND total_size >= $%d" % (len(params) + 1)
                params.append(min_size)

            if max_size is not None:
                query += " AND total_size <= $%d" % (len(params) + 1)
                params.append(max_size)

            query += " ORDER BY total_size DESC"

            async with self.db_manager.connection() as conn:
                result = await conn.fetch(query, params)
                rows = result.result()
                return [
                    PageGroup(
                        id=row["id"],
                        document_id=row["document_id"],
                        name=row["name"],
                        total_size=row["total_size"],
                        page_count=row["page_count"],
                        created_at=row["created_at"],
                        status=row["status"],
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get eligible groups for document {document_id}: {e}")
            raise

    async def get_group_content(self, group_id: int) -> str:
        """
        Get combined content of all pages in group.
        Pages are ordered by ID and joined with '\\n\\n---\\n\\n'.
        """
        try:
            query = """
                SELECT p.content
                FROM pages p
                JOIN page_group_members pgm ON p.id = pgm.page_id
                WHERE pgm.group_id = $1
                ORDER BY p.id
            """
            async with self.db_manager.connection() as conn:
                result = await conn.fetch(query, [group_id])
                rows = result.result()
                if not rows:
                    raise ValueError(f"No pages found for group {group_id}")

                contents = [row["content"] for row in rows]
                return "\n\n---\n\n".join(contents)
        except Exception as e:
            logger.error(f"Failed to get content for group {group_id}: {e}")
            raise

    async def update_status(self, group_id: int, status: str) -> bool:
        """Update group status."""
        try:
            query = """
                UPDATE page_groups
                SET status = $1
                WHERE id = $2
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [status, group_id])
                # PSQLPy UPDATE returns empty list, assume success
                logger.info(f"Updated group {group_id} status to {status}")
                return True
        except Exception as e:
            logger.error(f"Failed to update group {group_id} status: {e}")
            raise

    async def ungroup(self, group_id: int) -> bool:
        """
        Dissolve a group:
        - Set member pages back to 'pending'
        - Delete group
        Returns True if successful.
        """
        try:
            # First get the page IDs for this group
            page_query = """
                SELECT page_id FROM page_group_members WHERE group_id = $1
            """
            async with self.db_manager.connection() as conn:
                page_result = await conn.fetch(page_query, [group_id])
                page_rows = page_result.result()
                if not page_rows:
                    raise ValueError(f"Group {group_id} not found or has no members")

                page_ids = [row["page_id"] for row in page_rows]

            # Update pages and delete group in transaction
            operations = [
                # Set pages back to pending
                (
                    """
                    UPDATE pages
                    SET status = 'pending'
                    WHERE id = ANY($1)
                """,
                    [page_ids],
                ),
                # Delete group (cascade will delete members)
                (
                    """
                    DELETE FROM page_groups WHERE id = $1
                """,
                    [group_id],
                ),
            ]

            await self.db_manager.execute_transaction(operations)

            logger.info(f"Ungrouped group {group_id}, reset {len(page_ids)} pages to pending")
            return True
        except Exception as e:
            logger.error(f"Failed to ungroup {group_id}: {e}")
            raise

    async def delete(self, group_id: int) -> bool:
        """Delete group (cascades to members via FK)."""
        try:
            query = """
                DELETE FROM page_groups WHERE id = $1
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [group_id])
                # PSQLPy DELETE returns empty list, assume success
                logger.info(f"Deleted group {group_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete group {group_id}: {e}")
            raise

    async def validate_group_constraints(
        self, page_ids: List[int], min_size: Optional[int] = None, max_size: Optional[int] = None
    ) -> Tuple[bool, Optional[str], int]:
        """
        Validate if pages can form a valid group.
        Returns: (is_valid, error_message, total_size)
        """
        try:
            if not page_ids:
                return False, "Cannot create group with empty page list", 0

            query = """
                SELECT id, document_id, status, content_length
                FROM pages
                WHERE id = ANY($1)
            """
            async with self.db_manager.connection() as conn:
                result = await conn.fetch(query, [page_ids])
                rows = result.result()

            if len(rows) != len(page_ids):
                found_ids = {row["id"] for row in rows}
                missing_ids = set(page_ids) - found_ids
                return False, f"Pages not found: {missing_ids}", 0

            # Check if all pages belong to the same document
            document_ids = {row["document_id"] for row in rows}
            if len(document_ids) > 1:
                return False, "Pages belong to different documents", 0

            # Check if all pages have pending status
            invalid_status_pages = [row["id"] for row in rows if row["status"] != "pending"]
            if invalid_status_pages:
                return False, f"Pages have invalid status (not pending): {invalid_status_pages}", 0

            # Calculate total size
            total_size = sum(row["content_length"] for row in rows)

            # Check size constraints
            if min_size is not None and total_size < min_size:
                return False, f"Total size {total_size} is below minimum {min_size}", total_size

            if max_size is not None and total_size > max_size:
                return False, f"Total size {total_size} exceeds maximum {max_size}", total_size

            return True, None, total_size
        except Exception as e:
            logger.error(f"Failed to validate group constraints: {e}")
            return False, f"Validation error: {str(e)}", 0
