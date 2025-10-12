from typing import Optional, List, Set
from datetime import datetime
import logging
from pydantic import BaseModel, Field

from context_bridge.database.postgres_manager import PostgreSQLManager


logger = logging.getLogger(__name__)


class Page(BaseModel):
    """
    Page model representing a crawled webpage or document page.

    Attributes:
        id: Unique page identifier
        document_id: ID of the parent document
        url: URL where the page was crawled from
        content: Raw content (usually markdown)
        content_hash: SHA256 hash of the content for deduplication
        content_length: Length of content (computed column)
        crawled_at: Timestamp when page was crawled
        status: Page status ('pending', 'grouped', 'deleted')
        metadata: Additional metadata as JSON object
    """

    id: int
    document_id: int
    url: str
    content: str
    content_hash: str
    content_length: int
    crawled_at: datetime
    status: str = Field(default="pending")
    metadata: dict = Field(default_factory=dict)


class PageRepository:
    """
    Repository for page CRUD operations using PSQLPy.

    This repository handles all database operations for crawled pages,
    including creation, retrieval, status updates, and deduplication.
    Follows PSQLPy best practices with proper error handling and
    connection management.
    """

    def __init__(self, db_manager: PostgreSQLManager):
        """
        Initialize page repository.

        Args:
            db_manager: PostgreSQL connection manager
        """
        self.db_manager = db_manager
        logger.debug("PageRepository initialized")

    async def create(
        self,
        document_id: int,
        url: str,
        content: str,
        content_hash: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        Create a new page or return existing ID if URL already exists.

        Args:
            document_id: Parent document ID
            url: Page URL (must be unique)
            content: Page content
            content_hash: Content hash for deduplication
            metadata: Optional metadata dict

        Returns:
            ID of created page or existing page with same URL

        Raises:
            RuntimeError: If page creation fails
            Exception: Database errors
        """
        try:
            # First check if URL already exists
            existing_page = await self.get_by_url(url)
            if existing_page:
                logger.info(f"Page with URL '{url}' already exists (ID {existing_page.id})")
                return existing_page.id

            # Create new page
            query = """
                INSERT INTO pages (document_id, url, content, content_hash, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(
                    query, [document_id, url, content, content_hash, metadata or {}]
                )
                rows = result.result()
                if rows:
                    page_id = rows[0]["id"]  # PSQLPy returns dicts
                    logger.info(f"Created page '{url}' with ID {page_id}")
                    return page_id
                else:
                    raise RuntimeError(f"Failed to create page '{url}'")
        except Exception as e:
            logger.error(f"Failed to create page '{url}': {e}")
            raise

    async def get_by_id(self, page_id: int) -> Optional[Page]:
        """
        Get page by ID.

        Args:
            page_id: Page ID

        Returns:
            Page if found, None otherwise

        Raises:
            Exception: Database errors
        """
        try:
            query = """
                SELECT id, document_id, url, content, content_hash, content_length, crawled_at, status, metadata
                FROM pages
                WHERE id = $1
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [page_id])
                rows = result.result()
                if rows:
                    page = self._row_to_page(rows[0])
                    logger.debug(f"Retrieved page ID {page_id}: '{page.url}'")
                    return page
                logger.debug(f"Page ID {page_id} not found")
                return None
        except Exception as e:
            logger.error(f"Failed to get page by ID {page_id}: {e}")
            raise

    async def get_by_url(self, url: str) -> Optional[Page]:
        """
        Get page by URL.

        Args:
            url: Page URL

        Returns:
            Page if found, None otherwise

        Raises:
            Exception: Database errors
        """
        try:
            query = """
                SELECT id, document_id, url, content, content_hash, content_length, crawled_at, status, metadata
                FROM pages
                WHERE url = $1
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [url])
                rows = result.result()
                if rows:
                    page = self._row_to_page(rows[0])
                    logger.debug(f"Retrieved page by URL '{url}' (ID {page.id})")
                    return page
                logger.debug(f"Page with URL '{url}' not found")
                return None
        except Exception as e:
            logger.error(f"Failed to get page by URL '{url}': {e}")
            raise

    async def list_by_document(
        self, document_id: int, status: Optional[str] = None, offset: int = 0, limit: int = 100
    ) -> List[Page]:
        """
        List pages for a document, optionally filtered by status.

        Args:
            document_id: Document ID
            status: Optional status filter ('pending', 'grouped', 'deleted')
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of pages

        Raises:
            Exception: Database errors
        """
        try:
            if status:
                query = """
                    SELECT id, document_id, url, content, content_hash, content_length, crawled_at, status, metadata
                    FROM pages
                    WHERE document_id = $1 AND status = $2
                    ORDER BY crawled_at DESC
                    LIMIT $3 OFFSET $4
                """
                params = [document_id, status, limit, offset]
            else:
                query = """
                    SELECT id, document_id, url, content, content_hash, content_length, crawled_at, status, metadata
                    FROM pages
                    WHERE document_id = $1
                    ORDER BY crawled_at DESC
                    LIMIT $2 OFFSET $3
                """
                params = [document_id, limit, offset]

            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, params)
                rows = result.result()
                pages = [self._row_to_page(row) for row in rows]
                logger.debug(
                    f"Listed {len(pages)} pages for document {document_id} "
                    f"(status={status}, offset={offset}, limit={limit})"
                )
                return pages
        except Exception as e:
            logger.error(
                f"Failed to list pages for document {document_id} "
                f"(status={status}, offset={offset}, limit={limit}): {e}"
            )
            raise

    async def count_by_document(self, document_id: int, status: Optional[str] = None) -> int:
        """
        Count pages for a document.

        Args:
            document_id: Document ID
            status: Optional status filter

        Returns:
            Number of pages

        Raises:
            Exception: Database errors
        """
        try:
            if status:
                query = "SELECT COUNT(*) as count FROM pages WHERE document_id = $1 AND status = $2"
                params = [document_id, status]
            else:
                query = "SELECT COUNT(*) as count FROM pages WHERE document_id = $1"
                params = [document_id]

            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, params)
                rows = result.result()
                count = rows[0]["count"] if rows else 0
                logger.debug(f"Counted {count} pages for document {document_id} (status={status})")
                return count
        except Exception as e:
            logger.error(f"Failed to count pages for document {document_id} (status={status}): {e}")
            raise

    async def update_status(self, page_id: int, status: str) -> bool:
        """
        Update page status.

        Args:
            page_id: Page ID to update
            status: New status ('pending', 'grouped', 'deleted')

        Returns:
            True if page was updated, False otherwise

        Raises:
            ValueError: If status is invalid
            Exception: Database errors
        """
        try:
            # Validate status
            valid_statuses = {"pending", "grouped", "deleted"}
            if status not in valid_statuses:
                raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

            query = "UPDATE pages SET status = $1 WHERE id = $2"
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [status, page_id])
                # PSQLPy result contains string representation like "UPDATE 1" or "UPDATE 0"
                result_str = str(result.result())
                updated = "UPDATE 0" not in result_str and result.result() != 0
                if updated:
                    logger.info(f"Updated page {page_id} status to '{status}'")
                else:
                    logger.warning(f"No page found with ID {page_id} to update status")
                return updated
        except Exception as e:
            logger.error(f"Failed to update page {page_id} status to '{status}': {e}")
            raise

    async def update_status_bulk(self, page_ids: List[int], status: str) -> int:
        """
        Update status for multiple pages.

        Args:
            page_ids: List of page IDs to update
            status: New status for all pages

        Returns:
            Number of pages updated

        Raises:
            ValueError: If status is invalid
            Exception: Database errors
        """
        try:
            # Validate status
            valid_statuses = {"pending", "grouped", "deleted"}
            if status not in valid_statuses:
                raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

            if not page_ids:
                logger.warning("update_status_bulk called with empty page_ids list")
                return 0

            # Build query with IN clause
            placeholders = ", ".join(f"${i+2}" for i in range(len(page_ids)))
            query = f"UPDATE pages SET status = $1 WHERE id IN ({placeholders})"

            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [status] + page_ids)
                # For UPDATE queries, PSQLPy returns an empty list on success
                # We assume all requested pages were updated if no exception
                count = len(page_ids)

                logger.info(f"Updated {count} pages to status '{status}'")
                return count
        except Exception as e:
            logger.error(f"Failed to bulk update {len(page_ids)} pages to status '{status}': {e}")
            raise

    async def delete(self, page_id: int) -> bool:
        """
        Soft delete page (mark as deleted).

        Args:
            page_id: Page ID to delete

        Returns:
            True if page was deleted, False otherwise

        Raises:
            Exception: Database errors
        """
        try:
            # Soft delete by updating status
            return await self.update_status(page_id, "deleted")
        except Exception as e:
            logger.error(f"Failed to delete page {page_id}: {e}")
            raise

    async def delete_bulk(self, page_ids: List[int]) -> int:
        """
        Soft delete multiple pages.

        Args:
            page_ids: List of page IDs to delete

        Returns:
            Number of pages deleted

        Raises:
            Exception: Database errors
        """
        try:
            # Soft delete by bulk updating status
            return await self.update_status_bulk(page_ids, "deleted")
        except Exception as e:
            logger.error(f"Failed to bulk delete {len(page_ids)} pages: {e}")
            raise

    async def check_duplicates(self, content_hashes: List[str]) -> Set[str]:
        """
        Check which content hashes already exist in the database.

        Args:
            content_hashes: List of content hashes to check

        Returns:
            Set of existing content hashes

        Raises:
            Exception: Database errors
        """
        try:
            if not content_hashes:
                return set()

            # Build query with IN clause
            placeholders = ", ".join(f"${i+1}" for i in range(len(content_hashes)))
            query = (
                f"SELECT DISTINCT content_hash FROM pages WHERE content_hash IN ({placeholders})"
            )

            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, content_hashes)
                rows = result.result()
                existing_hashes = {row["content_hash"] for row in rows}
                logger.debug(
                    f"Found {len(existing_hashes)} existing content hashes out of {len(content_hashes)} checked"
                )
                return existing_hashes
        except Exception as e:
            logger.error(f"Failed to check duplicates for {len(content_hashes)} hashes: {e}")
            raise

    def _row_to_page(self, row: dict) -> Page:
        """
        Convert database row dict to Page model.

        PSQLPy returns rows as dicts with column names as keys.

        Args:
            row: Database row dict with columns: id, document_id, url, content,
                 content_hash, content_length, crawled_at, status, metadata

        Returns:
            Page model instance
        """
        return Page(
            id=row["id"],
            document_id=row["document_id"],
            url=row["url"],
            content=row["content"],
            content_hash=row["content_hash"],
            content_length=row["content_length"],
            crawled_at=row["crawled_at"],
            status=row["status"],
            metadata=row.get("metadata") or {},  # Ensure empty dict if NULL
        )
