from typing import List, Optional, Dict, Any
import logging
from pydantic import BaseModel, Field

from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from context_bridge.database.repositories.chunk_repository import (
    ChunkRepository,
    Chunk,
    SearchResult,
)
from context_bridge.service.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class DocumentSearchResult(BaseModel):
    """Document search result."""

    document: Document
    relevance_score: float


class ContentSearchResult(BaseModel):
    """Content search result with context."""

    chunk: Chunk
    document_name: str
    document_version: str
    document_source_url: str
    score: float
    rank: int


class SearchService:
    """
    Service for orchestrating search operations across documents and content.

    This service provides high-level search functionality by coordinating
    between document repositories, chunk repositories, and embedding services.
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        embedding_service: EmbeddingService,
        default_vector_weight: float = 0.7,
        default_bm25_weight: float = 0.3,
    ):
        """
        Initialize search service with required dependencies.

        Args:
            document_repo: Repository for document operations
            chunk_repo: Repository for chunk operations
            embedding_service: Service for generating embeddings
            default_vector_weight: Default weight for vector similarity in hybrid search
            default_bm25_weight: Default weight for BM25 score in hybrid search
        """
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.embedding_service = embedding_service
        self.default_vector_weight = default_vector_weight
        self.default_bm25_weight = default_bm25_weight

        logger.debug("SearchService initialized")

    async def find_documents(self, query: str, limit: int = 10) -> List[DocumentSearchResult]:
        """
        Find documents by query.
        Searches document name, description, and metadata.
        Returns documents sorted by relevance.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of DocumentSearchResult sorted by relevance score

        Raises:
            Exception: Database or embedding errors
        """
        try:
            # Search documents using repository's find_by_query method
            documents = await self.document_repo.find_by_query(
                query=query, limit=limit, search_fields=["name", "description", "source_url"]
            )

            # Calculate relevance scores based on text matching
            results = []
            for doc in documents:
                # Simple relevance scoring based on field matches
                score = self._calculate_document_relevance(query, doc)
                results.append(DocumentSearchResult(document=doc, relevance_score=score))

            # Sort by relevance score descending
            results.sort(key=lambda x: x.relevance_score, reverse=True)

            logger.debug(f"Found {len(results)} documents matching '{query}'")
            return results

        except Exception as e:
            logger.error(f"Failed to find documents for query '{query}': {e}")
            raise

    async def search_content(
        self,
        query: str,
        document_id: int,
        version: Optional[str] = None,
        limit: int = 10,
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None,
    ) -> List[ContentSearchResult]:
        """
        Search within document content using hybrid search.

        Steps:
        1. Generate query embedding
        2. Perform hybrid search in chunks
        3. Enrich results with document metadata
        4. Return ranked results

        Args:
            query: Search query text
            document_id: Document ID to search within
            version: Optional version filter (for future use)
            limit: Maximum number of results
            vector_weight: Weight for vector similarity (0-1)
            bm25_weight: Weight for BM25 score (0-1)

        Returns:
            List of ContentSearchResult ordered by combined score

        Raises:
            Exception: Database or embedding errors
        """
        try:
            # Use default weights if not specified
            vec_weight = vector_weight if vector_weight is not None else self.default_vector_weight
            bm25_wt = bm25_weight if bm25_weight is not None else self.default_bm25_weight

            # Generate embedding for the query
            query_embedding = await self.embedding_service.get_embedding(query)

            # Perform hybrid search
            chunk_results: List[SearchResult] = await self.chunk_repo.hybrid_search(
                document_id=document_id,
                query=query,
                query_embedding=query_embedding,
                vector_weight=vec_weight,
                bm25_weight=bm25_wt,
                limit=limit,
            )

            # Get document info for enrichment
            document = await self.document_repo.get_by_id(document_id)
            if not document:
                logger.warning(f"Document {document_id} not found for content search")
                return []

            # Convert to ContentSearchResult
            results = []
            for chunk_result in chunk_results:
                result = ContentSearchResult(
                    chunk=chunk_result.chunk,
                    document_name=document.name,
                    document_version=document.version,
                    document_source_url=document.source_url,
                    score=chunk_result.score,
                    rank=chunk_result.rank,
                )
                results.append(result)

            logger.debug(
                f"Found {len(results)} content results for query '{query}' in document {document_id}"
            )
            return results

        except Exception as e:
            logger.error(
                f"Failed to search content for query '{query}' in document {document_id}: {e}"
            )
            raise

    async def search_across_versions(
        self, query: str, document_name: str, limit_per_version: int = 5
    ) -> Dict[str, List[ContentSearchResult]]:
        """
        Search across all versions of a document.
        Returns dict mapping version -> results.

        Args:
            query: Search query text
            document_name: Name of the document to search across versions
            limit_per_version: Maximum results per version

        Returns:
            Dict mapping version strings to lists of ContentSearchResult

        Raises:
            Exception: Database or embedding errors
        """
        try:
            # Get all versions of the document
            versions = await self.document_repo.list_versions(document_name)
            if not versions:
                logger.debug(f"No versions found for document '{document_name}'")
                return {}

            # Generate query embedding once
            query_embedding = await self.embedding_service.get_embedding(query)

            # Search each version
            results_by_version = {}

            for version in versions:
                # Get document by name and version
                document = await self.document_repo.get_by_name_version(document_name, version)
                if not document:
                    logger.warning(f"Document '{document_name}' v{version} not found")
                    continue

                try:
                    # Perform hybrid search for this version
                    chunk_results = await self.chunk_repo.hybrid_search(
                        document_id=document.id,
                        query=query,
                        query_embedding=query_embedding,
                        vector_weight=self.default_vector_weight,
                        bm25_weight=self.default_bm25_weight,
                        limit=limit_per_version,
                    )

                    # Convert to ContentSearchResult
                    content_results = []
                    for chunk_result in chunk_results:
                        result = ContentSearchResult(
                            chunk=chunk_result.chunk,
                            document_name=document.name,
                            document_version=document.version,
                            document_source_url=document.source_url,
                            score=chunk_result.score,
                            rank=chunk_result.rank,
                        )
                        content_results.append(result)

                    if content_results:
                        results_by_version[version] = content_results

                except Exception as e:
                    logger.warning(f"Failed to search version {version} of '{document_name}': {e}")
                    continue

            logger.debug(
                f"Searched {len(versions)} versions of '{document_name}', found results in {len(results_by_version)} versions"
            )
            return results_by_version

        except Exception as e:
            logger.error(f"Failed to search across versions for '{document_name}': {e}")
            raise

    def _calculate_document_relevance(self, query: str, document: Document) -> float:
        """
        Calculate relevance score for document search results.

        Uses simple text matching heuristics:
        - Exact match in name: highest score
        - Partial match in name: high score
        - Match in description: medium score
        - Match in source_url: low score

        Args:
            query: Search query (case-insensitive)
            document: Document to score

        Returns:
            Relevance score between 0.0 and 1.0
        """
        query_lower = query.lower()
        score = 0.0

        # Check name (highest weight)
        name_lower = document.name.lower()
        if query_lower == name_lower:
            score += 1.0  # Exact match
        elif query_lower in name_lower:
            score += 0.7  # Partial match

        # Check description
        if document.description:
            desc_lower = document.description.lower()
            if query_lower in desc_lower:
                score += 0.4

        # Check source URL
        if document.source_url:
            url_lower = document.source_url.lower()
            if query_lower in url_lower:
                score += 0.2

        # Check metadata (basic key/value search)
        if document.metadata:
            metadata_str = str(document.metadata).lower()
            if query_lower in metadata_str:
                score += 0.1

        # Normalize to 0-1 range (max possible score is ~2.4, but cap at 1.0)
        return min(score, 1.0)
