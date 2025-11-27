-- V2 Migration: Add Tags and Groups Support (Fixed Order)
-- Created: November 22, 2025
-- This migration adds tables in the correct order to avoid foreign key conflicts

BEGIN;

-- =============================================================================
-- 1. CREATE TAGS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK (
        category IN (
            'documentation_type',
            'technology',
            'domain',
            'custom'
        )
    ),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- 2. CREATE GROUPS TABLE (BEFORE adding foreign keys to pages/chunks)
-- =============================================================================

CREATE TABLE IF NOT EXISTS groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    context_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    context_model TEXT DEFAULT NULL,
    combined_content_length INTEGER,
    total_pages INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    processing_status TEXT DEFAULT 'pending' CHECK (
        processing_status IN (
            'pending',
            'processing',
            'completed',
            'failed',
            'reprocessing'
        )
    ),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- =============================================================================
-- 3. BACKFILL GROUPS FROM EXISTING DATA (before adding foreign keys)
-- =============================================================================

-- Create groups for existing page/chunk group_ids
INSERT INTO groups (
    id,
    document_id,
    name,
    description,
    context_enabled,
    processing_status,
    total_pages,
    total_chunks,
    created_at,
    processed_at
)
SELECT DISTINCT
    COALESCE(c.group_id, gen_random_uuid()),
    c.document_id,
    'Migrated Group',
    'Group migrated from existing data',
    FALSE,
    'completed',
    (SELECT COUNT(DISTINCT p.id) FROM pages p WHERE p.group_id = c.group_id),
    COUNT(*),
    NOW(),
    NOW()
FROM chunks c
WHERE c.group_id IS NOT NULL
GROUP BY c.document_id, c.group_id
ON CONFLICT DO NOTHING;

-- Also backfill from pages table
INSERT INTO groups (
    id,
    document_id,
    name,
    description,
    context_enabled,
    processing_status,
    total_pages,
    created_at,
    processed_at
)
SELECT DISTINCT
    p.group_id,
    p.document_id,
    'Migrated Group',
    'Group migrated from existing pages',
    FALSE,
    'completed',
    COUNT(*),
    MIN(p.crawled_at),
    NOW()
FROM pages p
WHERE p.group_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM groups g WHERE g.id = p.group_id)
GROUP BY p.group_id, p.document_id
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 4. NOW ADD FOREIGN KEY CONSTRAINTS
-- =============================================================================

-- Add foreign key constraint to pages table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_pages_group'
    ) THEN
        ALTER TABLE pages
        ADD CONSTRAINT fk_pages_group 
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL;
    END IF;
END$$;

-- Add foreign key constraint to chunks table  
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_chunks_group'
    ) THEN
        ALTER TABLE chunks
        ADD CONSTRAINT fk_chunks_group
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE;
    END IF;
END$$;

-- Add context column to chunks table
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS context TEXT;

-- =============================================================================
-- 5. CREATE DOCUMENT_TAGS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS document_tags (
    document_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (document_id, tag_id)
);

-- =============================================================================
-- 6. CREATE INDEXES
-- =============================================================================

-- Tags indexes
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);

-- Document tags indexes
CREATE INDEX IF NOT EXISTS idx_document_tags_document ON document_tags(document_id);
CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_document_tags_created ON document_tags(created_at);

-- Groups indexes
CREATE INDEX IF NOT EXISTS idx_groups_document ON groups(document_id);
CREATE INDEX IF NOT EXISTS idx_groups_status ON groups(processing_status);
CREATE INDEX IF NOT EXISTS idx_groups_context_enabled ON groups(context_enabled);
CREATE INDEX IF NOT EXISTS idx_groups_created ON groups(created_at);
CREATE INDEX IF NOT EXISTS idx_groups_document_status ON groups(document_id, processing_status);

-- Pages/Chunks indexes for group_id
CREATE INDEX IF NOT EXISTS idx_pages_group_new ON pages(group_id);
CREATE INDEX IF NOT EXISTS idx_chunks_group_new ON chunks(group_id);

-- Context index for chunks
CREATE INDEX IF NOT EXISTS idx_chunks_context ON chunks USING GIN (
    to_tsvector('english', COALESCE(context, ''))
);

-- =============================================================================
-- 7. SEED PREDEFINED TAGS
-- =============================================================================

-- Documentation Types
INSERT INTO tags (name, category, description) VALUES
('technical-documentation', 'documentation_type', 'General technical documentation'),
('api-reference', 'documentation_type', 'API documentation and references'),
('user-guide', 'documentation_type', 'User guides and tutorials'),
('developer-guide', 'documentation_type', 'Developer-focused documentation'),
('wiki', 'documentation_type', 'Wiki-style documentation'),
('specification', 'documentation_type', 'Technical specifications (RFC, standards)'),
('whitepaper', 'documentation_type', 'Technical whitepapers'),
('research-paper', 'documentation_type', 'Academic/research papers'),
('blog-post', 'documentation_type', 'Blog articles and posts'),
('article', 'documentation_type', 'General articles'),
('faq', 'documentation_type', 'Frequently Asked Questions'),
('changelog', 'documentation_type', 'Version history and changelogs'),
('release-notes', 'documentation_type', 'Software release notes'),
('tutorial', 'documentation_type', 'Step-by-step tutorials'),
('case-study', 'documentation_type', 'Case studies and examples')
ON CONFLICT DO NOTHING;

-- Technology Tags
INSERT INTO tags (name, category, description) VALUES
('python', 'technology', 'Python programming language'),
('javascript', 'technology', 'JavaScript programming language'),
('typescript', 'technology', 'TypeScript programming language'),
('java', 'technology', 'Java programming language'),
('go', 'technology', 'Go programming language'),
('rust', 'technology', 'Rust programming language'),
('csharp', 'technology', 'C# programming language'),
('cpp', 'technology', 'C++ programming language'),
('sql', 'technology', 'SQL and database query language'),
('database', 'technology', 'Database documentation'),
('postgresql', 'technology', 'PostgreSQL database'),
('mongodb', 'technology', 'MongoDB database'),
('redis', 'technology', 'Redis in-memory data store'),
('web-framework', 'technology', 'Web framework documentation'),
('ml-ai', 'technology', 'Machine Learning / AI'),
('cloud', 'technology', 'Cloud platform documentation'),
('aws', 'technology', 'Amazon Web Services'),
('azure', 'technology', 'Microsoft Azure'),
('gcp', 'technology', 'Google Cloud Platform'),
('kubernetes', 'technology', 'Kubernetes container orchestration'),
('docker', 'technology', 'Docker containerization'),
('devops', 'technology', 'DevOps tools and practices'),
('cicd', 'technology', 'CI/CD and automation')
ON CONFLICT DO NOTHING;

-- Domain Tags
INSERT INTO tags (name, category, description) VALUES
('backend', 'domain', 'Backend development'),
('frontend', 'domain', 'Frontend development'),
('fullstack', 'domain', 'Full-stack development'),
('infrastructure', 'domain', 'Infrastructure and systems'),
('security', 'domain', 'Security documentation'),
('testing', 'domain', 'Testing documentation'),
('monitoring', 'domain', 'Monitoring and observability'),
('performance', 'domain', 'Performance optimization'),
('scalability', 'domain', 'Scalability and architecture'),
('deployment', 'domain', 'Deployment and release')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 8. TRIGGERS
-- =============================================================================

CREATE OR REPLACE FUNCTION update_document_on_tag_change()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE documents SET updated_at = NOW() WHERE id = NEW.document_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_doc_on_tag_change ON document_tags;
CREATE TRIGGER update_doc_on_tag_change
AFTER INSERT OR DELETE ON document_tags
FOR EACH ROW
EXECUTE FUNCTION update_document_on_tag_change();

DROP TRIGGER IF EXISTS update_doc_on_group_change ON groups;
CREATE TRIGGER update_doc_on_group_change
AFTER INSERT OR UPDATE ON groups
FOR EACH ROW
EXECUTE FUNCTION update_document_on_tag_change();

-- =============================================================================
-- 9. VERIFY MIGRATION
-- =============================================================================

DO $$
DECLARE
    table_count INTEGER;
    tag_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_name IN ('tags', 'document_tags', 'groups');
    
    SELECT COUNT(*) INTO tag_count FROM tags;
    
    IF table_count = 3 THEN
        RAISE NOTICE 'Migration successful: All 3 tables created';
        RAISE NOTICE 'Seeded % predefined tags', tag_count;
    ELSE
        RAISE WARNING 'Migration incomplete: Only % of 3 tables found', table_count;
    END IF;
END
$$;

COMMIT;
