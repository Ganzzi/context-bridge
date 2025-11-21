"""Unit tests for MCP reprocessing tool handlers."""

import json
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

from context_bridge_mcp.server import (
    _handle_reprocess_group,
    _handle_reprocess_multiple_groups,
)
from context_bridge import ContextBridge


@pytest.mark.asyncio
async def test_handle_reprocess_group_success():
    """Test reprocess_group handler with successful re-processing."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_result = {
        "success": True,
        "group_id": str(group_id),  # Convert to string for JSON serialization
        "chunks_created": 42,
        "processing_status": "COMPLETED",
    }

    mock_bridge.reprocess_group_with_context = AsyncMock(return_value=mock_result)

    # Execute
    arguments = {
        "group_id": str(group_id),
        "context_model": "anthropic:claude-3-5-sonnet-20241022",
    }
    result = await _handle_reprocess_group(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    assert result[0].type == "text"

    response = json.loads(result[0].text)
    assert response["status"] == "success"
    assert response["result"]["success"] is True
    assert response["result"]["chunks_created"] == 42


@pytest.mark.asyncio
async def test_handle_reprocess_group_missing_group_id():
    """Test reprocess_group handler with missing group_id."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)

    # Execute
    arguments = {"context_model": "anthropic:claude-3-5-sonnet-20241022"}
    result = await _handle_reprocess_group(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    response = json.loads(result[0].text)
    assert "error" in response
    assert response["status"] == "failed"


@pytest.mark.asyncio
async def test_handle_reprocess_group_error():
    """Test reprocess_group handler with error during re-processing."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    error_msg = "Group not found"
    mock_bridge.reprocess_group_with_context = AsyncMock(side_effect=ValueError(error_msg))

    # Execute
    arguments = {"group_id": str(group_id)}
    result = await _handle_reprocess_group(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    response = json.loads(result[0].text)
    assert "error" in response
    assert error_msg in response["error"]
    assert response["status"] == "failed"


@pytest.mark.asyncio
async def test_handle_reprocess_multiple_groups_success():
    """Test reprocess_multiple_groups handler with successful batch."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id_1 = uuid4()
    group_id_2 = uuid4()
    group_id_3 = uuid4()

    mock_result = {
        "success": True,
        "total_groups": 3,
        "successful": 3,
        "failed": 0,
        "results": [
            {
                "group_id": str(group_id_1),  # Convert to string
                "success": True,
                "chunks_created": 30,
            },
            {
                "group_id": str(group_id_2),  # Convert to string
                "success": True,
                "chunks_created": 42,
            },
            {
                "group_id": str(group_id_3),  # Convert to string
                "success": True,
                "chunks_created": 28,
            },
        ],
    }

    mock_bridge.reprocess_multiple_groups_with_context = AsyncMock(return_value=mock_result)

    # Execute
    arguments = {
        "group_ids": [str(group_id_1), str(group_id_2), str(group_id_3)],
        "context_model": "anthropic:claude-3-5-sonnet-20241022",
    }
    result = await _handle_reprocess_multiple_groups(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    assert result[0].type == "text"

    response = json.loads(result[0].text)
    assert response["status"] == "success"
    assert response["result"]["total_groups"] == 3
    assert response["result"]["successful"] == 3
    assert response["result"]["failed"] == 0


@pytest.mark.asyncio
async def test_handle_reprocess_multiple_groups_with_failures():
    """Test reprocess_multiple_groups handler with some failures."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id_1 = uuid4()
    group_id_2 = uuid4()

    mock_result = {
        "success": False,
        "total_groups": 2,
        "successful": 1,
        "failed": 1,
        "results": [
            {
                "group_id": str(group_id_1),  # Convert to string
                "success": True,
                "chunks_created": 30,
            },
            {
                "group_id": str(group_id_2),  # Convert to string
                "success": False,
                "chunks_created": 0,
                "error": "Group not found",
            },
        ],
    }

    mock_bridge.reprocess_multiple_groups_with_context = AsyncMock(return_value=mock_result)

    # Execute
    arguments = {
        "group_ids": [str(group_id_1), str(group_id_2)],
        "context_model": "openai:gpt-4o",
    }
    result = await _handle_reprocess_multiple_groups(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    response = json.loads(result[0].text)
    assert response["status"] == "success"
    assert response["result"]["total_groups"] == 2
    assert response["result"]["successful"] == 1
    assert response["result"]["failed"] == 1


@pytest.mark.asyncio
async def test_handle_reprocess_multiple_groups_missing_group_ids():
    """Test reprocess_multiple_groups handler with missing group_ids."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)

    # Execute
    arguments = {}
    result = await _handle_reprocess_multiple_groups(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    response = json.loads(result[0].text)
    assert "error" in response
    assert response["status"] == "failed"


@pytest.mark.asyncio
async def test_handle_reprocess_multiple_groups_empty_list():
    """Test reprocess_multiple_groups handler with empty group list."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)

    # Execute
    arguments = {"group_ids": []}
    result = await _handle_reprocess_multiple_groups(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    response = json.loads(result[0].text)
    assert "error" in response
    assert response["status"] == "failed"


@pytest.mark.asyncio
async def test_handle_reprocess_multiple_groups_error():
    """Test reprocess_multiple_groups handler with exception."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id_1 = uuid4()

    error_msg = "Database connection failed"
    mock_bridge.reprocess_multiple_groups_with_context = AsyncMock(side_effect=Exception(error_msg))

    # Execute
    arguments = {"group_ids": [str(group_id_1)]}
    result = await _handle_reprocess_multiple_groups(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    response = json.loads(result[0].text)
    assert "error" in response
    assert error_msg in response["error"]
    assert response["status"] == "failed"


@pytest.mark.asyncio
async def test_handle_reprocess_group_without_model():
    """Test reprocess_group handler without specifying context_model."""
    # Setup
    mock_bridge = AsyncMock(spec=ContextBridge)
    group_id = uuid4()

    mock_result = {
        "success": True,
        "group_id": group_id,
        "chunks_created": 25,
        "processing_status": "COMPLETED",
    }

    mock_bridge.reprocess_group_with_context = AsyncMock(return_value=mock_result)

    # Execute (no context_model provided)
    arguments = {"group_id": str(group_id)}
    result = await _handle_reprocess_group(mock_bridge, arguments)

    # Verify
    assert len(result) == 1
    response = json.loads(result[0].text)
    assert response["status"] == "success"

    # Verify the bridge was called with None for context_model
    mock_bridge.reprocess_group_with_context.assert_called_once()
    call_kwargs = mock_bridge.reprocess_group_with_context.call_args[1]
    assert call_kwargs["context_model"] is None
