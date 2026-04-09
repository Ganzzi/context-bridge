"""Integration tests for MCP server with real database connections."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from context_bridge_mcp.server import (
    _handle_find_documents,
    _handle_search_content,
    handle_list_tools,
)
from context_bridge import ContextBridge
from context_bridge.database.repositories.document_repository import Document
from context_bridge.service.search_service import ContentSearchResult
from context_bridge.database.repositories.chunk_repository import Chunk
import mcp.types as types
from datetime import datetime, timezone


@pytest.fixture
async def real_bridge():
    """Create a real ContextBridge instance for integration testing."""
    bridge = ContextBridge()
    await bridge.initialize()

    yield bridge

    # Cleanup
    await bridge.close()


class TestMCPIntegration:
    """Integration tests for MCP server with real database."""

    @pytest.mark.asyncio
    async def test_list_tools_integration(self):
        """Test tool discovery in integration context."""
        tools = await handle_list_tools()

        assert len(tools) == 2

        # Check find_documents tool
        find_tool = next(t for t in tools if t.name == "find_documents")
        assert find_tool.name == "find_documents"
        assert "Find documentation by name, version, or query" in find_tool.description

        # Check search_content tool
        search_tool = next(t for t in tools if t.name == "search_content")
        assert search_tool.name == "search_content"
        assert (
            "Search documentation content with hybrid vector + BM25 search"
            in search_tool.description
        )

    @pytest.mark.asyncio
    async def test_handle_find_documents_real_bridge(self, real_bridge):
        """Test find_documents handler with real database connection."""
        result = await _handle_find_documents(real_bridge, {"limit": 10})

        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "documents" in response_data
        assert "count" in response_data
        assert isinstance(response_data["documents"], list)
        assert isinstance(response_data["count"], int)

    @pytest.mark.asyncio
    async def test_handle_search_content_missing_document_id_real_bridge(self, real_bridge):
        """Test search_content handler with missing document_id using real bridge."""
        result = await _handle_search_content(real_bridge, {"query": "test"})

        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "document_id is required" in response_data["error"]
        assert response_data["results"] == []
        assert response_data["count"] == 0

    @pytest.mark.asyncio
    async def test_handle_search_content_invalid_document_id_real_bridge(self, real_bridge):
        """Test search_content handler with invalid document_id using real bridge."""
        result = await _handle_search_content(real_bridge, {"query": "test", "document_id": 99999})

        assert len(result) == 1
        response_data = json.loads(result[0].text)
        # Should return empty results for non-existent document
        assert "results" in response_data
        assert "count" in response_data
        assert response_data["count"] == 0
        assert len(response_data["results"]) == 0

    @pytest.mark.asyncio
    async def test_concurrent_handlers(self, real_bridge):
        """Test concurrent execution of multiple handlers."""
        # Create multiple concurrent calls
        tasks = []
        for i in range(5):
            if i % 2 == 0:
                task = _handle_find_documents(real_bridge, {"limit": 10})
            else:
                task = _handle_search_content(real_bridge, {"query": f"test{i}", "document_id": 1})
            tasks.append(task)

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all completed without exceptions
        for result in results:
            assert not isinstance(result, Exception)
            assert len(result) == 1
            assert isinstance(result[0], types.TextContent)

    @pytest.mark.asyncio
    async def test_parameter_validation_real_bridge(self, real_bridge):
        """Test parameter validation with real bridge."""
        # Test find_documents with various parameters
        result = await _handle_find_documents(real_bridge, {"limit": 100})
        assert len(result) == 1

        result = await _handle_find_documents(real_bridge, {"name": "nonexistent"})
        assert len(result) == 1

        result = await _handle_find_documents(real_bridge, {"version": "1.0.0"})
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_error_handling_real_bridge(self, real_bridge):
        """Test error handling with real bridge."""
        # Test with invalid parameters that might cause issues
        result = await _handle_search_content(
            real_bridge, {"query": "", "document_id": 1}  # Empty query
        )
        # Should handle gracefully
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_large_result_handling_real_bridge(self, real_bridge):
        """Test handling of potentially large result sets with real bridge."""
        # Test with large limit
        result = await _handle_find_documents(real_bridge, {"limit": 1000})

        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "documents" in response_data
        assert "count" in response_data
        # Should handle large limits gracefully

    @pytest.mark.asyncio
    async def test_search_with_weights_real_bridge(self, real_bridge):
        """Test search with custom weights using real bridge."""
        result = await _handle_search_content(
            real_bridge,
            {
                "query": "test",
                "document_id": 1,
                "limit": 5,
                "vector_weight": 0.8,
                "bm25_weight": 0.2,
            },
        )

        assert len(result) == 1
        response_data = json.loads(result[0].text)
        # Should handle weights gracefully even with no data
        assert "results" in response_data
        assert "count" in response_data
