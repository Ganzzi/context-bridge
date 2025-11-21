# Migration Guide: Context Bridge v0.1 → v0.2.0

**Date:** November 2025  
**Version:** v0.2.0  
**Target Users:** Current v0.1.x deployments upgrading to v0.2.0

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [What's New in v0.2.0](#whats-new-in-v020)
3. [Breaking Changes](#breaking-changes)
4. [Pre-Migration Checklist](#pre-migration-checklist)
5. [Migration Steps](#migration-steps)
6. [Database Migrations](#database-migrations)
7. [Configuration Updates](#configuration-updates)
8. [Post-Migration Validation](#post-migration-validation)
9. [Rollback Procedure](#rollback-procedure)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

**For most users:** Follow the 5-step process below to upgrade safely.

```bash
# 1. Backup your database
pg_dump -U postgres context_bridge > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Update package
pip install --upgrade context-bridge==0.2.0

# 3. Run migrations
context-bridge migrate

# 4. Update configuration (if needed)
# See Configuration Updates section

# 5. Restart services
systemctl restart context-bridge
```

**Estimated Time:** 10-30 minutes (depending on database size)

---

## What's New in v0.2.0

### Major Features

#### 1. **Tags System (Phase 1)**
- Organize documents with predefined and custom tags
- 48 built-in tags across 4 categories:
  - Documentation Types (15 tags): API, Guide, Tutorial, etc.
  - Technologies (23 tags): Python, JavaScript, React, etc.
  - Domains (10 tags): Web, Mobile, Data, etc.
  - Custom tags (unlimited)
- Tag-based filtering and search
- Tag statistics and analytics

**Files Affected:**
- New tables: `tags`, `document_tags`
- New APIs: `list_tags()`, `add_tags_to_document()`, `remove_tag_from_document()`
- New MCP tools: `list_tags`, `add_document_tags`, `remove_tag_from_document`

#### 2. **Groups Management (Phase 2)**
- Group related pages within documents
- Track processing status per group
- Group-level statistics (page count, chunk count)
- Support for batch processing by group

**Files Affected:**
- New table: `groups`
- New repository: `GroupRepository` with 21 methods
- Updated services: `PageRepository`, `ChunkRepository`, `DocManager`
- New APIs: `list_groups()`, `get_group_info()`, `process_group()`

#### 3. **AI Context Generation (Phase 3)**
- Auto-generate contextual summaries for chunks using LLM
- Support for Anthropic Claude and OpenAI GPT models
- Prompt caching for cost optimization
- Configurable temperature and token limits

**Files Affected:**
- New service: `ContextGenerationAgent`
- New dependencies: `pydantic-ai`, `pydantic-ai-slim`
- New config fields: `context_agent_model`, `context_agent_temperature`, etc.
- New APIs: `generate_context_for_group()`, `list_non_context_groups()`

#### 4. **Re-processing with Context (Phase 4)**
- Re-process existing groups with newly enabled context
- Support batch re-processing
- Preserve existing data while adding context
- Track re-processing progress

**Files Affected:**
- New service: `ReprocessingService`
- New repository methods: `delete_by_group()`, `update_chunks_group_reference()`
- New APIs: `reprocess_group_with_context()`, `list_reprocessable_groups()`
- New Streamlit page: `pages/reprocess.py`

#### 5. **System Integration Tests**
- 28+ new comprehensive integration tests
- End-to-end workflow validation
- Multi-phase interaction testing
- Error recovery scenarios

### Minor Improvements

- Enhanced error handling and logging throughout
- Improved search performance with optimized indexes
- Better async/await patterns across all services
- Comprehensive type hints (100% coverage)
- Extended documentation and examples

---

## Breaking Changes

### ⚠️ Important: No Breaking Changes

**Good news:** v0.2.0 is fully backward compatible with v0.1.x

- Existing APIs remain unchanged
- Database migrations are non-destructive (additive only)
- All existing documents and searches continue to work
- No data loss during migration

### Deprecated (but still functional)

Nothing is deprecated in this release. All v0.1.x features are fully supported.

---

## Pre-Migration Checklist

Before upgrading, ensure:

- [ ] **Database Backup**
  - [ ] Take a full database backup
  - [ ] Store backup in safe location
  - [ ] Test backup restoration locally

- [ ] **Python Version**
  - [ ] Running Python 3.11 or later: `python --version`
  - [ ] Using virtual environment: `which python`

- [ ] **Dependencies**
  - [ ] Review `pyproject.toml` changes (new AI deps)
  - [ ] Check for conflicts with existing packages
  - [ ] Plan for additional disk space (~50MB more)

- [ ] **Staging Testing**
  - [ ] Test upgrade in staging environment first
  - [ ] Validate data integrity after migration
  - [ ] Test new features (tags, groups, context)

- [ ] **Downtime Planning**
  - [ ] Schedule migration during low-traffic hours
  - [ ] Notify users of temporary unavailability
  - [ ] Prepare rollback procedure (see below)

- [ ] **Configuration Review**
  - [ ] Review new config fields in `.env.example`
  - [ ] Plan for LLM API keys (if using context generation)
  - [ ] Decide on optional features to enable

---

## Migration Steps

### Step 1: Backup Database

```bash
# Full backup
pg_dump -U postgres -Fc context_bridge > backup_v0.1_$(date +%Y%m%d_%H%M%S).dump

# Alternative: text format
pg_dump -U postgres context_bridge > backup_v0.1_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_v0.1_*.dump
```

### Step 2: Stop Services

```bash
# Stop web service
systemctl stop context-bridge-web

# Stop MCP server
systemctl stop context-bridge-mcp

# Or if using docker
docker-compose down
```

### Step 3: Update Package

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Upgrade package
pip install --upgrade context-bridge==0.2.0

# Verify installation
pip show context-bridge
# Should show: Version: 0.2.0
```

### Step 4: Run Database Migrations

```bash
# Apply all pending migrations
context-bridge migrate

# Output should show:
# - v2_migration_001_tags_and_groups.sql
# - v2_migration_002_groups_table.sql
# - v2_migration_003_groups_backfill.sql
# Migration successful ✓
```

### Step 5: Update Configuration (Optional)

If using new features, update `.env`:

```bash
# For AI context generation
CONTEXT_AGENT_MODEL=anthropic:claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...  # Your Anthropic API key
OPENAI_API_KEY=sk-...  # Your OpenAI API key (optional)

# Configure context generation
CONTEXT_AGENT_TEMPERATURE=0.3
CONTEXT_AGENT_MAX_TOKENS=500
CONTEXT_BATCH_SIZE=10
CONTEXT_ENABLE_CACHE=true
```

### Step 6: Restart Services

```bash
# Restart web service
systemctl start context-bridge-web

# Restart MCP server
systemctl start context-bridge-mcp

# Or if using docker
docker-compose up -d

# Wait for services to be ready (~10 seconds)
sleep 10

# Verify services are running
curl http://localhost:8501/  # Streamlit app
curl http://localhost:5000/health  # API health check
```

---

## Database Migrations

### Overview

Three migrations are applied automatically:

1. **v2_migration_001_tags_and_groups.sql** (50 lines)
   - Creates `tags` table with 48 predefined tags
   - Creates `document_tags` junction table
   - Adds indexes and constraints

2. **v2_migration_002_groups_table.sql** (100 lines)
   - Creates `groups` table for page grouping
   - Adds foreign keys to `pages` and `chunks`
   - Creates indexes on group_id

3. **v2_migration_003_groups_backfill.sql** (200+ lines)
   - Creates groups for existing page groupings
   - Backfills group statistics
   - Validates data integrity

### Migration Safety

Each migration includes:

- ✅ Pre-flight checks (schema validation)
- ✅ Transaction rollback on failure
- ✅ Data integrity verification
- ✅ Backward compatibility checks

### Rollback Capability

If migration fails:

```sql
-- Migration 001 rollback
DROP TABLE IF EXISTS document_tags;
DROP TABLE IF EXISTS tags;

-- Migration 002 rollback
ALTER TABLE pages DROP CONSTRAINT IF EXISTS fk_pages_group;
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS fk_chunks_group;
DROP TABLE IF EXISTS groups;

-- Migration 003 - no data changes, safe to skip

-- Verify
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
```

---

## Configuration Updates

### New Environment Variables

**Context Generation (Optional):**

```bash
# LLM Model selection
CONTEXT_AGENT_MODEL=anthropic:claude-3-5-sonnet-20241022
# Options: anthropic:*, openai:gpt-4o, openai:gpt-4-turbo

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Behavior tuning
CONTEXT_AGENT_TEMPERATURE=0.3  # 0.0 (deterministic) to 1.0 (creative)
CONTEXT_AGENT_MAX_TOKENS=500   # Max output tokens per chunk
CONTEXT_BATCH_SIZE=10          # Chunks to process in parallel
CONTEXT_ENABLE_CACHE=true      # Use prompt caching for cost savings
```

**Group Processing:**

```bash
# Group processing defaults
DEFAULT_GROUP_NAME=General  # Default name for auto-created groups
GROUP_AUTO_CONTEXT=false    # Auto-enable context for new groups
```

### Updated Config Schema

**context_bridge/config.py** - New fields added:

```python
# Phase 1: Tags
PREDEFINED_TAGS: dict  # 48 built-in tags

# Phase 2: Groups
GROUP_AUTO_CREATE: bool = True
DEFAULT_GROUP_NAME: str = "General"

# Phase 3: Context Generation
CONTEXT_AGENT_MODEL: str = "anthropic:claude-3-5-sonnet-20241022"
CONTEXT_AGENT_TEMPERATURE: float = 0.3
CONTEXT_AGENT_MAX_TOKENS: int = 500
CONTEXT_BATCH_SIZE: int = 10
CONTEXT_ENABLE_CACHE: bool = True
ANTHROPIC_API_KEY: Optional[str] = None
OPENAI_API_KEY: Optional[str] = None

# Phase 4: Re-processing
REPROCESSING_BATCH_SIZE: int = 5
REPROCESSING_TIMEOUT: int = 3600  # seconds
```

### Backward Compatibility

All new config fields have defaults:
- Optional fields won't cause errors if missing
- Existing `.env` files continue to work
- New features can be enabled incrementally

---

## Post-Migration Validation

### Step 1: Verify Database

```sql
-- Check new tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('tags', 'document_tags', 'groups')
AND table_schema = 'public';

-- Expected output: 3 rows (tags, document_tags, groups)

-- Check predefined tags
SELECT COUNT(*) as tag_count FROM tags;
-- Expected: 48 tags

-- Check groups were backfilled
SELECT COUNT(*) as group_count FROM groups;
-- Expected: >= number of documents
```

### Step 2: Verify API Functionality

```bash
# Test tag operations
curl http://localhost:5000/api/tags

# Test group operations
curl http://localhost:5000/api/groups

# Test MCP tools
mcp list-tools context-bridge

# Expected tools include: list_tags, list_groups, etc.
```

### Step 3: Test UI Components

Visit Streamlit app:
- [ ] Navigate to "Crawled Pages" - should work as before
- [ ] Navigate to "Groups" - should display existing groups
- [ ] Try adding tags to a document
- [ ] Try creating/editing groups

### Step 4: Run Integration Tests

```bash
# Run Phase 5 integration tests
pytest tests/integration/test_complete_workflow.py -v
pytest tests/integration/test_multi_phase.py -v
pytest tests/integration/test_error_recovery.py -v

# All tests should pass
```

### Step 5: Validate Data Integrity

```bash
# Check document count unchanged
SELECT COUNT(*) FROM documents;

# Check pages count unchanged
SELECT COUNT(*) FROM pages;

# Check chunks count unchanged
SELECT COUNT(*) FROM chunks;

# Check search still works
SELECT * FROM chunks WHERE embedding <-> '[0.1, 0.2, ...]'::vector LIMIT 5;
```

---

## Rollback Procedure

### If Migration Fails

```bash
# 1. Stop services
systemctl stop context-bridge-web context-bridge-mcp

# 2. Restore database from backup
pg_restore -U postgres -d context_bridge backup_v0.1_TIMESTAMP.dump

# 3. Downgrade package
pip install context-bridge==0.1.1

# 4. Restart services
systemctl start context-bridge-web context-bridge-mcp

# 5. Verify rollback
curl http://localhost:8501/
```

### If Issues Occur After Migration

#### Database integrity issues:

```sql
-- Run integrity checks
VACUUM ANALYZE;
REINDEX DATABASE context_bridge;

-- Check for constraint violations
SELECT * FROM pg_constraints WHERE table_name IN 
('tags', 'document_tags', 'groups', 'pages', 'chunks')
AND constraint_type = 'f';  -- foreign keys
```

#### Search not working:

```sql
-- Rebuild search indexes
REINDEX INDEX idx_chunks_embedding;
REINDEX INDEX idx_chunks_bm25_content;
```

#### Tags/Groups missing:

```sql
-- Re-seed predefined tags
INSERT INTO tags (id, name, category, description, created_at)
VALUES (...);  -- See migration script for values

-- Re-backfill groups
-- See v2_migration_003_groups_backfill.sql
```

---

## Troubleshooting

### Common Issues

#### 1. Migration Fails: "Relation 'tags' already exists"

**Cause:** Migrations already applied

**Solution:**
```bash
# Check migration status
context-bridge migrate --status

# If already applied, continue with Step 6 (Restart Services)
```

#### 2. Import Error: "No module named 'pydantic_ai'"

**Cause:** New dependencies not installed

**Solution:**
```bash
# Reinstall with all dependencies
pip install --upgrade --force-reinstall context-bridge==0.2.0

# Or manually install
pip install pydantic-ai pydantic-ai-slim
```

#### 3. Context generation API errors

**Cause:** Missing or invalid API keys

**Solution:**
```bash
# Verify API keys in .env
grep ANTHROPIC_API_KEY .env
grep OPENAI_API_KEY .env

# Test API connection
python -c "from anthropic import Anthropic; print('OK')"

# If keys are invalid, get new ones from:
# - Anthropic: https://console.anthropic.com
# - OpenAI: https://platform.openai.com/account/api-keys
```

#### 4. Sluggish performance after upgrade

**Cause:** Missing indexes or outdated query planner stats

**Solution:**
```sql
-- Rebuild all indexes
REINDEX DATABASE context_bridge;

-- Update statistics
VACUUM ANALYZE;

-- Check slow queries
EXPLAIN ANALYZE
SELECT * FROM chunks 
WHERE embedding <-> '[...]'::vector
LIMIT 10;
```

#### 5. Tags/Groups not showing in UI

**Cause:** Cache not cleared or browser cache stale

**Solution:**
```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -r {} +

# Restart services
systemctl restart context-bridge-web

# Clear browser cache (Ctrl+Shift+Delete or Cmd+Shift+Delete)
```

### Getting Help

If issues persist:

1. **Check logs:**
   ```bash
   journalctl -u context-bridge-web -n 100
   tail -f /var/log/context-bridge/app.log
   ```

2. **Enable debug logging:**
   ```bash
   # In .env
   LOG_LEVEL=DEBUG
   ```

3. **Review migration logs:**
   ```bash
   psql -U postgres context_bridge -c "SELECT * FROM schema_migrations ORDER BY installed_on DESC LIMIT 10;"
   ```

4. **Report issue:**
   - GitHub Issues: https://github.com/Ganzzi/context_bridge/issues
   - Include: version, error message, logs, steps to reproduce

---

## Summary

| Step | Action | Time | Status |
|------|--------|------|--------|
| 1 | Backup database | 2-5 min | Before upgrade |
| 2 | Stop services | 1 min | Before upgrade |
| 3 | Update package | 2-5 min | Upgrade |
| 4 | Run migrations | 1-10 min | Upgrade |
| 5 | Update config | 1 min | After upgrade (optional) |
| 6 | Restart services | 2 min | After upgrade |
| 7 | Validate | 5 min | After upgrade |

**Total Time:** 15-30 minutes

---

## Support Timeline

- **v0.2.0 Release:** November 2025
- **v0.1.x Support:** Through May 2026
- **Security Fixes:** As needed
- **Migration Support:** 3 months post-release

---

## Related Documentation

- [README.md](../README.md) - Project overview
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [API_REFERENCE.md](./API_REFERENCE.md) - API documentation
- [Phase Guides](./guides/) - Feature-specific documentation
- [CHANGELOG.md](../CHANGELOG.md) - Full v0.2.0 release notes
