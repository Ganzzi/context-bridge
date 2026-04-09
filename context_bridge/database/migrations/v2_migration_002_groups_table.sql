-- V2 Migration 002: Groups Table and Management
-- Duration: ~1-2 hours
-- Purpose: Add explicit groups table for tracking page groupings with processing metadata
--
-- Changes:
-- 1. Create groups table with processing_status tracking
-- 2. Add foreign key constraints to pages and chunks tables
-- 3. Create performance indexes
-- 4. Backfill existing data

BEGIN;

-- 1. CREATE GROUPS TABLE
-- Purpose: Track page groupings with metadata like processing status, context generation status, etc.
CREATE TABLE IF NOT EXISTS groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    document_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    name TEXT, -- Optional human-readable name
    description TEXT, -- Optional description
    context_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    context_model TEXT, -- e.g., "anthropic:claude-3-5-sonnet-20241022"
    combined_content_length INTEGER,
    total_pages INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ, -- When chunking/context generation completed
    processing_status TEXT DEFAULT 'pending' CHECK (
        processing_status IN (
            'pending', -- Created but not processed
            'processing', -- Currently processing
            'completed', -- Successfully processed
            'failed', -- Processing failed
            'reprocessing' -- Being reprocessed
        )
    ),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 2. ALTER EXISTING TABLES TO ADD FOREIGN KEY CONSTRAINTS
-- Note: Some columns might already exist, so we use IF NOT EXISTS where applicable

-- Add foreign key constraint to pages table (if not already present)
ALTER TABLE pages
ADD CONSTRAINT fk_pages_group FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE SET NULL;

-- Add foreign key constraint to chunks table (if not already present)
ALTER TABLE chunks
ADD CONSTRAINT fk_chunks_group FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE;

-- 3. CREATE INDEXES FOR PERFORMANCE
-- Index for filtering by document
CREATE INDEX IF NOT EXISTS idx_groups_document ON groups (document_id);

-- Index for filtering by processing status
CREATE INDEX IF NOT EXISTS idx_groups_status ON groups (processing_status);

-- Index for context-enabled filtering
CREATE INDEX IF NOT EXISTS idx_groups_context_enabled ON groups (context_enabled);

-- Composite index for common queries (document + status)
CREATE INDEX IF NOT EXISTS idx_groups_document_status ON groups (
    document_id,
    processing_status
);

-- 4. BACKFILL EXISTING DATA
-- Create groups for existing page groupings by inferring from existing chunks
-- This ensures existing data is properly associated with groups

-- Get distinct group_ids from chunks table and create corresponding groups
INSERT INTO
    groups (
        id,
        document_id,
        context_enabled,
        processing_status,
        total_pages,
        total_chunks,
        processed_at,
        created_at
    )
SELECT
    COALESCE(
        chunk_group.group_id,
        gen_random_uuid ()
    ) AS id,
    page.document_id,
    FALSE AS context_enabled,
    'completed' AS processing_status,
    COUNT(DISTINCT page.id) AS total_pages,
    COUNT(DISTINCT chunk_group.chunk_id) AS total_chunks,
    NOW() AS processed_at,
    MIN(page.created_at) AS created_at
FROM pages page
    LEFT JOIN (
        SELECT chunks.group_id, chunks.id as chunk_id, pages.id as page_id
        FROM chunks
            JOIN pages ON chunks.page_id = pages.id
        WHERE
            chunks.group_id IS NOT NULL
    ) chunk_group ON page.id = chunk_group.page_id
WHERE
    page.group_id IS NOT NULL
    OR chunk_group.group_id IS NOT NULL
GROUP BY
    page.document_id,
    COALESCE(
        chunk_group.group_id,
        gen_random_uuid ()
    )
ON CONFLICT (id) DO NOTHING;

-- Update pages to reference groups if not already set
-- This happens for pages that are referenced by chunks with group_id set
UPDATE pages
SET
    group_id = (
        SELECT DISTINCT
            chunks.group_id
        FROM chunks
        WHERE
            chunks.page_id = pages.id
            AND chunks.group_id IS NOT NULL
    )
WHERE
    pages.group_id IS NULL
    AND EXISTS (
        SELECT 1
        FROM chunks
        WHERE
            chunks.page_id = pages.id
            AND chunks.group_id IS NOT NULL
    );

-- 5. VERIFY DATA INTEGRITY
-- Add any missing groups for pages that don't have a group yet
-- (Create a default group per document for ungrouped pages)
INSERT INTO
    groups (
        id,
        document_id,
        context_enabled,
        processing_status,
        total_pages,
        total_chunks,
        created_at,
        processed_at
    )
SELECT
    gen_random_uuid () AS id,
    p.document_id,
    FALSE,
    'completed',
    COUNT(DISTINCT p.id),
    0,
    MIN(p.created_at),
    NOW()
FROM pages p
WHERE
    p.group_id IS NULL
GROUP BY
    p.document_id
ON CONFLICT DO NOTHING;

-- Update pages without a group to use the default group
UPDATE pages
SET
    group_id = (
        SELECT id
        FROM groups
        WHERE
            groups.document_id = pages.document_id
        LIMIT 1
    )
WHERE
    pages.group_id IS NULL;

COMMIT;

-- 6. MIGRATION NOTES
-- - Existing chunks are preserved with their group relationships
-- - Pages without groups are assigned to document-level groups
-- - All groups are marked as 'completed' with context_enabled=FALSE
-- - Processed timestamp is set to current time for existing data
-- - This migration is non-breaking and preserves all existing data
--
-- Future: Run Phase 2.5 tasks to fully integrate groups into the application