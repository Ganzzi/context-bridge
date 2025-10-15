"""MCP Server implementation for Context Bridge."""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, AsyncIterator

from mcp.server.lowlevel import Server
import mcp.types as types

from context_bridge import ContextBridge
from context_bridge_mcp.schemas import (
    FIND_DOCUMENTS_INPUT_SCHEMA,
    SEARCH_CONTENT_INPUT_SCHEMA,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("context_bridge_mcp")


@asynccontextmanager
async def server_lifespan(_server: Server) -> AsyncIterator[dict[str, Any]]:
    """
    Manage server lifecycle - initialize ContextBridge on startup.

    This creates a singleton ContextBridge instance that's shared across
    all tool calls, maintaining database connections efficiently.
    """
    logger.info("Starting Context Bridge MCP server...")

    # Startup: Initialize ContextBridge with configuration
    try:
        bridge = ContextBridge()
        logger.info("Initializing ContextBridge instance...")
        await bridge.initialize()
        logger.info("ContextBridge initialized successfully")
        logger.info("MCP server ready to accept requests")

        yield {"bridge": bridge}
    except Exception as e:
        logger.error(f"Failed to initialize ContextBridge: {e}", exc_info=True)
        raise
    finally:
        # Cleanup: Close database connections
        logger.info("Shutting down MCP server...")
        if "bridge" in locals():
            await bridge.close()
        logger.info("MCP server shutdown complete")


# Create MCP server with lifespan management
server = Server("context-bridge-mcp", lifespan=server_lifespan)


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available documentation management tools."""
    return [
        types.Tool(
            name="find_documents",
            description=(
                "Find documentation by name, version, or query. "
                "Search through available documentation sources to locate specific documents "
                "or browse all available documentation. Supports filtering by name and version."
            ),
            inputSchema=FIND_DOCUMENTS_INPUT_SCHEMA,
        ),
        types.Tool(
            name="search_content",
            description=(
                "Search documentation content with hybrid vector + BM25 search. "
                "Perform intelligent search across all processed documentation content using "
                "a combination of vector similarity and BM25 text matching. Requires a document_id "
                "to limit search scope. Returns relevant chunks with context and relevance scores."
            ),
            inputSchema=SEARCH_CONTENT_INPUT_SCHEMA,
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls by routing to appropriate handler."""
    logger.info(f"Received tool call: {name}")
    logger.debug(f"Arguments: {arguments}")

    # Access ContextBridge from lifespan context
    ctx = server.request_context
    bridge: ContextBridge = ctx.lifespan_context["bridge"]

    try:
        if name == "find_documents":
            result = await _handle_find_documents(bridge, arguments)
            logger.info(f"Successfully executed {name}")
            return result
        elif name == "search_content":
            result = await _handle_search_content(bridge, arguments)
            logger.info(f"Successfully executed {name}")
            return result
        else:
            logger.error(f"Unknown tool requested: {name}")
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Error executing {name}: {e}", exc_info=True)
        # Return error as text content
        return [
            types.TextContent(
                type="text",
                text=f"Error executing {name}: {str(e)}",
            )
        ]


async def _handle_find_documents(
    bridge: ContextBridge, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Handle find_documents tool call."""
    try:
        # Extract parameters from arguments
        query = arguments["query"]
        limit = arguments.get("limit", 10)

        # Get documents
        documents = await bridge.find_documents(query=query, limit=limit)

        # Format response
        if not documents:
            response = {
                "documents": [],
                "count": 0,
                "message": "No documents found matching the criteria",
            }
        else:
            response = {
                "documents": [
                    {
                        "id": doc.id,
                        "name": doc.name,
                        "version": doc.version,
                        "description": doc.description,
                        "source_url": doc.source_url or "",
                        "total_pages": 0,  # TODO: Get actual page count
                        "total_chunks": 0,  # TODO: Get actual chunk count
                        "created_at": doc.created_at.isoformat(),
                    }
                    for doc in documents
                ],
                "count": len(documents),
            }

        import json

        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]
    except Exception as e:
        logger.error(f"Error executing find_documents: {e}", exc_info=True)
        error_response = {
            "error": f"Error executing find_documents: {str(e)}",
            "documents": [],
            "count": 0,
        }
        import json

        return [types.TextContent(type="text", text=json.dumps(error_response, indent=2))]


async def _handle_search_content(
    bridge: ContextBridge, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Handle search_content tool call."""
    try:
        query = arguments["query"]
        document_id = arguments.get("document_id")
        limit = arguments.get("limit", 10)
        vector_weight = arguments.get("vector_weight")
        bm25_weight = arguments.get("bm25_weight")

        if document_id is None:
            response = {
                "error": "document_id is required for content search",
                "results": [],
                "count": 0,
            }
        else:
            # Perform search
            search_results = await bridge.search(
                query=query,
                document_id=document_id,
                limit=limit,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
            )

            if not search_results:
                response = {
                    "results": [],
                    "count": 0,
                    "message": "No search results found",
                    "query": query,
                    "document_id": document_id,
                }
            else:
                response = {
                    "results": [
                        {
                            "document_name": item.document_name,
                            "document_version": item.document_version,
                            "chunk_content": item.chunk.content,
                            "score": item.score,
                            "rank": item.rank,
                        }
                        for item in search_results
                    ],
                    "count": len(search_results),
                    "query": query,
                    "document_id": document_id,
                }

        import json

        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]
    except Exception as e:
        logger.error(f"Error executing search_content: {e}", exc_info=True)
        error_response = {
            "error": f"Error executing search_content: {str(e)}",
            "results": [],
            "count": 0,
        }
        import json

        return [types.TextContent(type="text", text=json.dumps(error_response, indent=2))]
