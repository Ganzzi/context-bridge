# Context Bridge - MCP Server Usage Guide

**Version:** 1.1
**Date:** October 15, 2025

---

## 📋 Overview

The Context Bridge MCP (Model Context Protocol) server allows AI assistants like Claude Desktop to interact with the Context Bridge RAG system. This enables AI agents to search and retrieve documentation seamlessly.

---

## 🚀 Getting Started

### Prerequisites

- Context Bridge installed with MCP support
- PostgreSQL database with documents and chunks
- MCP-compatible AI client (Claude Desktop, etc.)

### Installation

```bash
# Install with MCP support
pip install context-bridge[mcp]

# Or install all features
pip install context-bridge[all]
```

### Running the Server

```bash
# Using the installed script
context-bridge-mcp

# Or run directly
python -m context_bridge_mcp

# For development
uv run python -m context_bridge_mcp
```

---

## 🛠️ Available Tools

The MCP server provides two main tools for AI agents:

### 1. `find_documents`

**Purpose:** Search for documents by query.

**Parameters:**
- `query` (required): Search term for document names/descriptions
- `limit` (optional): Maximum results (default: 10)

**Example Usage:**
```
Find me all Python-related documentation
Show me documents about machine learning
List all available documents
```

### 2. `search_content`

**Purpose:** Perform hybrid vector + BM25 search across document content.

**Parameters:**
- `query` (required): Search query
- `document_id` (required): Limit search to specific document
- `limit` (optional): Maximum results (default: 10)
- `vector_weight` (optional): Vector similarity weight (default: 0.7)
- `bm25_weight` (optional): BM25 keyword weight (default: 0.3)

**Example Usage:**
```
How do I use async functions in Python?
Find examples of error handling
Search for database connection code
```

---

## 🔌 Integration with AI Clients

### Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "context-bridge": {
      "command": "context-bridge-mcp"
    }
  }
}
```

### Other MCP Clients

The server uses stdio transport, compatible with any MCP client that supports stdio connections.

---

## 💡 Usage Examples

### Finding Documentation

**User:** "What Python documentation do you have available?"

**AI Agent internally:**
- Calls `find_documents` tool
- Receives list of Python documents with metadata
- Presents results to user

### Content Search

**User:** "How do I handle exceptions in Python asyncio?"

**AI Agent internally:**
- Calls `search_content` with query "exception handling asyncio"
- Receives relevant chunks with scores
- Synthesizes answer from top results

### Version-Specific Search

**User:** "Show me the Python 3.11 documentation for context managers"

**AI Agent internally:**
- Calls `find_documents` to get Python 3.11 document ID
- Calls `search_content` with document_id and query "context managers"
- Returns focused results

---

## 📊 Response Format

### Document Search Results

```json
{
  "documents": [
    {
      "id": 1,
      "name": "Python Documentation",
      "version": "3.11",
      "description": "Official Python 3.11 documentation",
      "source_url": "https://docs.python.org/3/",
      "created_at": "2025-10-14T10:30:00Z"
    }
  ],
  "count": 1
}
```

### Content Search Results

```json
{
  "results": [
    {
      "document_name": "Python Documentation",
      "document_version": "3.11",
      "chunk_content": "Exception handling in asyncio...",
      "score": 0.87,
      "rank": 1
    }
  ],
  "count": 1,
  "query": "exception handling asyncio",
  "document_id": 1
}
```

---

## ⚙️ Configuration

The MCP server uses the same environment variables as Context Bridge:

```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=context_bridge

# Embedding Configuration
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
VECTOR_DIMENSION=768

# Search Configuration
SIMILARITY_THRESHOLD=0.7
BM25_WEIGHT=0.3
VECTOR_WEIGHT=0.7
```

---

## 🔧 Troubleshooting

### Server Won't Start
- Check database connectivity
- Verify environment variables
- Ensure required Python packages are installed

### No Search Results
- Confirm documents are chunked and embedded
- Check embedding service is running (Ollama)
- Verify search query is relevant

### Connection Issues
- Check MCP client configuration
- Verify server is running on expected port
- Check firewall settings

### Performance Issues
- Large result limits can slow responses
- Complex queries may take longer
- Database indexing affects search speed

---

## 📈 Best Practices

### Query Formulation
- Use specific, descriptive queries
- Include relevant technical terms
- Consider both semantic and keyword aspects

### Result Interpretation
- Higher scores indicate better matches
- Check document versions for accuracy
- Use page URLs for full context

### Error Handling
- Server errors are communicated clearly
- Invalid parameters return helpful messages
- Network issues trigger automatic retries

---

## 🔒 Security Considerations

- The MCP server runs locally by default
- Database credentials should be protected
- No external network access required
- All communication happens via stdio

---

## 📞 Support

For issues with the MCP server:
- Check server logs for error messages
- Verify database and embedding service status
- Test with simple queries first
- Review configuration settings

---

**Last Updated:** October 15, 2025</content>
<parameter name="filePath">z:\code\ctx_bridge\docs\MCP_SERVER_USAGE.md