-- schema/supabase.sql
-- DDL complet du Second Brain v3.0.0 + UKP v1 — idempotent (re-run safe)
-- Dernière mise à jour : 2026-05-21
--
-- IMPORTANT: Deux projets séparés
--   sync.py  → SUPABASE_URL   (vault_entries, vault_sections, vault_profile, vault_journal)
--   brain.py → BRAIN_URL      (projects, sessions, claude_memory)

-- ============================================================
-- Projet sync.py (SUPABASE_URL / SUPABASE_ANON_KEY)
-- ============================================================

create table if not exists vault_sections (
    id          uuid primary key default gen_random_uuid(),
    slug        text unique not null,
    name        text,
    description text,
    icon        text,
    created_at  timestamptz default now()
);

ALTER TABLE vault_sections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_select_sections ON vault_sections;
CREATE POLICY anon_select_sections ON vault_sections
    FOR SELECT USING (true);
DROP POLICY IF EXISTS service_all_sections ON vault_sections;
CREATE POLICY service_all_sections ON vault_sections
    FOR ALL USING (true) WITH CHECK (true);

create table if not exists vault_entries (
    id              uuid primary key default gen_random_uuid(),
    section_slug    text references vault_sections(slug),
    obsidian_path   text unique not null,
    title           text,
    content         text,
    tags            text[],
    source          text,
    type            text,
    status          text default 'active',
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

-- Idempotent enriched columns for vault_entries v3.0.0
do $$
begin
    -- Phase 3 columns (hash, links, canonical)
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'content_hash') then
        alter table vault_entries add column content_hash text;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'source_hash') then
        alter table vault_entries add column source_hash text;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'source_path') then
        alter table vault_entries add column source_path text;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'links_to') then
        alter table vault_entries add column links_to jsonb default '[]'::jsonb;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'canonical_slug') then
        alter table vault_entries add column canonical_slug text;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'token_count') then
        alter table vault_entries add column token_count integer;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'summary') then
        alter table vault_entries add column summary text;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'last_ingested_at') then
        alter table vault_entries add column last_ingested_at timestamptz;
    end if;
    -- Phase 4 columns (freshness, memory_tier, decay)
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'freshness') then
        alter table vault_entries add column freshness text default 'volatile';
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'memory_tier') then
        alter table vault_entries add column memory_tier text default 'working';
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'decay_score') then
        alter table vault_entries add column decay_score real default 0.0;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'sensitivity') then
        alter table vault_entries add column sensitivity text default 'internal';
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'confidence') then
        alter table vault_entries add column confidence text default 'medium';
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'source_type') then
        alter table vault_entries add column source_type text default 'synthesis';
    end if;
    -- Phase 1 Fiabilité columns (confidence scoring, lineage)
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'confidence_score') then
        alter table vault_entries add column confidence_score real;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'confidence_signals') then
        alter table vault_entries add column confidence_signals jsonb default '{}'::jsonb;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'lineage_depth') then
        alter table vault_entries add column lineage_depth integer default 0;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'derived_from') then
        alter table vault_entries add column derived_from jsonb default '[]'::jsonb;
    end if;
    -- Phase 1 Fiabilité — Human validation workflow (review_status)
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'review_status') then
        alter table vault_entries add column review_status text default 'draft';
    end if;
    -- Phase 1 Fiabilité — Stale status (source invalidation)
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'stale_status') then
        alter table vault_entries add column stale_status text;
    end if;
    if not exists (select 1 from information_schema.columns where table_name = 'vault_entries' and column_name = 'stale_reason') then
        alter table vault_entries add column stale_reason text;
    end if;
end;
$$;

-- ============================================================
-- v3.1 — CHECK constraints for allowed values (from manifest.yaml)
-- ============================================================

ALTER TABLE vault_entries DROP CONSTRAINT IF EXISTS ck_entries_type;
ALTER TABLE vault_entries ADD CONSTRAINT ck_entries_type CHECK (
    type = ANY(ARRAY['concept','projet','contexte','recherche','decision','ressource','personne','daily','index'])
);

ALTER TABLE vault_entries DROP CONSTRAINT IF EXISTS ck_entries_status;
ALTER TABLE vault_entries ADD CONSTRAINT ck_entries_status CHECK (
    status = ANY(ARRAY['active','archive','staging'])
);

ALTER TABLE vault_entries DROP CONSTRAINT IF EXISTS ck_entries_freshness;
ALTER TABLE vault_entries ADD CONSTRAINT ck_entries_freshness CHECK (
    freshness = ANY(ARRAY['evergreen','volatile','deprecated'])
);

ALTER TABLE vault_entries DROP CONSTRAINT IF EXISTS ck_entries_sensitivity;
ALTER TABLE vault_entries ADD CONSTRAINT ck_entries_sensitivity CHECK (
    sensitivity = ANY(ARRAY['public','internal','private','sensitive'])
);

ALTER TABLE vault_entries DROP CONSTRAINT IF EXISTS ck_entries_confidence;
ALTER TABLE vault_entries ADD CONSTRAINT ck_entries_confidence CHECK (
    confidence = ANY(ARRAY['high','medium','low'])
);

ALTER TABLE vault_entries DROP CONSTRAINT IF EXISTS ck_entries_source_type;
ALTER TABLE vault_entries ADD CONSTRAINT ck_entries_source_type CHECK (
    source_type = ANY(ARRAY['raw','extraction','synthesis','human'])
);

ALTER TABLE vault_entries DROP CONSTRAINT IF EXISTS ck_entries_review_status;
ALTER TABLE vault_entries ADD CONSTRAINT ck_entries_review_status CHECK (
    review_status = ANY(ARRAY['draft','reviewed','verified','canonical'])
);

ALTER TABLE vault_entries DROP CONSTRAINT IF EXISTS ck_entries_stale_status;
ALTER TABLE vault_entries ADD CONSTRAINT ck_entries_stale_status CHECK (
    stale_status IS NULL OR stale_status = ANY(ARRAY['stale','needs_reingest','partially_outdated'])
);

-- vault_sections slug format (kebab-case)
ALTER TABLE vault_sections DROP CONSTRAINT IF EXISTS ck_sections_slug;
ALTER TABLE vault_sections ADD CONSTRAINT ck_sections_slug CHECK (
    slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
);

-- vault_transactions status values
ALTER TABLE vault_transactions DROP CONSTRAINT IF EXISTS ck_transactions_status;
ALTER TABLE vault_transactions ADD CONSTRAINT ck_transactions_status CHECK (
    status = ANY(ARRAY['pending', 'committed', 'rolled_back', 'failed'])
);

-- Trigger to auto-update updated_at
create or replace function update_updated_at()
returns trigger language plpgsql search_path = '' as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger vault_entries_updated_at
    before update on vault_entries
    for each row execute function update_updated_at();

create table if not exists vault_profile (
    id          uuid primary key default gen_random_uuid(),
    key         text unique not null,
    value       text,
    updated_at  timestamptz default now()
);

ALTER TABLE vault_profile ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_profile ON vault_profile;
CREATE POLICY service_all_profile ON vault_profile
    FOR ALL USING (true) WITH CHECK (true);

create table if not exists vault_journal (
    id          uuid primary key default gen_random_uuid(),
    entry_date  date not null default CURRENT_DATE,
    title       text,
    content     text not null,
    tags        text[] default '{}',
    project     text,
    created_at  timestamptz default now()
);

ALTER TABLE vault_journal ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_journal ON vault_journal;
CREATE POLICY service_all_journal ON vault_journal
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- v3.0.0 — vault_chunks (must be created BEFORE vault_embeddings)
-- ============================================================

create table if not exists vault_chunks (
    id              uuid primary key default gen_random_uuid(),
    entry_id        uuid references vault_entries(id) on delete cascade,
    chunk_index     integer not null,
    content         text not null,
    token_count     integer,
    created_at      timestamptz default now()
);

-- ============================================================
-- v3.0.0 — vault_embeddings (multi-provider, separated from vault_entries)
-- ============================================================

create table if not exists vault_embeddings (
    id                uuid primary key default gen_random_uuid(),
    entry_id          uuid references vault_entries(id) on delete cascade,
    chunk_id          uuid references vault_chunks(id) on delete cascade,
    provider          text not null,
    model             text not null,
    embedding_dim     integer not null,
    embedding         vector(1536),
    embedding_hash    text not null,
    pipeline_version  integer default 1,
    chunking_strategy text default 'section',
    tokenizer_hash    text,
    created_at        timestamptz default now()
);

-- ============================================================
-- v3.1 — Indexes & Performance
-- ============================================================

-- FK indexes (PostgreSQL does NOT auto-index foreign keys)
CREATE INDEX IF NOT EXISTS idx_entries_section ON vault_entries(section_slug);
CREATE INDEX IF NOT EXISTS idx_chunks_entry ON vault_chunks(entry_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_entry ON vault_embeddings(entry_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk ON vault_embeddings(chunk_id);

-- Content hash (critical for sync diff performance)
CREATE INDEX IF NOT EXISTS idx_entries_hash ON vault_entries(content_hash);
CREATE INDEX IF NOT EXISTS idx_entries_hash_path ON vault_entries(content_hash, obsidian_path);

-- Vector search (requires pgvector extension)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON vault_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- GIN indexes for array/jsonb queries
CREATE INDEX IF NOT EXISTS idx_entries_tags ON vault_entries USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_entries_links ON vault_entries USING GIN (links_to);

-- Partial index for active notes (most queries filter by status = 'active')
CREATE INDEX IF NOT EXISTS idx_entries_active ON vault_entries(status) WHERE status = 'active';

-- Brain project indexes
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_project ON claude_memory(project_id);

-- Unique constraint to prevent duplicate chunks
ALTER TABLE vault_chunks DROP CONSTRAINT IF EXISTS uq_chunk_entry_index;
ALTER TABLE vault_chunks ADD CONSTRAINT uq_chunk_entry_index UNIQUE (entry_id, chunk_index);

-- ============================================================
-- v3.1 — Full-Text Search (French)
-- ============================================================

ALTER TABLE vault_entries ADD COLUMN IF NOT EXISTS content_search tsvector
    GENERATED ALWAYS AS (to_tsvector('french', coalesce(content, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_entries_fts ON vault_entries USING GIN (content_search);

CREATE OR REPLACE FUNCTION search_vault(search_query text, limit_n int DEFAULT 20)
RETURNS SETOF vault_entries LANGUAGE sql STABLE search_path = '' AS $$
    SELECT * FROM vault_entries
    WHERE content_search @@ plainto_tsquery('french', search_query)
        AND status = 'active'
    ORDER BY ts_rank(content_search, plainto_tsquery('french', search_query)) DESC
    LIMIT limit_n;
$$;

-- ============================================================
-- v3.0.0 — vault_transactions (staging → wiki audit trail)
-- ============================================================

create table if not exists vault_transactions (
    id              uuid primary key default gen_random_uuid(),
    operations      jsonb not null,
    status          text default 'pending',
    snapshot_before jsonb,
    snapshot_after  jsonb,
    error           text,
    created_at      timestamptz default now(),
    completed_at    timestamptz
);

ALTER TABLE vault_transactions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_transactions ON vault_transactions;
CREATE POLICY service_all_transactions ON vault_transactions
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- v3.0.0 — vault_snapshots (temporal graph)
-- ============================================================

create table if not exists vault_snapshots (
    id              uuid primary key default gen_random_uuid(),
    graph_stats     jsonb,
    note_count      integer,
    link_count      integer,
    created_at      timestamptz default now()
);

ALTER TABLE vault_snapshots ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_snapshots ON vault_snapshots;
CREATE POLICY service_all_snapshots ON vault_snapshots
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- v3.0.0 — vault_links_from (materialized view of inverted links)
-- ============================================================

create materialized view if not exists vault_links_from as
select
    le.id as source_entry_id,
    le.obsidian_path as source_path,
    trim(both '"' from jsonb_array_elements_text(le.links_to)) as target_path
from vault_entries le
where le.links_to is not null
  and jsonb_array_length(le.links_to) > 0;

-- Required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS uq_links_from_entry ON vault_links_from(source_entry_id, target_path);

-- Matview bypasses RLS; restrict to service_role
REVOKE ALL ON vault_links_from FROM anon, authenticated;

-- ============================================================
-- Projet brain.py (BRAIN_URL / BRAIN_SERVICE_KEY)
-- ============================================================

create table if not exists projects (
    id          uuid primary key default gen_random_uuid(),
    slug        text unique not null,
    name        text,
    working_dir text,
    status      text default 'active',
    created_at  timestamptz default now()
);

create table if not exists sessions (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid references projects(id),
    started_at  timestamptz default now(),
    ended_at    timestamptz,
    summary     text
);

create table if not exists claude_memory (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid references projects(id),
    type        text not null,
    key         text,
    value       text,
    source      text,
    session_id  uuid,
    content     text,
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

-- Unique constraint for upsert_memory_with_history RPC (project_id + type + key)
alter table claude_memory
    drop constraint if exists claude_memory_project_type_unique;
alter table claude_memory
    drop constraint if exists claude_memory_project_type_key_unique;
alter table claude_memory
    add constraint claude_memory_project_type_key_unique unique (project_id, type, key);

-- ============================================================
-- RPC utilisé par brain.py
-- ============================================================

create or replace function upsert_memory_with_history(
    p_project_id  uuid,
    p_type        text,
    p_key         text default null,
    p_value       text default null,
    p_source      text default null,
    p_session_id  uuid default null
) returns void language plpgsql search_path = '' as $$
begin
    insert into claude_memory (project_id, type, key, value, source, session_id)
    values (p_project_id, p_type, p_key, p_value, p_source, p_session_id)
    on conflict (project_id, type, key)
    do update set value = excluded.value, updated_at = now();
end;
$$;

-- ============================================================
-- v3.1 — Row Level Security (RLS)
-- ============================================================

-- vault_entries: anon = read-only public/internal
ALTER TABLE vault_entries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS anon_select_public_internal ON vault_entries;
CREATE POLICY anon_select_public_internal ON vault_entries
    FOR SELECT USING (sensitivity IN ('public', 'internal'));

DROP POLICY IF EXISTS service_all_entries ON vault_entries;
CREATE POLICY service_all_entries ON vault_entries
    FOR ALL USING (true) WITH CHECK (true);

-- vault_chunks
ALTER TABLE vault_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS anon_select_chunks ON vault_chunks;
CREATE POLICY anon_select_chunks ON vault_chunks
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM vault_entries WHERE id = entry_id AND sensitivity IN ('public', 'internal'))
    );

DROP POLICY IF EXISTS service_all_chunks ON vault_chunks;
CREATE POLICY service_all_chunks ON vault_chunks
    FOR ALL USING (true) WITH CHECK (true);

-- vault_embeddings
ALTER TABLE vault_embeddings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS anon_select_embeddings ON vault_embeddings;
CREATE POLICY anon_select_embeddings ON vault_embeddings
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM vault_entries WHERE id = entry_id AND sensitivity IN ('public', 'internal'))
    );

DROP POLICY IF EXISTS service_all_embeddings ON vault_embeddings;
CREATE POLICY service_all_embeddings ON vault_embeddings
    FOR ALL USING (true) WITH CHECK (true);

-- Brain tables (service_role only)
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_projects ON projects;
CREATE POLICY service_all_projects ON projects FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_sessions ON sessions;
CREATE POLICY service_all_sessions ON sessions FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE claude_memory ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_memory ON claude_memory;
CREATE POLICY service_all_memory ON claude_memory FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- v3.2 — vault_events (append-only event log pour S3 event-driven)
-- ============================================================

create table if not exists vault_events (
    id              uuid primary key default gen_random_uuid(),
    event_type      text not null check (
        event_type = ANY(ARRAY['session_start','session_end','message','feedback','ingest','custom'])
    ),
    payload         jsonb not null default '{}'::jsonb,
    source          text not null default 'jan',
    project_slug    text,
    session_id      uuid,  -- references brain sessions(id), no FK (cross-project)
    ingested        boolean not null default false,
    ingested_at     timestamptz,
    error           text,
    created_at      timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_events_unprocessed ON vault_events(ingested, created_at)
    WHERE ingested = false;
CREATE INDEX IF NOT EXISTS idx_events_type ON vault_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_project ON vault_events(project_slug);
CREATE INDEX IF NOT EXISTS idx_events_created ON vault_events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_session ON vault_events(session_id);

ALTER TABLE vault_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_events ON vault_events;
CREATE POLICY service_all_events ON vault_events
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- v3.2 — vault_memories (vector search sessions pour S4)
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
-- v3.2 — vault_feedback (feedback pipeline pour S5)
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

ALTER TABLE vault_feedback DROP CONSTRAINT IF EXISTS fk_feedback_event;
ALTER TABLE vault_feedback ADD CONSTRAINT fk_feedback_event
    FOREIGN KEY (event_id) REFERENCES vault_events(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_feedback_status ON vault_feedback(status);
CREATE INDEX IF NOT EXISTS idx_feedback_occurrences ON vault_feedback(occurrences);
CREATE INDEX IF NOT EXISTS idx_feedback_event ON vault_feedback(event_id);

ALTER TABLE vault_feedback ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_feedback ON vault_feedback;
CREATE POLICY service_all_feedback ON vault_feedback
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- v3.2 — vault_relations (graph extraction pour S6)
-- Pas de FK (vault_entries est sur SUPABASE_URL, ceci déploie
-- sur BRAIN_URL). Intégrité référentielle en application.
-- ============================================================

create table if not exists vault_relations (
    id                uuid primary key default gen_random_uuid(),
    source_entry_id   text not null,  -- obsidian_path
    target_entry_id   text not null,  -- obsidian_path
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

-- ============================================================
-- v3.1 — Maintenance functions
-- ============================================================

-- Refresh the materialized view vault_links_from (call after each push)
CREATE OR REPLACE FUNCTION refresh_vault_links()
RETURNS void LANGUAGE sql search_path = '' AS $$
    REFRESH MATERIALIZED VIEW CONCURRENTLY vault_links_from;
$$;

-- Compute decay_score for volatile notes based on age
CREATE OR REPLACE FUNCTION compute_decay_scores()
RETURNS int LANGUAGE plpgsql search_path = '' AS $$
DECLARE
    updated_count int;
BEGIN
    UPDATE vault_entries
    SET decay_score = LEAST(1.0, EXTRACT(DAY FROM now() - COALESCE(last_ingested_at, updated_at, created_at))::real / 180.0)
    WHERE freshness = 'volatile' AND status = 'active';
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$;

-- ============================================================
-- v3.3 — Function permissions (restrict mutable functions)
-- ============================================================

REVOKE EXECUTE ON FUNCTION upsert_memory_with_history FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION compute_decay_scores FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION refresh_vault_links FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION upsert_memory_with_history TO service_role;
GRANT EXECUTE ON FUNCTION compute_decay_scores TO service_role;
GRANT EXECUTE ON FUNCTION refresh_vault_links TO service_role;
-- search_vault stays accessible (read-only FTS)

-- ============================================================
-- UKP v1 — Universal Knowledge Protocol: Runtime Tables
-- Déployé via migration 20260521_ukp_v1_runtime_tables
-- ============================================================

-- tools_registry
create table if not exists tools_registry (
    id              uuid primary key default gen_random_uuid(),
    name            text unique not null,
    description     text not null,
    version         text not null default '1.0.0',
    category        text not null default 'knowledge'
        check (category in ('knowledge', 'memory', 'session', 'context', 'system')),
    input_schema    jsonb not null default '{}'::jsonb,
    output_schema   jsonb not null default '{}'::jsonb,
    endpoint        text not null,
    auth_level      text not null default 'service_role'
        check (auth_level in ('anon', 'authenticated', 'service_role')),
    tags            text[] default '{}',
    enabled         boolean not null default true,
    created_at      timestamptz default now()
);

ALTER TABLE tools_registry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_tools ON tools_registry;
CREATE POLICY anon_read_tools ON tools_registry
    FOR SELECT USING (enabled = true);
DROP POLICY IF EXISTS service_all_tools ON tools_registry;
CREATE POLICY service_all_tools ON tools_registry
    FOR ALL USING (true) WITH CHECK (true);

-- tool_calls
create table if not exists tool_calls (
    id              uuid primary key default gen_random_uuid(),
    session_id      uuid,
    tool_name       text not null,
    input_payload   jsonb not null,
    output_payload  jsonb,
    status          text not null default 'running'
        check (status in ('running', 'success', 'error', 'cancelled')),
    duration_ms     integer,
    token_count     integer,
    error_message   text,
    client_ide      text,
    project_slug    text,
    created_at      timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_tool ON tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_calls_status ON tool_calls(status);
CREATE INDEX IF NOT EXISTS idx_tool_calls_created ON tool_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_project ON tool_calls(project_slug);

ALTER TABLE tool_calls ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_tool_calls ON tool_calls;
CREATE POLICY service_all_tool_calls ON tool_calls
    FOR ALL USING (true) WITH CHECK (true);

-- context_profiles
create table if not exists context_profiles (
    id                uuid primary key default gen_random_uuid(),
    name              text unique not null,
    description       text,
    system_prompt     text,
    retrieval_config  jsonb not null default '{"hybrid": true, "fts_weight": 0.4, "vector_weight": 0.6, "max_chunks": 24, "rerank": true}'::jsonb,
    compression_config jsonb not null default '{"strategy": "semantic", "target_tokens": 12000}'::jsonb,
    memory_config     jsonb not null default '{"short_term_limit": 25, "episodic_limit": 10, "include_decisions": true, "include_patterns": true}'::jsonb,
    tools_config      jsonb not null default '{"auto_enable": ["query", "prime", "ingest"]}'::jsonb,
    token_budget      integer not null default 12000,
    is_default        boolean not null default false,
    created_at        timestamptz default now(),
    updated_at        timestamptz default now()
);

ALTER TABLE context_profiles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_profiles ON context_profiles;
CREATE POLICY anon_read_profiles ON context_profiles
    FOR SELECT USING (true);
DROP POLICY IF EXISTS service_all_profiles ON context_profiles;
CREATE POLICY service_all_profiles ON context_profiles
    FOR ALL USING (true) WITH CHECK (true);

-- ide_clients
create table if not exists ide_clients (
    id              uuid primary key default gen_random_uuid(),
    project_slug    text not null,
    ide_type        text not null
        check (ide_type in ('claude-code', 'opencode', 'vscode', 'cursor', 'windsurf', 'custom')),
    client_name     text,
    capabilities    jsonb not null default '{"streaming": false, "tool_parallelism": false, "supports_mcp": false, "local_embeddings": false, "approval_workflows": false}'::jsonb,
    config          jsonb not null default '{}'::jsonb,
    last_ping       timestamptz,
    created_at      timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_ide_clients_project ON ide_clients(project_slug);
CREATE INDEX IF NOT EXISTS idx_ide_clients_type ON ide_clients(ide_type);

ALTER TABLE ide_clients ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_ide ON ide_clients;
CREATE POLICY service_all_ide ON ide_clients
    FOR ALL USING (true) WITH CHECK (true);

-- session_events
create table if not exists session_events (
    id              bigint generated always as identity primary key,
    session_id      uuid not null,
    event_type      text not null
        check (event_type in ('session.started', 'session.ended', 'context.injected', 'context.built', 'tool.executed', 'tool.failed', 'memory.updated', 'memory.retrieved', 'knowledge.ingested', 'knowledge.searched', 'profile.loaded', 'error', 'custom')),
    payload         jsonb not null default '{}'::jsonb,
    project_slug    text,
    created_at      timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_session_events_type ON session_events(event_type);
CREATE INDEX IF NOT EXISTS idx_session_events_created ON session_events(created_at);
CREATE INDEX IF NOT EXISTS idx_session_events_project ON session_events(project_slug);

ALTER TABLE session_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_session_events ON session_events;
CREATE POLICY service_all_session_events ON session_events
    FOR ALL USING (true) WITH CHECK (true);

-- resources_registry (MCP)
create table if not exists resources_registry (
    id              uuid primary key default gen_random_uuid(),
    uri_pattern     text unique not null,
    name            text not null,
    description     text,
    mime_type       text default 'text/markdown',
    category        text not null default 'note'
        check (category in ('note', 'project', 'section', 'memory', 'profile', 'system', 'session')),
    is_dynamic      boolean not null default false,
    created_at      timestamptz default now()
);

ALTER TABLE resources_registry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_resources ON resources_registry;
CREATE POLICY anon_read_resources ON resources_registry
    FOR SELECT USING (true);
DROP POLICY IF EXISTS service_all_resources ON resources_registry;
CREATE POLICY service_all_resources ON resources_registry
    FOR ALL USING (true) WITH CHECK (true);

-- agent_permissions
create table if not exists agent_permissions (
    id              uuid primary key default gen_random_uuid(),
    agent_name      text not null,
    project_slug    text not null,
    permissions     jsonb not null default '{"read_memory": true, "write_memory": false, "execute_tools": ["query"], "allowed_projects": ["*"]}'::jsonb,
    expires_at      timestamptz,
    created_at      timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_agent_perms_agent ON agent_permissions(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_perms_project ON agent_permissions(project_slug);

ALTER TABLE agent_permissions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_all_agent_perms ON agent_permissions;
CREATE POLICY service_all_agent_perms ON agent_permissions
    FOR ALL USING (true) WITH CHECK (true);

-- UKP Functions
create or replace function ukp_refresh_decay_scores()
returns int language plpgsql as $$
declare
    updated_count int;
begin
    update vault_entries
    set decay_score = least(1.0, extract(day from now() - coalesce(last_ingested_at, updated_at, created_at))::real / 180.0)
    where freshness = 'volatile' and status = 'active';
    get diagnostics updated_count = row_count;
    return updated_count;
end;
$$;

revoke execute on function ukp_refresh_decay_scores from public, anon, authenticated;
grant execute on function ukp_refresh_decay_scores to service_role;

create or replace function ukp_record_tool_call(
    p_session_id    uuid,
    p_tool_name     text,
    p_input_payload jsonb,
    p_project_slug  text default null,
    p_client_ide    text default null
) returns uuid language plpgsql as $$
declare
    call_id uuid;
begin
    insert into tool_calls (session_id, tool_name, input_payload, status, project_slug, client_ide)
    values (p_session_id, p_tool_name, p_input_payload, 'running', p_project_slug, p_client_ide)
    returning id into call_id;
    return call_id;
end;
$$;

revoke execute on function ukp_record_tool_call from public, anon, authenticated;
grant execute on function ukp_record_tool_call to service_role;

create or replace function ukp_complete_tool_call(
    p_call_id        uuid,
    p_output_payload jsonb,
    p_status         text,
    p_duration_ms    integer default null,
    p_token_count    integer default null,
    p_error_message  text default null
) returns void language plpgsql as $$
begin
    update tool_calls
    set output_payload = p_output_payload,
        status = p_status,
        duration_ms = p_duration_ms,
        token_count = p_token_count,
        error_message = p_error_message
    where id = p_call_id;
end;
$$;

revoke execute on function ukp_complete_tool_call from public, anon, authenticated;
grant execute on function ukp_complete_tool_call to service_role;

create or replace function ukp_emit_session_event(
    p_session_id   uuid,
    p_event_type   text,
    p_payload      jsonb default '{}'::jsonb,
    p_project_slug text default null
) returns bigint language plpgsql as $$
declare
    event_id bigint;
begin
    insert into session_events (session_id, event_type, payload, project_slug)
    values (p_session_id, p_event_type, p_payload, p_project_slug)
    returning id into event_id;
    return event_id;
end;
$$;

revoke execute on function ukp_emit_session_event from public, anon, authenticated;
grant execute on function ukp_emit_session_event to service_role;
