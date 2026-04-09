"""Unit tests for MCP server tools."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from context_bridge_mcp.server import (
    _handle_find_documents,
    _handle_search_content,
    handle_list_tools,
    handle_call_tool,
    server_lifespan,
)
from context_bridge_mcp.schemas import (
    FIND_DOCUMENTS_INPUT_SCHEMA,
    SEARCH_CONTENT_INPUT_SCHEMA,
)
from context_bridge import ContextBridge
from context_bridge.database.repositories.document_repository import Document
from context_bridge.service.search_service import ContentSearchResult
from context_bridge.database.repositories.chunk_repository import Chunk
import mcp.types as types


class TestMCPTools:
    """Test MCP tool implementations."""

    @pytest.fixture
    def mock_bridge(self):
        """Create a mock ContextBridge."""
        bridge = MagicMock(spec=ContextBridge)

        # Mock find_documents
        mock_doc = Document(
            id=1,
            name="test_doc",
            version="1.0.0",
            description="Test document",
            source_url="https://example.com",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        bridge.find_documents = AsyncMock(return_value=[mock_doc])

        # Mock search
        mock_chunk = Chunk(
            id=1,
            document_id=1,
            group_id=None,
            chunk_index=0,
            content="Test content with search terms",
            embedding=[0.1] * 768,
            created_at=MagicMock(),
        )
        mock_result = ContentSearchResult(
            chunk=mock_chunk,
            document_name="test_doc",
            document_version="1.0.0",
            document_source_url="https://example.com",
            score=0.85,
            rank=1,
        )
        bridge.search = AsyncMock(return_value=[mock_result])

        return bridge

    @pytest.fixture
    def mock_server_context(self, mock_bridge):
        """Create a mock server context."""
        return MagicMock(lifespan_context={"bridge": mock_bridge})

    @pytest.mark.asyncio
    async def test_handle_find_documents_basic(self, mock_bridge, mock_server_context):
        """Test find_documents with basic parameters."""
        # Mock the server context
        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            # Test basic call
            result = await _handle_find_documents(mock_bridge, {"query": "test", "limit": 10})

            assert len(result) == 1
            content = result[0]
            assert isinstance(content, types.TextContent)

            # Parse JSON response
            response_data = json.loads(content.text)
            assert "documents" in response_data
            assert "count" in response_data
            assert response_data["count"] == 1
            assert len(response_data["documents"]) == 1

            doc = response_data["documents"][0]
            assert doc["id"] == 1
            assert doc["name"] == "test_doc"
            assert doc["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_handle_find_documents_with_filters(self, mock_bridge, mock_server_context):
        """Test find_documents with name and version filters."""
        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await _handle_find_documents(
                mock_bridge, {"query": "test", "name": "test_doc", "version": "1.0.0", "limit": 5}
            )

            assert len(result) == 1
            response_data = json.loads(result[0].text)
            assert response_data["count"] == 1

    @pytest.mark.asyncio
    async def test_handle_search_content_basic(self, mock_bridge, mock_server_context):
        """Test search_content with basic parameters."""
        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await _handle_search_content(
                mock_bridge, {"query": "test search", "document_id": 1, "limit": 10}
            )

            assert len(result) == 1
            response_data = json.loads(result[0].text)
            assert "results" in response_data
            assert "count" in response_data
            assert "query" in response_data
            assert response_data["count"] == 1
            assert len(response_data["results"]) == 1

            search_result = response_data["results"][0]
            assert search_result["document_name"] == "test_doc"
            assert search_result["score"] == 0.85
            assert search_result["rank"] == 1

    @pytest.mark.asyncio
    async def test_handle_search_content_missing_document_id(
        self, mock_bridge, mock_server_context
    ):
        """Test search_content without required document_id."""
        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await _handle_search_content(
                mock_bridge, {"query": "test search", "limit": 10}
            )

            assert len(result) == 1
            response_data = json.loads(result[0].text)
            assert "error" in response_data
            assert "document_id is required" in response_data["error"]
            assert response_data["results"] == []
            assert response_data["count"] == 0

    @pytest.mark.asyncio
    async def test_handle_search_content_with_weights(self, mock_bridge, mock_server_context):
        """Test search_content with vector and BM25 weights."""
        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await _handle_search_content(
                mock_bridge,
                {
                    "query": "test search",
                    "document_id": 1,
                    "limit": 5,
                    "vector_weight": 0.7,
                    "bm25_weight": 0.3,
                },
            )

            assert len(result) == 1
            # Verify the weights were passed to the search method
            mock_bridge.search.assert_called_once_with(
                query="test search", document_id=1, limit=5, vector_weight=0.7, bm25_weight=0.3
            )

    @pytest.mark.asyncio
    async def test_handle_find_documents_error(self, mock_bridge, mock_server_context):
        """Test error handling in find_documents."""
        # Make find_documents raise an exception
        mock_bridge.find_documents.side_effect = Exception("Database error")

        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await _handle_find_documents(mock_bridge, {"limit": 10})

            assert len(result) == 1
            assert "Error executing find_documents" in result[0].text

    @pytest.mark.asyncio
    async def test_handle_search_content_error(self, mock_bridge, mock_server_context):
        """Test error handling in search_content."""
        # Make search raise an exception
        mock_bridge.search.side_effect = Exception("Search error")

        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await _handle_search_content(mock_bridge, {"query": "test", "document_id": 1})

            assert len(result) == 1
            assert "Error executing search_content" in result[0].text

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test tool discovery."""
        tools = await handle_list_tools()

        # Should have 2 tools: find_documents, search_content
        assert len(tools) == 2

        # Check find_documents tool
        find_tool = next(t for t in tools if t.name == "find_documents")
        assert find_tool.name == "find_documents"
        assert "Find documentation by name, version, or query" in find_tool.description
        assert find_tool.inputSchema == FIND_DOCUMENTS_INPUT_SCHEMA

        # Check search_content tool
        search_tool = next(t for t in tools if t.name == "search_content")
        assert search_tool.name == "search_content"
        assert (
            "Search documentation content with hybrid vector + BM25 search"
            in search_tool.description
        )
        assert search_tool.inputSchema == SEARCH_CONTENT_INPUT_SCHEMA

    @pytest.mark.asyncio
    async def test_call_tool_find_documents(self, mock_bridge, mock_server_context):
        """Test tool call dispatch for find_documents."""
        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await handle_call_tool("find_documents", {"query": "test", "limit": 10})

            assert len(result) == 1
            # Should have called our handler
            mock_bridge.find_documents.assert_called_once_with(query="test", limit=10)

    @pytest.mark.asyncio
    async def test_call_tool_search_content(self, mock_bridge, mock_server_context):
        """Test tool call dispatch for search_content."""
        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await handle_call_tool("search_content", {"query": "test", "document_id": 1})

            assert len(result) == 1
            # Should have called our handler
            mock_bridge.search.assert_called_once_with(
                query="test", document_id=1, limit=10, vector_weight=None, bm25_weight=None
            )

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self, mock_server_context):
        """Test calling unknown tool."""
        with patch("context_bridge_mcp.server.server") as mock_server:
            mock_server.request_context = mock_server_context

            result = await handle_call_tool("unknown_tool", {})

            assert len(result) == 1
            assert "Unknown tool: unknown_tool" in result[0].text

    @pytest.mark.asyncio
    async def test_server_lifespan(self):
        """Test server lifespan management."""
        from mcp.server.lowlevel import Server

        mock_server = MagicMock(spec=Server)

        # Test successful initialization
        with patch("context_bridge_mcp.server.ContextBridge") as mock_bridge_class:
            mock_bridge = MagicMock()
            mock_bridge.initialize = AsyncMock()
            mock_bridge.close = AsyncMock()
            mock_bridge_class.return_value = mock_bridge

            async with server_lifespan(mock_server) as context:
                assert "bridge" in context
                assert context["bridge"] is mock_bridge

            # Verify cleanup was called
            mock_bridge.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_server_lifespan_error(self):
        """Test server lifespan error handling."""
        from mcp.server.lowlevel import Server

        mock_server = MagicMock(spec=Server)

        # Test initialization error
        with patch("context_bridge_mcp.server.ContextBridge") as mock_bridge_class:
            mock_bridge = MagicMock()
            mock_bridge.initialize.side_effect = Exception("Init failed")
            mock_bridge.close = AsyncMock()
            mock_bridge_class.return_value = mock_bridge

            with pytest.raises(Exception, match="Init failed"):
                async with server_lifespan(mock_server):
                    pass
