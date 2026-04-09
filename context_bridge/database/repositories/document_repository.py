from typing import Optional, List
from datetime import datetime
import logging
from pydantic import BaseModel, Field

from context_bridge.database.postgres_manager import PostgreSQLManager


logger = logging.getLogger(__name__)


class Document(BaseModel):
    """
    Document model representing a versioned documentation source.

    Attributes:
        id: Unique document identifier
        name: Document name (e.g., "Python Guide")
        version: Version string (e.g., "1.0.0")
        source_url: Optional URL where document was sourced
        description: Optional description of the document
        metadata: Additional metadata as JSON object
        tags: List of tag IDs associated with this document (populated from TagRepository)
        created_at: Timestamp when document was created
        updated_at: Timestamp when document was last updated
    """

    id: int
    name: str
    version: str
    source_url: Optional[str] = None
    description: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    tags: List[int] = Field(default_factory=list)  # Tag IDs associated with document
    created_at: datetime
    updated_at: datetime


class DocumentRepository:
    """
    Repository for document CRUD operations using PSQLPy.

    This repository handles all database operations for documents,
    including creation, retrieval, search, updates, and deletion.
    Follows PSQLPy best practices with proper error handling and
    connection management.
    """

    def __init__(self, db_manager: PostgreSQLManager):
        """
        Initialize document repository.

        Args:
            db_manager: PostgreSQL connection manager
        """
        self.db_manager = db_manager
        logger.debug("DocumentRepository initialized")

    async def create(
        self,
        name: str,
        version: str,
        source_url: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        Create a new document and return its ID.

        Args:
            name: Document name
            version: Version string
            source_url: Optional source URL
            description: Optional description
            metadata: Optional metadata dict

        Returns:
            ID of created document

        Raises:
            RuntimeError: If document creation fails
            Exception: Database errors
        """
        try:
            # Use PSQLPy parameter binding with $1, $2, etc.
            query = """
                INSERT INTO documents (name, version, source_url, description, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(
                    query, [name, version, source_url, description, metadata or {}]
                )
                rows = result.result()
                if rows:
                    doc_id = rows[0]["id"]  # PSQLPy returns dicts
                    logger.info(f"Created document '{name}' v{version} with ID {doc_id}")
                    return doc_id
                else:
                    raise RuntimeError(f"Failed to create document '{name}' v{version}")
        except Exception as e:
            logger.error(f"Failed to create document '{name}' v{version}: {e}")
            raise

    async def get_by_id(self, doc_id: int) -> Optional[Document]:
        """
        Get document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document if found, None otherwise

        Raises:
            Exception: Database errors
        """
        try:
            query = """
                SELECT id, name, version, source_url, description, metadata, created_at, updated_at
                FROM documents
                WHERE id = $1
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [doc_id])
                rows = result.result()
                if rows:
                    doc = self._row_to_document(rows[0])
                    logger.debug(f"Retrieved document ID {doc_id}: '{doc.name}' v{doc.version}")
                    return doc
                logger.debug(f"Document ID {doc_id} not found")
                return None
        except Exception as e:
            logger.error(f"Failed to get document by ID {doc_id}: {e}")
            raise

    async def get_by_name_version(self, name: str, version: str) -> Optional[Document]:
        """
        Get document by name and version.

        Args:
            name: Document name
            version: Version string

        Returns:
            Document if found, None otherwise

        Raises:
            Exception: Database errors
        """
        try:
            query = """
                SELECT id, name, version, source_url, description, metadata, created_at, updated_at
                FROM documents
                WHERE name = $1 AND version = $2
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [name, version])
                rows = result.result()
                if rows:
                    doc = self._row_to_document(rows[0])
                    logger.debug(f"Retrieved document '{name}' v{version} (ID {doc.id})")
                    return doc
                logger.debug(f"Document '{name}' v{version} not found")
                return None
        except Exception as e:
            logger.error(f"Failed to get document '{name}' v{version}: {e}")
            raise

    async def find_by_query(
        self, query: str, limit: int = 10, search_fields: Optional[List[str]] = None
    ) -> List[Document]:
        """
        Find documents by text query using ILIKE pattern matching.

        Args:
            query: Search text (will be wrapped with % for ILIKE)
            limit: Maximum number of results (default 10)
            search_fields: Fields to search in (name, description, source_url).
                          Defaults to ['name', 'description']

        Returns:
            List of matching documents

        Raises:
            Exception: Database errors
        """
        try:
            if search_fields is None:
                search_fields = ["name", "description"]

            # Build WHERE clause for specified fields with proper parameter binding
            where_conditions = []
            params = []
            param_count = 1

            for field in search_fields:
                if field in ["name", "description", "source_url"]:
                    where_conditions.append(f"{field} ILIKE ${param_count}")
                    params.append(f"%{query}%")
                    param_count += 1

            if not where_conditions:
                logger.warning(f"No valid search fields provided: {search_fields}")
                return []

            where_clause = " OR ".join(where_conditions)

            search_query = f"""
                SELECT id, name, version, source_url, description, metadata, created_at, updated_at
                FROM documents
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count}
            """
            params.append(limit)

            async with self.db_manager.connection() as conn:
                result = await conn.execute(search_query, params)
                rows = result.result()
                documents = [self._row_to_document(row) for row in rows]
                logger.debug(
                    f"Found {len(documents)} documents matching '{query}' in fields {search_fields}"
                )
                return documents
        except Exception as e:
            logger.error(
                f"Failed to find documents by query '{query}' in fields {search_fields}: {e}"
            )
            raise

    async def list_all(self, offset: int = 0, limit: int = 100) -> List[Document]:
        """
        List all documents with pagination.

        Args:
            offset: Number of records to skip (default 0)
            limit: Maximum number of records to return (default 100)

        Returns:
            List of documents

        Raises:
            Exception: Database errors
        """
        try:
            query = """
                SELECT id, name, version, source_url, description, metadata, created_at, updated_at
                FROM documents
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [limit, offset])
                rows = result.result()
                documents = [self._row_to_document(row) for row in rows]
                logger.debug(f"Listed {len(documents)} documents (offset={offset}, limit={limit})")
                return documents
        except Exception as e:
            logger.error(f"Failed to list documents (offset={offset}, limit={limit}): {e}")
            raise

    async def list_versions(self, name: str) -> List[str]:
        """
        Get all versions of a document by name.

        Args:
            name: Document name

        Returns:
            List of version strings, sorted descending

        Raises:
            Exception: Database errors
        """
        try:
            query = """
                SELECT version
                FROM documents
                WHERE name = $1
                ORDER BY version DESC
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [name])
                rows = result.result()
                versions = [row["version"] for row in rows]  # PSQLPy returns dicts
                logger.debug(f"Found {len(versions)} versions for document '{name}'")
                return versions
        except Exception as e:
            logger.error(f"Failed to list versions for document '{name}': {e}")
            raise

    async def update(self, doc_id: int, **fields) -> bool:
        """
        Update document fields dynamically.

        Args:
            doc_id: Document ID to update
            **fields: Field names and values to update
                     (name, version, source_url, description, metadata)

        Returns:
            True if document was updated, False otherwise

        Raises:
            Exception: Database errors
        """
        try:
            if not fields:
                logger.warning(f"Update called on document {doc_id} with no fields")
                return False

            # Build dynamic update query with proper parameter binding
            set_parts = []
            values = []
            param_count = 1

            allowed_fields = ["name", "version", "source_url", "description", "metadata"]
            for field, value in fields.items():
                if field in allowed_fields:
                    set_parts.append(f"{field} = ${param_count}")
                    values.append(value)
                    param_count += 1
                else:
                    logger.warning(f"Ignoring invalid field '{field}' in update")

            if not set_parts:
                logger.warning(f"No valid fields to update for document {doc_id}")
                return False

            set_clause = ", ".join(set_parts)
            query = f"""
                UPDATE documents
                SET {set_clause}, updated_at = NOW()
                WHERE id = ${param_count}
            """
            values.append(doc_id)

            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, values)
                # PSQLPy result contains string representation like "UPDATE 1" or "UPDATE 0"
                result_str = str(result.result())
                affected = "UPDATE 0" not in result_str and result.result() != 0
                if affected:
                    logger.info(f"Updated document {doc_id} with fields: {list(fields.keys())}")
                else:
                    logger.warning(f"No rows affected when updating document {doc_id}")
                return affected
        except Exception as e:
            logger.error(
                f"Failed to update document {doc_id} with fields {list(fields.keys())}: {e}"
            )
            raise

    async def delete(self, doc_id: int) -> bool:
        """
        Delete document and cascade to all related data.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if document was deleted, False otherwise

        Raises:
            Exception: Database errors
        """
        try:
            query = "DELETE FROM documents WHERE id = $1"
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [doc_id])
                # PSQLPy result contains string representation like "DELETE 1" or "DELETE 0"
                result_str = str(result.result())
                deleted = "DELETE 0" not in result_str and result.result() != 0
                if deleted:
                    logger.info(f"Deleted document ID {doc_id}")
                else:
                    logger.warning(f"No document found with ID {doc_id} to delete")
                return deleted
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            raise

    def _row_to_document(self, row: dict) -> Document:
        """
        Convert database row dict to Document model.

        PSQLPy returns rows as dicts with column names as keys.

        Args:
            row: Database row dict with columns: id, name, version, source_url,
                 description, metadata, created_at, updated_at

        Returns:
            Document model instance
        """
        return Document(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            source_url=row.get("source_url"),
            description=row.get("description"),
            metadata=row.get("metadata") or {},  # Ensure empty dict if NULL
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
