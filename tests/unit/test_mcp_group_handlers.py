"""Unit tests for MCP group tool handlers."""

import json
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

from context_bridge_mcp.server import (
    _handle_list_groups,
    _handle_get_group_status,
)
from context_bridge import ContextBridge


@pytest.mark.asyncio
async def test_handle_list_groups_for_document():
    """Test list_groups handler for a specific document."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id_1 = uuid4()
    group_id_2 = uuid4()

    mock_groups = [
        {
            "id": str(group_id_1),
            "document_id": 1,
            "name": "API Documentation",
            "description": "API docs",
            "context_enabled": False,
            "context_model": None,
            "total_pages": 5,
            "total_chunks": 25,
            "processing_status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": str(group_id_2),
            "document_id": 1,
            "name": "Examples",
            "description": "Example docs",
            "context_enabled": True,
            "context_model": "anthropic:claude-3-5-sonnet-20241022",
            "total_pages": 8,
            "total_chunks": 40,
            "processing_status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    ]

    mock_bridge.list_groups = AsyncMock(return_value=mock_groups)

    # Call handler
    result = await _handle_list_groups(mock_bridge, {"document_id": 1, "limit": 100, "offset": 0})

    # Verify result
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    response = json.loads(content.text)
    assert "groups" in response
    assert "count" in response
    assert response["count"] == 2
    assert len(response["groups"]) == 2
    assert response["groups"][0]["name"] == "API Documentation"
    assert response["groups"][1]["context_enabled"] is True
    mock_bridge.list_groups.assert_called_once_with(document_id=1, limit=100, offset=0)


@pytest.mark.asyncio
async def test_handle_list_groups_all_documents():
    """Test list_groups handler for all documents."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_groups = [
        {
            "id": str(group_id),
            "document_id": 1,
            "name": "Group 1",
            "description": "First group",
            "context_enabled": False,
            "context_model": None,
            "total_pages": 5,
            "total_chunks": 25,
            "processing_status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processed_at": None,
        },
    ]

    mock_bridge.list_groups = AsyncMock(return_value=mock_groups)

    # Call without document_id
    result = await _handle_list_groups(mock_bridge, {})

    # Verify bridge was called with correct defaults
    mock_bridge.list_groups.assert_called_once_with(document_id=None, limit=100, offset=0)

    response = json.loads(result[0].text)
    assert response["count"] == 1
    assert response["document_id"] is None


@pytest.mark.asyncio
async def test_handle_list_groups_empty():
    """Test list_groups handler when no groups found."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.list_groups = AsyncMock(return_value=[])

    # Call handler
    result = await _handle_list_groups(mock_bridge, {"document_id": 1})

    # Verify result
    response = json.loads(result[0].text)
    assert response["count"] == 0
    assert response["groups"] == []
    assert "message" in response


@pytest.mark.asyncio
async def test_handle_list_groups_pagination():
    """Test list_groups handler with pagination."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_groups = [
        {
            "id": str(group_id),
            "document_id": 1,
            "name": "Group",
            "description": "Test",
            "context_enabled": False,
            "context_model": None,
            "total_pages": 5,
            "total_chunks": 25,
            "processing_status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processed_at": None,
        },
    ]

    mock_bridge.list_groups = AsyncMock(return_value=mock_groups)

    # Call with pagination parameters
    result = await _handle_list_groups(mock_bridge, {"limit": 10, "offset": 5})

    # Verify
    mock_bridge.list_groups.assert_called_once_with(document_id=None, limit=10, offset=5)


@pytest.mark.asyncio
async def test_handle_list_groups_error():
    """Test list_groups handler error handling."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    mock_bridge.list_groups = AsyncMock(side_effect=Exception("Database error"))

    # Call handler
    result = await _handle_list_groups(mock_bridge, {"document_id": 1})

    # Verify error response
    response = json.loads(result[0].text)
    assert "error" in response
    assert "Database error" in response["error"]
    assert response["count"] == 0


# Tests for get_group_status


@pytest.mark.asyncio
async def test_handle_get_group_status_success():
    """Test get_group_status handler returns group info."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_group_info = {
        "id": str(group_id),
        "document_id": 1,
        "name": "API Documentation",
        "description": "API docs",
        "context_enabled": True,
        "context_model": "anthropic:claude-3-5-sonnet-20241022",
        "total_pages": 10,
        "total_chunks": 75,
        "combined_content_length": 125000,
        "processing_status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "statistics": {
            "total_chunks": 75,
            "total_content_length": 125000,
            "avg_chunk_size": 1666.67,
        },
    }

    mock_bridge.get_group_info = AsyncMock(return_value=mock_group_info)

    # Call handler
    result = await _handle_get_group_status(mock_bridge, {"group_id": str(group_id)})

    # Verify result
    assert len(result) == 1
    content = result[0]
    assert content.type == "text"

    response = json.loads(content.text)
    assert response["status"] == "success"
    assert "group_info" in response
    assert response["group_info"]["name"] == "API Documentation"
    assert response["group_info"]["total_chunks"] == 75
    mock_bridge.get_group_info.assert_called_once_with(str(group_id))


@pytest.mark.asyncio
async def test_handle_get_group_status_not_found():
    """Test get_group_status handler when group not found."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_bridge.get_group_info = AsyncMock(side_effect=ValueError(f"Group not found: {group_id}"))

    # Call handler
    result = await _handle_get_group_status(mock_bridge, {"group_id": str(group_id)})

    # Verify error response
    response = json.loads(result[0].text)
    assert "error" in response
    assert "not found" in response["error"].lower()
    assert response["status"] is None


@pytest.mark.asyncio
async def test_handle_get_group_status_invalid_uuid():
    """Test get_group_status handler with invalid UUID."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)

    mock_bridge.get_group_info = AsyncMock(
        side_effect=ValueError("Invalid group ID format: invalid-uuid")
    )

    # Call handler
    result = await _handle_get_group_status(mock_bridge, {"group_id": "invalid-uuid"})

    # Verify error response
    response = json.loads(result[0].text)
    assert "error" in response
    assert "invalid" in response["error"].lower()


@pytest.mark.asyncio
async def test_handle_get_group_status_missing_group_id():
    """Test get_group_status handler when group_id is missing."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)

    # Call handler without group_id
    result = await _handle_get_group_status(mock_bridge, {})

    # Verify error response
    response = json.loads(result[0].text)
    assert "error" in response
    assert "required" in response["error"].lower()


@pytest.mark.asyncio
async def test_handle_get_group_status_exception():
    """Test get_group_status handler exception handling."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_bridge.get_group_info = AsyncMock(side_effect=Exception("Unexpected database error"))

    # Call handler
    result = await _handle_get_group_status(mock_bridge, {"group_id": str(group_id)})

    # Verify error response
    response = json.loads(result[0].text)
    assert "error" in response
    assert "database" in response["error"].lower()


@pytest.mark.asyncio
async def test_handle_get_group_status_with_pending_status():
    """Test get_group_status handler for pending group."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_group_info = {
        "id": str(group_id),
        "document_id": 1,
        "name": "Pending Group",
        "description": "Still processing",
        "context_enabled": False,
        "context_model": None,
        "total_pages": 5,
        "total_chunks": 0,
        "combined_content_length": None,
        "processing_status": "processing",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processed_at": None,
        "statistics": {
            "total_chunks": 0,
            "total_content_length": 0,
            "avg_chunk_size": 0,
        },
    }

    mock_bridge.get_group_info = AsyncMock(return_value=mock_group_info)

    # Call handler
    result = await _handle_get_group_status(mock_bridge, {"group_id": str(group_id)})

    # Verify result
    response = json.loads(result[0].text)
    assert response["status"] == "success"
    assert response["group_info"]["processing_status"] == "processing"
    assert response["group_info"]["processed_at"] is None
    assert response["group_info"]["total_chunks"] == 0


@pytest.mark.asyncio
async def test_handle_list_groups_return_format():
    """Test list_groups returns properly formatted groups."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_groups = [
        {
            "id": str(group_id),
            "document_id": 1,
            "name": "Test Group",
            "description": "Test description",
            "context_enabled": True,
            "context_model": "anthropic:claude-3-5-sonnet-20241022",
            "total_pages": 5,
            "total_chunks": 25,
            "processing_status": "completed",
            "created_at": "2025-11-16T10:00:00+00:00",
            "processed_at": "2025-11-16T10:05:00+00:00",
        },
    ]

    mock_bridge.list_groups = AsyncMock(return_value=mock_groups)

    # Call handler
    result = await _handle_list_groups(mock_bridge, {"document_id": 1})

    # Verify format
    response = json.loads(result[0].text)
    group = response["groups"][0]

    # Verify all expected keys
    expected_keys = {
        "id",
        "document_id",
        "name",
        "description",
        "context_enabled",
        "context_model",
        "total_pages",
        "total_chunks",
        "processing_status",
        "created_at",
        "processed_at",
    }
    assert set(group.keys()) == expected_keys
