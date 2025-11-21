"""Unit tests for MCP tag tool handlers."""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from context_bridge_mcp.server import (
    _handle_list_tags,
    _handle_add_document_tags,
    _handle_remove_tag,
)
from context_bridge import ContextBridge
from context_bridge.database.models.tag_models import Tag, TagCategory


@pytest.mark.asyncio
async def test_handle_list_tags():
    """Test list_tags handler returns proper JSON response."""
    # Setup mock bridge
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_tags = [
        Tag(
            id=1,
            name="Python",
            category=TagCategory.TECHNOLOGY,
            description="Python programming language",
            created_at=datetime.now(timezone.utc),
        ),
        Tag(
            id=2,
            name="API",
            category=TagCategory.TECHNOLOGY,
            description="API-related documentation",
            created_at=datetime.now(timezone.utc),
        ),
    ]

    mock_bridge.list_tags = AsyncMock(return_value=mock_tags)

    # Call handler
    result = await _handle_list_tags(mock_bridge, {})

    # Verify result structure
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    # Parse JSON response
    response = json.loads(content.text)
    assert "tags" in response
    assert "count" in response
    assert response["count"] == 2
    assert len(response["tags"]) == 2
    assert response["tags"][0]["name"] == "Python"
    assert response["tags"][0]["category"] == "technology"


@pytest.mark.asyncio
async def test_handle_list_tags_with_category_filter():
    """Test list_tags handler with category filter."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_tags = [
        Tag(
            id=1,
            name="Python",
            category=TagCategory.TECHNOLOGY,
            description="Python",
            created_at=datetime.now(timezone.utc),
        ),
    ]

    mock_bridge.list_tags = AsyncMock(return_value=mock_tags)

    # Call with category filter
    result = await _handle_list_tags(mock_bridge, {"category": "technology"})

    # Verify bridge was called with category
    mock_bridge.list_tags.assert_called_once_with(category="technology")

    response = json.loads(result[0].text)
    assert response["category_filter"] == "technology"


@pytest.mark.asyncio
async def test_handle_add_document_tags():
    """Test add_document_tags handler returns proper response."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.add_tags_to_document = AsyncMock(return_value=2)

    # Call handler
    result = await _handle_add_document_tags(mock_bridge, {"document_id": 1, "tag_ids": [1, 2]})

    # Verify result
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    response = json.loads(content.text)
    assert response["document_id"] == 1
    assert response["tags_added"] == 2
    assert response["tag_ids"] == [1, 2]

    # Verify bridge was called correctly
    mock_bridge.add_tags_to_document.assert_called_once_with(1, [1, 2])


@pytest.mark.asyncio
async def test_handle_remove_tag_success():
    """Test remove_tag handler when removal succeeds."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.remove_tag_from_document = AsyncMock(return_value=True)

    # Call handler
    result = await _handle_remove_tag(mock_bridge, {"document_id": 1, "tag_id": 5})

    # Verify result
    response = json.loads(result[0].text)
    assert response["document_id"] == 1
    assert response["tag_id"] == 5
    assert response["removed"] is True
    assert "Successfully removed" in response["message"]


@pytest.mark.asyncio
async def test_handle_remove_tag_not_found():
    """Test remove_tag handler when tag not found."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.remove_tag_from_document = AsyncMock(return_value=False)

    # Call handler
    result = await _handle_remove_tag(mock_bridge, {"document_id": 1, "tag_id": 999})

    # Verify result
    response = json.loads(result[0].text)
    assert response["removed"] is False
    assert "not found" in response["message"]


@pytest.mark.asyncio
async def test_handle_list_tags_error():
    """Test list_tags handler error handling."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.list_tags = AsyncMock(side_effect=Exception("Database connection error"))

    # Call handler
    result = await _handle_list_tags(mock_bridge, {})

    # Verify error response
    response = json.loads(result[0].text)
    assert "error" in response
    assert "Database connection error" in response["error"]
    assert response["count"] == 0


@pytest.mark.asyncio
async def test_handle_add_document_tags_error():
    """Test add_document_tags handler error handling."""
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.add_tags_to_document = AsyncMock(side_effect=ValueError("Invalid document ID"))

    # Call handler
    result = await _handle_add_document_tags(mock_bridge, {"document_id": 999, "tag_ids": [1]})

    # Verify error response
    response = json.loads(result[0].text)
    assert "error" in response
    assert "Invalid document ID" in response["error"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
