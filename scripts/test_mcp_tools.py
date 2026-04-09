#!/usr/bin/env python
"""Test script to verify MCP tools are properly registered."""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_bridge_mcp.server import handle_list_tools


async def main():
    """Test that all MCP tools are properly registered."""
    print("Testing MCP Tool Registration...\n")

    try:
        # Get list of tools
        tools = await handle_list_tools()

        print(f"✓ Found {len(tools)} registered tools\n")

        # Verify all expected tools are present
        expected_tools = {
            "find_documents",
            "search_content",
            "list_tags",
            "add_document_tags",
            "remove_tag_from_document",
        }

        registered_names = {tool.name for tool in tools}

        print("Registered Tools:")
        for tool in tools:
            print(f"  • {tool.name}: {tool.description[:60]}...")

        print(f"\nExpected: {expected_tools}")
        print(f"Registered: {registered_names}")

        missing = expected_tools - registered_names
        if missing:
            print(f"❌ Missing tools: {missing}")
            return 1

        extra = registered_names - expected_tools
        if extra:
            print(f"⚠ Extra tools: {extra}")

        print("\n✓ All expected tools are registered!")

        # Verify tag tool input schemas
        print("\n\nTag Tool Input Schemas:")
        tag_tools = [t for t in tools if "tag" in t.name.lower()]
        for tool in tag_tools:
            print(f"\n{tool.name}:")
            print(f"  Schema: {json.dumps(tool.inputSchema, indent=2)}")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
