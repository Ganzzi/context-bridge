"""CLI entry point for Context Bridge MCP Server."""

import asyncio
import mcp.server.stdio
from context_bridge_mcp.server import server


async def main():
    """Run server with stdio transport."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
