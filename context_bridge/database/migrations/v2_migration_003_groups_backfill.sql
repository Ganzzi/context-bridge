-- Migration: v2_migration_003_groups_backfill.sql
-- Purpose: Backfill existing groups table with data from existing page relationships
--
-- This script backfills the groups table for all existing documents that have pages.
-- For each document, it creates a group for all chunked pages and sets the processing_status
-- to 'completed' since the data is already processed.
--
-- Steps:
-- 1. For each document with pages, create a group
-- 2. Assign all pages to that group
-- 3. Update chunks to reference the group
-- 4. Set processing_status to 'completed'
--
-- This ensures that existing crawled data remains functional with the new group system.

BEGIN TRANSACTION;

-- Step 1: Create a group for each document with existing pages
-- This creates one group per document with all existing pages
INSERT INTO
    groups (
        id,
        document_id,
        name,
        description,
        context_enabled,
        context_model,
        combined_content_length,
        total_pages,
        total_chunks,
        created_at,
        processed_at,
        processing_status,
        metadata
    )
SELECT
    gen_random_uuid ()::uuid, -- id: Generate new UUID
    d.id, -- document_id
    'Default Group: ' || d.name, -- name: Use document name
    'Auto-created group from existing pages', -- description
    FALSE, -- context_enabled: Start with False
    NULL, -- context_model: None initially
    SUM(
        COALESCE(LENGTH(p.content), 0)
    ), -- combined_content_length: Sum of page lengths
    COUNT(DISTINCT p.id)::integer, -- total_pages: Count of pages
    COUNT(DISTINCT c.id)::integer, -- total_chunks: Count of chunks
    NOW(), -- created_at
    NOW(), -- processed_at: Set to now (data already processed)
    'completed'::text, -- processing_status
    jsonb_build_object(
        'migration',
        true,
        'migrated_from',
        'existing_pages',
        'migration_date',
        NOW()::text
    ) -- metadata: Mark as migrated
FROM
    documents d
    LEFT JOIN pages p ON p.document_id = d.id
    LEFT JOIN chunks c ON c.page_id = p.id
    AND c.group_id IS NULL
WHERE
    d.id IN (
        -- Only process documents that have existing pages
        SELECT DISTINCT
            document_id
        FROM pages
    )
GROUP BY
    d.id
ON CONFLICT DO NOTHING;

-- Step 2: Update pages to reference groups
-- Assign all pages to their document's group
UPDATE pages p
SET
    group_id = (
        SELECT id
        FROM groups g
        WHERE
            g.document_id = p.document_id
            AND g.processing_status = 'completed'
            AND g.metadata ->> 'migrated_from' = 'existing_pages'
        LIMIT 1
    )
WHERE
    p.document_id IN (
        SELECT DISTINCT
            document_id
        FROM pages
    )
    AND p.group_id IS NULL;

-- Step 3: Update chunks to reference groups
-- Assign all chunks to their page's group (which was assigned in Step 2)
UPDATE chunks c
SET
    group_id = (
        SELECT p.group_id
        FROM pages p
        WHERE
            p.id = c.page_id
            AND p.group_id IS NOT NULL
    )
WHERE
    c.page_id IN (
        SELECT id
        FROM pages
        WHERE
            group_id IS NOT NULL
    )
    AND c.group_id IS NULL;

-- Step 4: Verify data integrity
-- Count how many records were updated/migrated
DO $$
DECLARE
    groups_created INTEGER;
    pages_assigned INTEGER;
    chunks_assigned INTEGER;
    groups_with_pages INTEGER;
    pages_without_group INTEGER;
    chunks_without_group INTEGER;
BEGIN
    -- Count migrated records
    SELECT COUNT(*) INTO groups_created FROM groups WHERE metadata->>'migrated_from' = 'existing_pages';
    SELECT COUNT(*) INTO pages_assigned FROM pages WHERE group_id IS NOT NULL;
    SELECT COUNT(*) INTO chunks_assigned FROM chunks WHERE group_id IS NOT NULL;
    
    -- Count potential issues
    SELECT COUNT(*) INTO groups_with_pages FROM groups WHERE total_pages > 0;
    SELECT COUNT(*) INTO pages_without_group FROM pages WHERE group_id IS NULL;
    SELECT COUNT(*) INTO chunks_without_group FROM chunks WHERE group_id IS NULL;
    
    -- Log results
    RAISE NOTICE 'Migration Results:';
    RAISE NOTICE '  Groups created: %', groups_created;
    RAISE NOTICE '  Pages assigned to groups: %', pages_assigned;
    RAISE NOTICE '  Chunks assigned to groups: %', chunks_assigned;
    RAISE NOTICE '  Groups with pages: %', groups_with_pages;
    RAISE NOTICE 'Potential Issues:';
    RAISE NOTICE '  Pages without group: %', pages_without_group;
    RAISE NOTICE '  Chunks without group: %', chunks_without_group;
    
    -- If there are orphaned pages/chunks, log a warning
    IF pages_without_group > 0 THEN
        RAISE WARNING 'Found % pages without group assignment', pages_without_group;
    END IF;
    
    IF chunks_without_group > 0 THEN
        RAISE WARNING 'Found % chunks without group assignment', chunks_without_group;
    END IF;
END $$;

-- Step 5: Final validation
-- Check that all groups have proper relationships
SELECT
    g.id,
    g.document_id,
    g.name,
    COUNT(DISTINCT p.id) as actual_pages,
    g.total_pages as expected_pages,
    COUNT(DISTINCT c.id) as actual_chunks,
    g.total_chunks as expected_chunks,
    CASE
        WHEN COUNT(DISTINCT p.id) = g.total_pages
        AND COUNT(DISTINCT c.id) = g.total_chunks THEN '✓ VALID'
        ELSE '✗ MISMATCH'
    END as validation_status
FROM groups g
    LEFT JOIN pages p ON p.group_id = g.id
    LEFT JOIN chunks c ON c.group_id = g.id
WHERE
    g.metadata ->> 'migrated_from' = 'existing_pages'
GROUP BY
    g.id,
    g.document_id,
    g.name,
    g.total_pages,
    g.total_chunks
ORDER BY g.created_at DESC;

COMMIT;

-- Post-migration checks (run separately to verify):
--
-- 1. Verify all pages have groups:
--    SELECT COUNT(*) FROM pages WHERE group_id IS NULL;
--    Expected: 0 (for all pages that existed before migration)
--
-- 2. Verify all chunks have groups:
--    SELECT COUNT(*) FROM chunks WHERE group_id IS NULL;
--    Expected: 0 (for all chunks that existed before migration)
--
-- 3. Verify group statistics:
--    SELECT COUNT(*) FROM groups WHERE processing_status = 'completed' AND metadata->>'migrated_from' = 'existing_pages';
--    Expected: Number of documents with pages
--
-- 4. Verify cascading delete works:
--    DELETE FROM groups WHERE metadata->>'migrated_from' = 'existing_pages' LIMIT 1;
--    Then check that related pages and chunks are NOT deleted (only group_id set to NULL)