-- ============================================================
-- Migration v3.2 — 3 nouvelles tables (S4+S5+S6)
-- Déployer sur BRAIN_URL (wusyqgxzyqifpgmxxbkf.supabase.co)
-- Les scripts (memory_store, feedback_pipeline, graph_extractor)
--   utilisent BRAIN_URL + service_role key pour les écritures.
-- vault_relations stocke obsidian_path en text (pas FK cross-project).
-- vault_feedback.event_id référence vault_events (SUPABASE_URL) sans FK.
-- Idempotent (re-run safe)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

-- ============================================================
-- vault_memories (vector search sessions — S4)
-- ============================================================

create table if not exists vault_memories (
    id              uuid primary key default gen_random_uuid(),
    session_id      uuid not null,
    project_slug    text not null,
    summary         text default '',
    decisions       jsonb default '[]'::jsonb,
    patterns        jsonb default '[]'::jsonb,
    embedding       vector(1536),
    created_at      timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_memories_project ON vault_memories(project_slug);
CREATE INDEX IF NOT EXISTS idx_memories_session ON vault_memories(session_id);
CREATE INDEX IF NOT EXISTS idx_memories_vector ON vault_memories
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

ALTER TABLE vault_memories ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_all_memories ON vault_memories;
CREATE POLICY service_all_memories ON vault_memories
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- vault_feedback (feedback pipeline — S5)
-- ============================================================

create table if not exists vault_feedback (
    id              uuid primary key default gen_random_uuid(),
    event_id        uuid not null,
    content         text not null,
    positive        boolean not null default true,
    occurrences     integer not null default 1,
    status          text not null default 'raw_feedback',
    source          text default 'jan',
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

ALTER TABLE vault_feedback DROP CONSTRAINT IF EXISTS ck_feedback_status;
ALTER TABLE vault_feedback ADD CONSTRAINT ck_feedback_status CHECK (
    status = ANY(ARRAY['raw_feedback','validated_precedent','promoted_memory'])
);

CREATE INDEX IF NOT EXISTS idx_feedback_status ON vault_feedback(status);
CREATE INDEX IF NOT EXISTS idx_feedback_occurrences ON vault_feedback(occurrences);
CREATE INDEX IF NOT EXISTS idx_feedback_event ON vault_feedback(event_id);

ALTER TABLE vault_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_all_feedback ON vault_feedback;
CREATE POLICY service_all_feedback ON vault_feedback
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- vault_relations (graph extraction — S6)
-- Pas de FK directe (vault_entries est sur SUPABASE_URL,
-- ce script déploie sur BRAIN_URL).
-- L'intégrité référentielle est gérée en application.
-- ============================================================

create table if not exists vault_relations (
    id                uuid primary key default gen_random_uuid(),
    source_entry_id   text not null,  -- obsidian_path (pas FK)
    target_entry_id   text not null,  -- obsidian_path (pas FK)
    relation_type     text not null default 'references',
    confidence        real default 0.5,
    metadata          jsonb default '{}'::jsonb,
    created_at        timestamptz default now()
);

ALTER TABLE vault_relations DROP CONSTRAINT IF EXISTS ck_relations_type;
ALTER TABLE vault_relations ADD CONSTRAINT ck_relations_type CHECK (
    relation_type = ANY(ARRAY['references','decides','depends_on','related_to'])
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON vault_relations(source_entry_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON vault_relations(target_entry_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON vault_relations(relation_type);

ALTER TABLE vault_relations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_all_relations ON vault_relations;
CREATE POLICY service_all_relations ON vault_relations
    FOR ALL USING (true) WITH CHECK (true);
