# Creating an MCP Server with Python

This guide provides a focused walkthrough on creating an MCP server using the Python SDK. We'll cover the essential concepts to get you up and running, with a focus on advanced server configurations, tools, structured output, context, and running your server.

## Table of Contents

- [Installation](#installation)
- [Server](#server)
  - [FastMCP Server](#fastmcp-server)
  - [Low-Level Server (Advanced)](#low-level-server-advanced)
- [Tools](#tools)
- [Structured Output](#structured-output)
- [Context](#context)
- [Running Your Server](#running-your-server)
  - [Development Mode](#development-mode)
  - [Direct Execution](#direct-execution)
  - [Streamable HTTP Transport](#streamable-http-transport)
  - [SSE servers](#sse-servers)

## Installation

First, you need to add the MCP SDK to your Python project. We recommend using `uv` for project management.

If you don't have a `uv`-managed project, create one:
```bash
uv init mcp-server-demo
cd mcp-server-demo
```

Then, add `mcp` as a dependency:
```bash
uv add "mcp[cli]"
```

Alternatively, if you are using `pip`:
```bash
pip install "mcp[cli]"
```

## Server

### FastMCP Server

The `FastMCP` server is the high-level interface for the MCP protocol. It handles connection management, protocol compliance, and message routing.

Here's a basic example of a `FastMCP` server:

```python
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Demo")

# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b
```

### Low-Level Server (Advanced)

For more control, you can use the low-level server implementation directly. This gives you full access to the protocol and allows you to customize every aspect of your server, including lifecycle management through the `lifespan` API.

The `lifespan` API provides:
- A way to initialize resources when the server starts and clean them up when it stops.
- Access to initialized resources through the request context in handlers.
- Type-safe context passing between `lifespan` and request handlers.

Here is an example of a low-level server with `lifespan` management:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# Mock database class for example
class Database:
    """Mock database class for example."""

    @classmethod
    async def connect(cls) -> "Database":
        """Connect to database."""
        print("Database connected")
        return cls()

    async def disconnect(self) -> None:
        """Disconnect from database."""
        print("Database disconnected")

    async def query(self, query_str: str) -> list[dict[str, str]]:
        """Execute a query."""
        # Simulate database query
        return [{"id": "1", "name": "Example", "query": query_str}]


@asynccontextmanager
async def server_lifespan(_server: Server) -> AsyncIterator[dict[str, Any]]:
    """Manage server startup and shutdown lifecycle."""
    # Initialize resources on startup
    db = await Database.connect()
    try:
        yield {"db": db}
    finally:
        # Clean up on shutdown
        await db.disconnect()


# Pass lifespan to server
server = Server("example-server", lifespan=server_lifespan)

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="query_db",
            description="Query the database",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "SQL query to execute"}},
                "required": ["query"],
            },
        )
    ]

@server.call_tool()
async def query_db(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle database query tool call."""
    if name != "query_db":
        raise ValueError(f"Unknown tool: {name}")

    # Access lifespan context
    ctx = server.request_context
    db = ctx.lifespan_context["db"]

    # Execute query
    results = await db.query(arguments["query"])

    return [types.TextContent(type="text", text=f"Query results: {results}")]
```

## Tools

Tools allow LLMs to take actions through your server. They can perform computations and have side effects.

Here's how to define a tool:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="Tool Example")

@mcp.tool()
def sum(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

@mcp.tool()
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get weather for a city."""
    # This would normally call a weather API
    return f"Weather in {city}: 22 degrees {unit[0].upper()}"
```

## Structured Output

Tools can return structured results, which are automatically validated against an output schema. This is the default behavior if the return type annotation is compatible.

Supported return types for structured output include:
- Pydantic models (`BaseModel` subclasses)
- `TypedDict`s
- Dataclasses and other classes with type hints
- `dict[str, T]` (where `T` is any JSON-serializable type)
- Primitive types (`str`, `int`, `float`, `bool`, `bytes`, `None`) - wrapped in `{"result": value}`
- Generic types (`list`, `tuple`, `Union`, `Optional`, etc.) - wrapped in `{"result": value}`

Here's an example of a tool that returns a Pydantic model:

```python
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Structured Output Example")

# Using Pydantic models for rich structured data
class WeatherData(BaseModel):
    """Weather information structure."""

    temperature: float = Field(description="Temperature in Celsius")
    humidity: float = Field(description="Humidity percentage")
    condition: str
    wind_speed: float

@mcp.tool()
def get_weather(city: str) -> WeatherData:
    """Get weather for a city - returns structured data."""
    # Simulated weather data
    return WeatherData(
        temperature=22.5,
        humidity=45.0,
        condition="sunny",
        wind_speed=5.2,
    )
```

The low-level server also supports structured output. You can define an `outputSchema` for a tool, and the server will validate the output.

```python
from typing import Any
import mcp.types as types
from mcp.server.lowlevel import Server

server = Server("example-server")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools with structured output schemas."""
    return [
        types.Tool(
            name="get_weather",
            description="Get current weather for a city",
            inputSchema={
                "type": "object",
                "properties": {"city": {"type": "string", "description": "City name"}},
                "required": ["city"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "description": "Temperature in Celsius"},
                    "condition": {"type": "string", "description": "Weather condition"},
                    "humidity": {"type": "number", "description": "Humidity percentage"},
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["temperature", "condition", "humidity", "city"],
            },
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle tool calls with structured output."""
    if name == "get_weather":
        city = arguments["city"]

        # Simulated weather data
        weather_data = {
            "temperature": 22.5,
            "condition": "partly cloudy",
            "humidity": 65,
            "city": city,
        }
        return weather_data
    else:
        raise ValueError(f"Unknown tool: {name}")
```

## Context

The `Context` object is automatically injected into tool and resource functions that request it via type hints. It provides access to MCP capabilities like logging, progress reporting, and more.

To use the context, add a parameter with the `Context` type annotation to your tool function:

```python
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

mcp = FastMCP(name="Context Example")

@mcp.tool()
async def long_running_task(task_name: str, ctx: Context[ServerSession, None], steps: int = 5) -> str:
    """Execute a task with progress updates."""
    await ctx.info(f"Starting: {task_name}")

    for i in range(steps):
        progress = (i + 1) / steps
        await ctx.report_progress(
            progress=progress,
            total=1.0,
            message=f"Step {i + 1}/{steps}",
        )
        await ctx.debug(f"Completed step {i + 1}")

    return f"Task '{task_name}' completed"
```

The `Context` object provides the following capabilities:
- `ctx.request_id`: Unique ID for the current request.
- `ctx.client_id`: Client ID if available.
- `ctx.fastmcp`: Access to the `FastMCP` server instance.
- `ctx.session`: Access to the underlying session for advanced communication.
- `ctx.request_context`: Access to request-specific data and lifespan resources.
- `await ctx.debug(message)`: Send a debug log message.
- `await ctx.info(message)`: Send an info log message.
- `await ctx.warning(message)`: Send a warning log message.
- `await ctx.error(message)`: Send an error log message.
- `await ctx.log(level, message, logger_name=None)`: Send a log with a custom level.
- `await ctx.report_progress(progress, total=None, message=None)`: Report operation progress.
- `await ctx.read_resource(uri)`: Read a resource by URI.
- `await ctx.elicit(message, schema)`: Request additional information from the user with validation.

## Running Your Server

### Development Mode

The fastest way to test and debug your server is with the MCP Inspector:

```bash
uv run mcp dev server.py
```

### Direct Execution

For advanced scenarios like custom deployments, you can run the server directly:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My App")

@mcp.tool()
def hello(name: str = "World") -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()
```

You can run this script with:
```bash
python server.py
```
or
```bash
uv run mcp run server.py
```

### Streamable HTTP Transport

For production deployments, the Streamable HTTP transport is recommended.

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("StatefulServer")

@mcp.tool()
def greet(name: str = "World") -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

You can also mount your MCP server to an existing ASGI server, like Starlette:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("My App")

@mcp.tool()
def hello() -> str:
    """A simple hello tool"""
    return "Hello from MCP!"

# Mount the StreamableHTTP server to the existing ASGI server
app = Starlette(
    routes=[
        Mount("/", app=mcp.streamable_http_app()),
    ]
)
```


### SSE servers

> **Note**: SSE transport is being superseded by [Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http).

You can mount the SSE server to an existing ASGI server using the `sse_app` method. This allows you to integrate the SSE server with other ASGI applications.

```python
from starlette.applications import Starlette
from starlette.routing import Mount, Host
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("My App")

# Mount the SSE server to the existing ASGI server
app = Starlette(
    routes=[
        Mount('/', app=mcp.sse_app()),
    ]
)

# or dynamically mount as host
app.router.routes.append(Host('mcp.acme.corp', app=mcp.sse_app()))
```

When mounting multiple MCP servers under different paths, you can configure the mount path in several ways:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp.server.fastmcp import FastMCP

# Create multiple MCP servers
github_mcp = FastMCP("GitHub API")
browser_mcp = FastMCP("Browser")
curl_mcp = FastMCP("Curl")
search_mcp = FastMCP("Search")

# Method 1: Configure mount paths via settings (recommended for persistent configuration)
github_mcp.settings.mount_path = "/github"
browser_mcp.settings.mount_path = "/browser"

# Method 2: Pass mount path directly to sse_app (preferred for ad-hoc mounting)
# This approach doesn't modify the server's settings permanently

# Create Starlette app with multiple mounted servers
app = Starlette(
    routes=[
        # Using settings-based configuration
        Mount("/github", app=github_mcp.sse_app()),
        Mount("/browser", app=browser_mcp.sse_app()),
        # Using direct mount path parameter
        Mount("/curl", app=curl_mcp.sse_app("/curl")),
        Mount("/search", app=search_mcp.sse_app("/search")),
    ]
)

# Method 3: For direct execution, you can also pass the mount path to run()
if __name__ == "__main__":
    search_mcp.run(transport="sse", mount_path="/search")
```

For more information on mounting applications in Starlette, see the [Starlette documentation](https://www.starlette.io/routing/#submounting-routes).
