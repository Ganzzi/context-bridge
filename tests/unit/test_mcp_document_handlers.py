"""Unit tests for MCP document tool handlers."""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock

from context_bridge_mcp.server import (
    _handle_find_documents,
    _handle_search_content,
)
from context_bridge import ContextBridge
from context_bridge.database.repositories.document_repository import Document
from context_bridge.database.repositories.chunk_repository import Chunk
from context_bridge.service.search_service import ContentSearchResult


@pytest.mark.asyncio
async def test_handle_find_documents_with_results():
    """Test find_documents handler returns documents in proper JSON format."""
    # Setup mock bridge
    mock_bridge = AsyncMock(spec=ContextBridge)
    now = datetime.now(timezone.utc)
    mock_documents = [
        Document(
            id=1,
            name="Python Guide",
            version="1.0.0",
            description="A comprehensive Python guide",
            source_url="https://example.com/python",
            created_at=now,
            updated_at=now,
        ),
        Document(
            id=2,
            name="API Documentation",
            version="2.1.0",
            description="REST API documentation",
            source_url="https://example.com/api",
            created_at=now,
            updated_at=now,
        ),
    ]

    mock_bridge.find_documents = AsyncMock(return_value=mock_documents)

    # Call handler
    result = await _handle_find_documents(mock_bridge, {"query": "python", "limit": 10})

    # Verify result structure
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    # Parse JSON response
    response = json.loads(content.text)
    assert "documents" in response
    assert "count" in response
    assert response["count"] == 2
    assert len(response["documents"]) == 2

    # Verify document structure
    first_doc = response["documents"][0]
    assert first_doc["name"] == "Python Guide"
    assert first_doc["version"] == "1.0.0"
    assert first_doc["description"] == "A comprehensive Python guide"
    assert first_doc["source_url"] == "https://example.com/python"
    assert "id" in first_doc
    assert "created_at" in first_doc


@pytest.mark.asyncio
async def test_handle_find_documents_empty_results():
    """Test find_documents handler with no results."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.find_documents = AsyncMock(return_value=[])

    # Call handler
    result = await _handle_find_documents(mock_bridge, {"query": "nonexistent", "limit": 10})

    # Verify result structure
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    # Parse JSON response
    response = json.loads(content.text)
    assert response["count"] == 0
    assert response["documents"] == []
    assert "message" in response


@pytest.mark.asyncio
async def test_handle_find_documents_with_limit():
    """Test find_documents handler respects limit parameter."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    now = datetime.now(timezone.utc)
    mock_documents = [
        Document(
            id=i,
            name=f"Doc {i}",
            version="1.0.0",
            description=f"Description {i}",
            source_url=f"https://example.com/doc{i}",
            created_at=now,
            updated_at=now,
        )
        for i in range(5)
    ]

    mock_bridge.find_documents = AsyncMock(return_value=mock_documents)

    # Call handler with limit
    result = await _handle_find_documents(mock_bridge, {"query": "doc", "limit": 5})

    # Verify bridge was called with correct limit
    mock_bridge.find_documents.assert_called_once_with(query="doc", limit=5)

    # Parse response
    response = json.loads(result[0].text)
    assert response["count"] == 5


@pytest.mark.asyncio
async def test_handle_find_documents_exception():
    """Test find_documents handler handles exceptions gracefully."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.find_documents = AsyncMock(side_effect=Exception("Database connection error"))

    # Call handler
    result = await _handle_find_documents(mock_bridge, {"query": "python"})

    # Verify error response structure
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    response = json.loads(content.text)
    assert "error" in response
    assert response["count"] == 0
    assert response["documents"] == []


@pytest.mark.asyncio
async def test_handle_search_content_with_results():
    """Test search_content handler returns search results in proper format."""
    # Setup mock bridge
    mock_bridge = AsyncMock(spec=ContextBridge)

    # Create mock chunk
    mock_chunk_1 = Chunk(
        id=1,
        document_id=1,
        group_id=None,
        chunk_index=0,
        content="Python is a high-level programming language",
        embedding=[0.1] * 384,
        created_at=datetime.now(timezone.utc),
    )

    mock_chunk_2 = Chunk(
        id=2,
        document_id=1,
        group_id=None,
        chunk_index=1,
        content="Python supports multiple programming paradigms",
        embedding=[0.2] * 384,
        created_at=datetime.now(timezone.utc),
    )

    mock_search_results = [
        ContentSearchResult(
            chunk=mock_chunk_1,
            document_name="Python Guide",
            document_version="1.0.0",
            document_source_url="https://example.com/python",
            score=0.95,
            rank=1,
        ),
        ContentSearchResult(
            chunk=mock_chunk_2,
            document_name="Python Guide",
            document_version="1.0.0",
            document_source_url="https://example.com/python",
            score=0.87,
            rank=2,
        ),
    ]

    mock_bridge.search = AsyncMock(return_value=mock_search_results)

    # Call handler
    result = await _handle_search_content(
        mock_bridge,
        {
            "query": "python",
            "document_id": 1,
            "limit": 10,
        },
    )

    # Verify result structure
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    # Parse JSON response
    response = json.loads(content.text)
    assert "results" in response
    assert "count" in response
    assert response["count"] == 2
    assert len(response["results"]) == 2

    # Verify search result structure
    first_result = response["results"][0]
    assert first_result["document_name"] == "Python Guide"
    assert first_result["document_version"] == "1.0.0"
    assert "chunk_content" in first_result
    assert first_result["score"] == 0.95
    assert first_result["rank"] == 1


@pytest.mark.asyncio
async def test_handle_search_content_no_document_id():
    """Test search_content handler requires document_id."""
    mock_bridge = AsyncMock(spec=ContextBridge)

    # Call handler without document_id
    result = await _handle_search_content(
        mock_bridge,
        {
            "query": "python",
        },
    )

    # Verify error response
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    response = json.loads(content.text)
    assert "error" in response
    assert "document_id is required" in response["error"]
    assert response["results"] == []
    assert response["count"] == 0

    # Verify bridge was NOT called
    mock_bridge.search.assert_not_called()


@pytest.mark.asyncio
async def test_handle_search_content_empty_results():
    """Test search_content handler with no search results."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.search = AsyncMock(return_value=[])

    # Call handler
    result = await _handle_search_content(
        mock_bridge,
        {
            "query": "nonexistent",
            "document_id": 1,
            "limit": 10,
        },
    )

    # Verify result structure
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    response = json.loads(content.text)
    assert response["count"] == 0
    assert response["results"] == []
    assert "message" in response


@pytest.mark.asyncio
async def test_handle_search_content_with_weights():
    """Test search_content handler passes weight parameters correctly."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.search = AsyncMock(return_value=[])

    # Call handler with custom weights
    result = await _handle_search_content(
        mock_bridge,
        {
            "query": "python",
            "document_id": 1,
            "limit": 5,
            "vector_weight": 0.7,
            "bm25_weight": 0.3,
        },
    )

    # Verify bridge was called with weights
    mock_bridge.search.assert_called_once_with(
        query="python",
        document_id=1,
        limit=5,
        vector_weight=0.7,
        bm25_weight=0.3,
    )


@pytest.mark.asyncio
async def test_handle_search_content_default_limit():
    """Test search_content handler uses default limit."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.search = AsyncMock(return_value=[])

    # Call handler without explicit limit
    result = await _handle_search_content(
        mock_bridge,
        {
            "query": "python",
            "document_id": 1,
        },
    )

    # Verify default limit was used
    mock_bridge.search.assert_called_once()
    call_args = mock_bridge.search.call_args
    assert call_args.kwargs["limit"] == 10


@pytest.mark.asyncio
async def test_handle_search_content_exception():
    """Test search_content handler handles exceptions gracefully."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.search = AsyncMock(side_effect=Exception("Search index error"))

    # Call handler
    result = await _handle_search_content(
        mock_bridge,
        {
            "query": "python",
            "document_id": 1,
        },
    )

    # Verify error response structure
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    response = json.loads(content.text)
    assert "error" in response
    assert "Search index error" in response["error"]


@pytest.mark.asyncio
async def test_handle_find_documents_json_serializable():
    """Test that find_documents response is valid JSON."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    now_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock_documents = [
        Document(
            id=i,
            name=f"Doc {i}",
            version=f"{i}.0.0",
            description=f"Description {i}",
            source_url=f"https://example.com/doc{i}",
            created_at=now_time,
            updated_at=now_time,
        )
        for i in range(3)
    ]

    mock_bridge.find_documents = AsyncMock(return_value=mock_documents)

    # Call handler
    result = await _handle_find_documents(mock_bridge, {"query": "doc", "limit": 3})

    # Verify JSON is valid by parsing
    content = result[0]
    response = json.loads(content.text)

    # Verify we can serialize it back
    serialized = json.dumps(response)
    assert isinstance(serialized, str)
    assert len(serialized) > 0


@pytest.mark.asyncio
async def test_handle_search_content_json_serializable():
    """Test that search_content response is valid JSON."""
    mock_bridge = AsyncMock(spec=ContextBridge)

    mock_chunk = Chunk(
        id=1,
        document_id=1,
        group_id=None,
        chunk_index=0,
        content="Sample content",
        embedding=[0.1] * 384,
        created_at=datetime.now(timezone.utc),
    )

    mock_search_results = [
        ContentSearchResult(
            chunk=mock_chunk,
            document_name="Doc",
            document_version="1.0.0",
            document_source_url="https://example.com",
            score=0.95,
            rank=1,
        ),
    ]

    mock_bridge.search = AsyncMock(return_value=mock_search_results)

    # Call handler
    result = await _handle_search_content(
        mock_bridge,
        {"query": "test", "document_id": 1},
    )

    # Verify JSON is valid
    content = result[0]
    response = json.loads(content.text)
    serialized = json.dumps(response)
    assert isinstance(serialized, str)
    assert len(serialized) > 0


@pytest.mark.asyncio
async def test_handle_find_documents_missing_optional_fields():
    """Test find_documents handles documents with missing optional fields."""
    mock_bridge = AsyncMock(spec=ContextBridge)

    now = datetime.now(timezone.utc)
    # Document with None values for optional fields
    mock_document = Document(
        id=1,
        name="Minimal Doc",
        version="1.0.0",
        description=None,
        source_url=None,
        created_at=now,
        updated_at=now,
    )

    mock_bridge.find_documents = AsyncMock(return_value=[mock_document])

    # Call handler
    result = await _handle_find_documents(mock_bridge, {"query": "doc"})

    # Verify response handles None gracefully
    response = json.loads(result[0].text)
    doc = response["documents"][0]
    assert doc["name"] == "Minimal Doc"
    assert doc["source_url"] == ""  # Converted from None
    assert doc["description"] is None


@pytest.mark.asyncio
async def test_handle_search_content_return_format():
    """Test search_content return format matches expected structure."""
    mock_bridge = AsyncMock(spec=ContextBridge)

    mock_chunk = Chunk(
        id=1,
        document_id=1,
        group_id=None,
        chunk_index=0,
        content="Test content about Python",
        embedding=[0.1] * 384,
        created_at=datetime.now(timezone.utc),
    )

    mock_search_results = [
        ContentSearchResult(
            chunk=mock_chunk,
            document_name="Python Guide",
            document_version="1.0.0",
            document_source_url="https://example.com/python",
            score=0.92,
            rank=1,
        ),
    ]

    mock_bridge.search = AsyncMock(return_value=mock_search_results)

    # Call handler
    result = await _handle_search_content(
        mock_bridge,
        {"query": "python", "document_id": 1},
    )

    response = json.loads(result[0].text)

    # Verify expected structure
    assert "results" in response
    assert "count" in response
    assert "query" in response
    assert "document_id" in response
    assert response["query"] == "python"
    assert response["document_id"] == 1

    # Verify results structure
    result_item = response["results"][0]
    assert "document_name" in result_item
    assert "document_version" in result_item
    assert "chunk_content" in result_item
    assert "score" in result_item
    assert "rank" in result_item
