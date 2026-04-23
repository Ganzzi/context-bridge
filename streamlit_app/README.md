# Context Bridge - Streamlit UI

> **Note:** This Streamlit app is provided for demo/debugging purposes and is **not actively maintained**. It may not reflect the latest API changes in the core `context_bridge` package. Use at your own risk.

**Version:** 0.1.0
**Last Updated:** October 13, 2025

A web-based interface for managing documentation in the Context Bridge RAG (Retrieval-Augmented Generation) system.

---

## 📋 Overview

The Context Bridge Streamlit UI provides an intuitive web interface for:

- **Document Management**: Crawl, view, and manage documentation sources
- **Page Management**: Select and process pages for chunking and embedding
- **Search Interface**: Search across all documentation with hybrid vector + BM25 search
- **Real-time Feedback**: Progress indicators, status updates, and error handling

---

## ✨ Features

### 🌉 Home Page
- Welcome message and navigation guide
- System status indicator
- Quick statistics (when available)

### 📚 Document Management
- **List All Documents**: View all documentation with filtering and pagination
- **Crawl New Documentation**: Add new documentation by URL
- **Document Details**: View metadata, page counts, and quick actions
- **Delete Documents**: Remove documentation with confirmation dialogs
- **Search & Filter**: Find documents by name or version

### 📄 Page Management
- **View Pages**: See all crawled pages for a document
- **Select Pages**: Multi-select pages for processing
- **Chunk Processing**: Convert pages to chunks for embedding
- **Status Tracking**: Monitor which pages have been processed
- **Page Details**: View content previews and chunk information

### 🔍 Search Interface
- **Hybrid Search**: Vector similarity + BM25 keyword matching
- **Document Filtering**: Search within specific documents
- **Advanced Options**: Adjust search weights and result limits
- **Result Highlighting**: Query terms highlighted in results
- **Search History**: Quick access to recent searches
- **Pagination**: Handle large result sets efficiently

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- PostgreSQL database with pgvector extension
- Ollama running locally (for embeddings)
- Context Bridge core library installed

### Installation

1. **Install Context Bridge with UI dependencies:**

```bash
# Using uv (recommended)
uv pip install -e ".[ui]"

# Or using pip
pip install -e ".[ui]"
```

2. **Set up environment variables:**

Create a `.env` file in the project root:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=context_bridge
DB_USER=your_username
DB_PASSWORD=your_password

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text

# Optional: Logging
LOG_LEVEL=INFO
```

3. **Initialize the database:**

```bash
# Run database initialization
uv run python -m context_bridge.database.init_databases
```

### Running the App

**Start the Streamlit app:**

```bash
# Using uv
uv run streamlit run streamlit_app/app.py

# Or using streamlit directly
streamlit run streamlit_app/app.py
```

The app will be available at `http://localhost:8501`

**Custom port:**

```bash
uv run streamlit run streamlit_app/app.py --server.port 8502
```

**Headless mode (for servers):**

```bash
uv run streamlit run streamlit_app/app.py --server.headless true
```

---

## 📖 Usage Guide

### Crawling New Documentation

1. Navigate to **Documents** page
2. Click **"Crawl New"** tab
3. Fill in the form:
   - **Document Name**: Unique identifier (e.g., "psqlpy")
   - **Version**: Version number (e.g., "0.9.0")
   - **Source URL**: Starting URL for crawler
   - **Description**: Optional description
   - **Max Crawl Depth**: How deep to follow links (1-10)
4. Click **"🚀 Start Crawling"**
5. Wait for crawl to complete (progress bar shows status)
6. View results and click **"View Pages"** to see crawled content

### Processing Pages

1. Navigate to **Crawled Pages** page
2. Select a document from dropdown
3. Check boxes next to pages you want to process
4. Use **"Select All"** or **"Clear All"** for bulk actions
5. Review selection summary (count and total size)
6. Click **"Process Selected Pages"**
7. Wait for chunking to complete
8. Pages will be marked as "chunked" when done

### Searching Documentation

1. Navigate to **Search** page
2. Enter your search query
3. (Optional) Select specific document to search in
4. (Optional) Expand **Advanced Options** to adjust:
   - **Result Limit**: Number of results (1-50)
   - **Vector Weight**: Importance of semantic similarity (0-1)
   - **BM25 Weight**: Importance of keyword matching (0-1)
5. Click **"🔍 Search"**
6. Browse results with rank and relevance scores
7. Click **"View Full Page"** to see original content
8. Use pagination for large result sets

---

## 🎨 UI Customization

### Theme Configuration

The app uses a custom theme defined in `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#3498db"        # Blue buttons and accents
backgroundColor = "#f8f9fa"      # Light gray background
secondaryBackgroundColor = "#e9ecef"  # Slightly darker gray
textColor = "#2c3e50"           # Dark blue-gray text
font = "sans serif"
```

**To customize:**

1. Edit `.streamlit/config.toml`
2. Restart the Streamlit app
3. Changes apply immediately

### Custom CSS

Additional styling is provided in `streamlit_app/utils/ui_helpers.py`:

- Card styling with shadows
- Button hover effects
- Custom message boxes (success/error/info)
- Enhanced metrics and DataFrames
- Loading spinner customization

---

## 🛠️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_HOST` | Yes | `localhost` | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_NAME` | Yes | `context_bridge` | Database name |
| `DB_USER` | Yes | - | Database user |
| `DB_PASSWORD` | Yes | - | Database password |
| `OLLAMA_BASE_URL` | Yes | `http://localhost:11434` | Ollama API URL |
| `EMBEDDING_MODEL` | Yes | `nomic-embed-text` | Embedding model name |
| `LOG_LEVEL` | No | `INFO` | Logging level |

### Streamlit Configuration

**Server settings** (`.streamlit/config.toml`):

```toml
[server]
maxUploadSize = 10              # Max upload size in MB
enableCORS = false               # CORS for security
enableXsrfProtection = true      # CSRF protection

[browser]
gatherUsageStats = false         # Disable usage stats
```

---

## 🧪 Testing

### Manual Testing

Use the comprehensive testing checklist:

```bash
# Open the manual testing guide
cat docs/STREAMLIT_MANUAL_TESTING.md
```

The checklist includes 100+ test scenarios covering:
- Navigation and layout
- Document management workflows
- Page management workflows
- Search interface functionality
- UI/UX elements
- Performance benchmarks
- Error handling
- Accessibility
- Cross-browser compatibility

### Automated Testing

**End-to-end tests with Playwright:**

```bash
# Install Playwright browsers
uv run playwright install chromium

# Run all e2e tests
uv run pytest tests/e2e/ -v

# Run specific test class
uv run pytest tests/e2e/test_streamlit_ui.py::TestNavigationAndHome -v

# Run without slow tests
uv run pytest tests/e2e/ -v -m "not slow"
```

---

## 🚨 Error Handling

The app includes comprehensive error handling:

### Database Connection Errors
- Automatic detection of connection issues
- Clear error messages with retry options
- Connection status indicator in sidebar

### Validation Errors
- Real-time input validation
- Field-level error messages
- Form submission prevention until valid

### Network Errors
- Timeout handling for long operations
- Retry mechanisms for failed requests
- Graceful degradation

### User-Friendly Messages
All errors are displayed with:
- 🔴 Clear error descriptions
- 💡 Suggested solutions
- 🔍 Technical details (expandable)
- 🔄 Retry buttons where applicable

---

## ⚡ Performance Optimization

### Caching

The app implements multi-level caching:

**Session Cache** (in-memory):
- Document lists cached for 5 minutes
- Search results cached for 1 minute
- Automatic cache invalidation on updates

**Streamlit Cache** (`@st.cache_data`):
- Pure function results cached
- Automatic TTL (time-to-live) management
- Cache clearing utilities

**Manual Cache Management:**

```python
from utils.caching import CacheManager

# Invalidate specific cache
CacheManager.invalidate(key="documents_list")

# Invalidate by prefix
CacheManager.invalidate(prefix="documents")

# Clear all cache
CacheManager.invalidate()

# Cleanup expired entries
CacheManager.cleanup_expired()
```

### Lazy Loading

- Pagination for large datasets
- On-demand loading of page content
- Progressive rendering of search results

### Optimization Tips

1. **Use filters** to reduce data loaded
2. **Adjust page size** in document lists
3. **Enable caching** for repeated operations
4. **Clear cache** periodically if data changes frequently

---

## 📁 Project Structure

```
streamlit_app/
├── app.py                  # Main entry point and home page
├── pages/
│   ├── documents.py        # Document management
│   ├── crawled_pages.py    # Page management
│   └── search.py           # Search interface
├── components/
│   ├── crawl_form.py       # Crawl form component
│   └── search_results.py   # Search results display
└── utils/
    ├── session_state.py    # Session state management
    ├── formatters.py       # Data formatting helpers
    ├── ui_helpers.py       # UI styling and error handling
    └── caching.py          # Caching utilities

.streamlit/
└── config.toml            # Theme and server configuration

tests/
└── e2e/
    ├── conftest.py        # Playwright fixtures
    └── test_streamlit_ui.py  # Browser tests

docs/
├── STREAMLIT_MANUAL_TESTING.md  # Testing checklist
└── PHASE_7_PROGRESS.md          # Implementation progress
```

---

## 🐛 Troubleshooting

### App Won't Start

**Error:** `ModuleNotFoundError: No module named 'streamlit'`

**Solution:**
```bash
uv pip install -e ".[ui]"
```

**Error:** `Database connection failed`

**Solution:**
- Check PostgreSQL is running
- Verify `.env` file exists with correct credentials
- Test connection: `psql -h localhost -U your_user -d context_bridge`

### Crawling Fails

**Error:** `Connection timeout` or `Unable to crawl`

**Possible causes:**
- Website blocks crawlers (check robots.txt)
- URL requires authentication
- Network connectivity issues
- Site uses JavaScript rendering (not supported)

**Solutions:**
- Try a different URL
- Reduce max crawl depth
- Check website accessibility in browser first

### Search Returns No Results

**Possible causes:**
- Pages not yet processed/chunked
- Query too specific
- Document filter too restrictive

**Solutions:**
- Process pages first (Pages → Select → Process)
- Try broader search terms
- Remove document filter to search all documents

### Performance Issues

**Symptoms:** Slow page loads, timeouts

**Solutions:**
- Clear cache (sidebar → Clear All Cache)
- Reduce page size in lists
- Use specific filters to reduce data
- Check database performance
- Restart Streamlit app

---

## 🔒 Security Considerations

### Input Validation
- All user inputs are validated
- URL schemes checked (http/https only)
- SQL injection prevention (parameterized queries)
- XSS protection (HTML escaping)

### Authentication
- ⚠️ **Not implemented in current version**
- App assumes trusted environment
- For production: Add authentication layer
- Consider: Streamlit-authenticator, OAuth, etc.

### Database Security
- Use environment variables for credentials
- Never commit `.env` file
- Use strong database passwords
- Restrict database access to localhost (if possible)

---

## 🚀 Deployment

### Local Development

```bash
uv run streamlit run streamlit_app/app.py
```

### Production Deployment

**Option 1: Streamlit Cloud**

1. Push code to GitHub
2. Connect to Streamlit Cloud
3. Configure secrets (environment variables)
4. Deploy

**Option 2: Docker** (coming soon)

**Option 3: Traditional Server**

```bash
# Install requirements
pip install -e ".[ui]"

# Run with systemd or supervisord
streamlit run streamlit_app/app.py \
    --server.port 8501 \
    --server.headless true \
    --server.address 0.0.0.0
```

**Nginx reverse proxy:**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 📚 Additional Resources

- [Context Bridge Core Documentation](../README.md)
- [MCP Server Implementation](../MCP_SERVER_TESTING.md)
- [Manual Testing Checklist](../docs/STREAMLIT_MANUAL_TESTING.md)
- [Phase 7 Progress Report](../docs/PHASE_7_PROGRESS.md)
- [Streamlit Official Docs](https://docs.streamlit.io/)

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- [ ] Add authentication/authorization
- [ ] Implement dark mode
- [ ] Add data export features
- [ ] Improve mobile responsiveness
- [ ] Add more visualizations
- [ ] Implement real-time updates (WebSocket)

---

## 📄 License

MIT License - See [LICENSE](../LICENSE) file for details

---

## 🆘 Support

For issues, questions, or contributions:

- **Issues**: [GitHub Issues](https://github.com/Ganzzi/context-bridge/issues)
- **Documentation**: [Full Documentation](https://github.com/Ganzzi/context-bridge)
- **Email**: boinguyen9701@gmail.com

---

**Built with ❤️ using Streamlit and Context Bridge**
