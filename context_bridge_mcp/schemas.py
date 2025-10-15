"""JSON schemas for MCP tool input/output validation."""

from typing import Any


# Input schemas
FIND_DOCUMENTS_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["query"],
    "properties": {
        "query": {"type": "string", "description": "Search query for document name/description"},
        "limit": {
            "type": "integer",
            "description": "Maximum results",
            "minimum": 1,
            "maximum": 100,
            "default": 10,
        },
    },
}

SEARCH_CONTENT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["query"],
    "properties": {
        "query": {"type": "string", "description": "Search query for content"},
        "document_id": {"type": "integer", "description": "Limit search to specific document"},
        "limit": {
            "type": "integer",
            "description": "Maximum results",
            "minimum": 1,
            "maximum": 50,
            "default": 10,
        },
        "vector_weight": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Weight for vector similarity",
        },
        "bm25_weight": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Weight for BM25 score",
        },
    },
}


# Output schemas (for reference - not used directly in MCP)
DOCUMENT_INFO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "source_url": {"type": "string"},
        "total_pages": {"type": "integer"},
        "total_chunks": {"type": "integer"},
        "created_at": {"type": "string", "format": "date-time"},
    },
    "required": [
        "id",
        "name",
        "version",
        "source_url",
        "total_pages",
        "total_chunks",
        "created_at",
    ],
}

SEARCH_RESULT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "document_name": {"type": "string"},
        "document_version": {"type": "string"},
        "chunk_content": {"type": "string"},
        "page_url": {"type": "string"},
        "score": {"type": "number"},
        "rank": {"type": "integer"},
    },
    "required": ["document_name", "document_version", "chunk_content", "page_url", "score", "rank"],
}
