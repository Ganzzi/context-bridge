"""JSON schemas for MCP tool input/output validation."""

from typing import Any


# Input schemas for MCP tools
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
