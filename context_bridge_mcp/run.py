"""
Simple runner for AgentMem MCP server.

Usage:
    python agent_mem_mcp/run.py
"""

import sys
import asyncio
from pathlib import Path


# Add parent directory to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import mcp.server.stdio
from context_bridge_mcp.server import server


async def main():
    """Run server with stdio transport."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    print("Starting AgentMem MCP server...", file=sys.stderr)
    asyncio.run(main())
