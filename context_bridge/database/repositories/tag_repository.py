"""
Repository for managing tags and document-tag relationships.
"""

import logging
from typing import List, Optional, Dict
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.models.tag_models import (
    Tag,
    TagCreate,
    TagUpdate,
    TagCategory,
    TagStatistics,
)

logger = logging.getLogger(__name__)


class TagRepository:
    """Repository for tag management operations."""

    def __init__(self, db_manager: PostgreSQLManager):
        """
        Initialize TagRepository.

        Args:
            db_manager: PostgreSQL connection manager
        """
        self.db_manager = db_manager

    async def create_tag(self, tag: TagCreate) -> Tag:
        """
        Create a new tag.

        Args:
            tag: TagCreate model with tag data

        Returns:
            Created Tag object

        Raises:
            ValueError: If tag name already exists
            Exception: Database errors
        """
        logger.info(f"Creating tag: {tag.name}")

        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                INSERT INTO tags (name, category, description)
                VALUES ($1, $2, $3)
                RETURNING id, name, category, description, created_at
                """,
                [tag.name, tag.category.value, tag.description],
            )

            row = result.result()
            if not row:
                raise ValueError(f"Failed to create tag: {tag.name}")

            row_data = row[0]
            return Tag(
                id=row_data[0],
                name=row_data[1],
                category=TagCategory(row_data[2]),
                description=row_data[3],
                created_at=row_data[4],
            )

    async def get_tag_by_id(self, tag_id: int) -> Optional[Tag]:
        """
        Get tag by ID.

        Args:
            tag_id: Tag ID

        Returns:
            Tag object or None if not found
        """
        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                SELECT id, name, category, description, created_at
                FROM tags
                WHERE id = $1
                """,
                [tag_id],
            )

            row = result.result()
            if not row:
                return None

            row_data = row[0]
            return Tag(
                id=row_data[0],
                name=row_data[1],
                category=TagCategory(row_data[2]),
                description=row_data[3],
                created_at=row_data[4],
            )

    async def get_tag_by_name(self, name: str) -> Optional[Tag]:
        """
        Get tag by name.

        Args:
            name: Tag name

        Returns:
            Tag object or None if not found
        """
        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                SELECT id, name, category, description, created_at
                FROM tags
                WHERE name = $1
                """,
                [name],
            )

            row = result.result()
            if not row:
                return None

            row_data = row[0]
            return Tag(
                id=row_data[0],
                name=row_data[1],
                category=TagCategory(row_data[2]),
                description=row_data[3],
                created_at=row_data[4],
            )

    async def list_tags(
        self,
        category: Optional[TagCategory] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Tag]:
        """
        List tags with optional category filter.

        Args:
            category: Optional category filter
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of Tag objects
        """
        query = "SELECT id, name, category, description, created_at FROM tags"
        params = []

        if category:
            query += " WHERE category = $1"
            params.append(category.value)
            query += f" ORDER BY name LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
            params.extend([limit, offset])
        else:
            query += f" ORDER BY name LIMIT $1 OFFSET $2"
            params = [limit, offset]

        async with self.db_manager.connection() as conn:
            result = await conn.execute(query, params)

            tags = []
            for row_data in result.result():
                tags.append(
                    Tag(
                        id=row_data[0],
                        name=row_data[1],
                        category=TagCategory(row_data[2]),
                        description=row_data[3],
                        created_at=row_data[4],
                    )
                )

            return tags

    async def list_all_tags(self) -> List[Tag]:
        """
        List all tags (no pagination).

        Returns:
            List of all Tag objects
        """
        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                SELECT id, name, category, description, created_at
                FROM tags
                ORDER BY category, name
                """,
            )

            tags = []
            for row_data in result.result():
                tags.append(
                    Tag(
                        id=row_data[0],
                        name=row_data[1],
                        category=TagCategory(row_data[2]),
                        description=row_data[3],
                        created_at=row_data[4],
                    )
                )

            return tags

    async def update_tag(self, tag_id: int, update: TagUpdate) -> Optional[Tag]:
        """
        Update a tag.

        Args:
            tag_id: Tag ID
            update: TagUpdate model

        Returns:
            Updated Tag object or None if not found
        """
        logger.info(f"Updating tag {tag_id}")

        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                UPDATE tags
                SET description = COALESCE($1, description)
                WHERE id = $2
                RETURNING id, name, category, description, created_at
                """,
                [update.description, tag_id],
            )

            row = result.result()
            if not row:
                return None

            row_data = row[0]
            return Tag(
                id=row_data[0],
                name=row_data[1],
                category=TagCategory(row_data[2]),
                description=row_data[3],
                created_at=row_data[4],
            )

    async def delete_tag(self, tag_id: int) -> bool:
        """
        Delete a tag.

        Args:
            tag_id: Tag ID

        Returns:
            True if deleted, False if not found
        """
        logger.info(f"Deleting tag {tag_id}")

        async with self.db_manager.connection() as conn:
            result = await conn.execute("DELETE FROM tags WHERE id = $1", [tag_id])
            return bool(result.result())

    # =========================================================================
    # Document-Tag Associations
    # =========================================================================

    async def add_tag_to_document(self, document_id: int, tag_id: int) -> bool:
        """
        Add a tag to a document.

        Args:
            document_id: Document ID
            tag_id: Tag ID

        Returns:
            True if successful, False if relationship already exists
        """
        logger.info(f"Adding tag {tag_id} to document {document_id}")

        async with self.db_manager.connection() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO document_tags (document_id, tag_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    [document_id, tag_id],
                )
                return True
            except Exception as e:
                logger.error(f"Failed to add tag to document: {e}")
                return False

    async def add_tags_to_document(self, document_id: int, tag_ids: List[int]) -> int:
        """
        Add multiple tags to a document.

        Args:
            document_id: Document ID
            tag_ids: List of tag IDs

        Returns:
            Number of tags added
        """
        if not tag_ids:
            return 0

        logger.info(f"Adding {len(tag_ids)} tags to document {document_id}")

        added = 0
        for tag_id in tag_ids:
            if await self.add_tag_to_document(document_id, tag_id):
                added += 1

        return added

    async def remove_tag_from_document(self, document_id: int, tag_id: int) -> bool:
        """
        Remove a tag from a document.

        Args:
            document_id: Document ID
            tag_id: Tag ID

        Returns:
            True if removed, False if relationship didn't exist
        """
        logger.info(f"Removing tag {tag_id} from document {document_id}")

        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM document_tags
                WHERE document_id = $1 AND tag_id = $2
                """,
                [document_id, tag_id],
            )
            return bool(result.result())

    async def remove_all_tags_from_document(self, document_id: int) -> int:
        """
        Remove all tags from a document.

        Args:
            document_id: Document ID

        Returns:
            Number of tags removed
        """
        logger.info(f"Removing all tags from document {document_id}")

        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                "DELETE FROM document_tags WHERE document_id = $1",
                [document_id],
            )
            return len(result.result()) if result.result() else 0

    async def get_document_tags(self, document_id: int) -> List[Tag]:
        """
        Get all tags for a document.

        Args:
            document_id: Document ID

        Returns:
            List of Tag objects
        """
        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                SELECT t.id, t.name, t.category, t.description, t.created_at
                FROM tags t
                JOIN document_tags dt ON t.id = dt.tag_id
                WHERE dt.document_id = $1
                ORDER BY t.name
                """,
                [document_id],
            )

            tags = []
            for row_data in result.result():
                tags.append(
                    Tag(
                        id=row_data[0],
                        name=row_data[1],
                        category=TagCategory(row_data[2]),
                        description=row_data[3],
                        created_at=row_data[4],
                    )
                )

            return tags

    async def get_documents_by_tag(
        self, tag_id: int, limit: int = 100, offset: int = 0
    ) -> List[int]:
        """
        Get all document IDs with a specific tag.

        Args:
            tag_id: Tag ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of document IDs
        """
        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                SELECT document_id
                FROM document_tags
                WHERE tag_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                [tag_id, limit, offset],
            )

            return [row[0] for row in result.result()]

    async def get_documents_by_tags(
        self,
        tag_ids: List[int],
        match_all: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[int]:
        """
        Get documents matching one or more tags.

        Args:
            tag_ids: List of tag IDs
            match_all: If True, document must have ALL tags. If False, ANY tag.
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of document IDs
        """
        if not tag_ids:
            return []

        if match_all:
            # Document must have ALL tags
            placeholders = ",".join(f"${i}" for i in range(1, len(tag_ids) + 1))
            query = f"""
                SELECT document_id
                FROM document_tags
                WHERE tag_id IN ({placeholders})
                GROUP BY document_id
                HAVING COUNT(DISTINCT tag_id) = ${{len(tag_ids) + 1}}
                ORDER BY document_id DESC
                LIMIT ${{len(tag_ids) + 2}} OFFSET ${{len(tag_ids) + 3}}
            """
            params = tag_ids + [len(tag_ids), limit, offset]
        else:
            # Document can have ANY tag
            placeholders = ",".join(f"${i}" for i in range(1, len(tag_ids) + 1))
            query = f"""
                SELECT DISTINCT document_id
                FROM document_tags
                WHERE tag_id IN ({placeholders})
                ORDER BY document_id DESC
                LIMIT ${len(tag_ids) + 1} OFFSET ${len(tag_ids) + 2}
            """
            params = tag_ids + [limit, offset]

        async with self.db_manager.connection() as conn:
            result = await conn.execute(query, params)
            return [row[0] for row in result.result()]

    async def get_tag_statistics(self) -> List[TagStatistics]:
        """
        Get statistics for all tags (usage counts).

        Returns:
            List of TagStatistics objects
        """
        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                SELECT
                    t.id,
                    t.name,
                    t.category,
                    COUNT(dt.document_id) as usage_count,
                    t.created_at
                FROM tags t
                LEFT JOIN document_tags dt ON t.id = dt.tag_id
                GROUP BY t.id, t.name, t.category, t.created_at
                ORDER BY usage_count DESC, t.name
                """
            )

            stats = []
            for row_data in result.result():
                stats.append(
                    TagStatistics(
                        tag_id=row_data[0],
                        name=row_data[1],
                        category=TagCategory(row_data[2]),
                        usage_count=row_data[3],
                        created_at=row_data[4],
                    )
                )

            return stats

    async def get_tag_statistics_by_category(self, category: TagCategory) -> List[TagStatistics]:
        """
        Get statistics for tags in a category.

        Args:
            category: Tag category

        Returns:
            List of TagStatistics objects for category
        """
        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                SELECT
                    t.id,
                    t.name,
                    t.category,
                    COUNT(dt.document_id) as usage_count,
                    t.created_at
                FROM tags t
                LEFT JOIN document_tags dt ON t.id = dt.tag_id
                WHERE t.category = $1
                GROUP BY t.id, t.name, t.category, t.created_at
                ORDER BY usage_count DESC, t.name
                """,
                [category.value],
            )

            stats = []
            for row_data in result.result():
                stats.append(
                    TagStatistics(
                        tag_id=row_data[0],
                        name=row_data[1],
                        category=TagCategory(row_data[2]),
                        usage_count=row_data[3],
                        created_at=row_data[4],
                    )
                )

            return stats

    async def count_tags_by_category(self) -> Dict[str, int]:
        """
        Get count of tags in each category.

        Returns:
            Dictionary mapping category names to counts
        """
        async with self.db_manager.connection() as conn:
            result = await conn.execute(
                """
                SELECT category, COUNT(*) as count
                FROM tags
                GROUP BY category
                ORDER BY category
                """
            )

            counts = {}
            for row_data in result.result():
                counts[row_data[0]] = row_data[1]

            return counts
