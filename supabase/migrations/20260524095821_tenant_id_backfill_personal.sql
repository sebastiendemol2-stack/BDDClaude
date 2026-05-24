-- M8 Tenant Isolation: nullable tenant_id columns + personal backfill.
--
-- This migration is intentionally additive:
--   - add nullable tenant_id columns;
--   - backfill existing rows to the default personal tenant;
--   - add tenant indexes;
--   - do not change RLS policies;
--   - do not add NOT NULL;
--   - do not drop or replace uniqueness constraints.

CREATE OR REPLACE FUNCTION pg_temp.add_nullable_tenant_column(table_name regclass, index_name text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE format(
        'ALTER TABLE %s ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES public.vault_tenants(id)',
        table_name
    );
    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS %I ON %s(tenant_id)',
        index_name,
        table_name
    );
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp.backfill_personal_tenant(table_name regclass, tenant uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE format('UPDATE %s SET tenant_id = $1 WHERE tenant_id IS NULL', table_name)
    USING tenant;
END;
$$;

DO $$
DECLARE
    personal_id uuid;
BEGIN
    SELECT id INTO personal_id
    FROM public.vault_tenants
    WHERE slug = 'personal';

    IF personal_id IS NULL THEN
        RAISE EXCEPTION 'Default tenant "personal" does not exist. Apply tenant bootstrap first.';
    END IF;

    -- Direct single-tenant backfill tables.
    IF to_regclass('public.vault_sections') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_sections'::regclass, 'idx_vault_sections_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_sections'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_entries') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_entries'::regclass, 'idx_vault_entries_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_entries'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_transactions') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_transactions'::regclass, 'idx_vault_transactions_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_transactions'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_snapshots') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_snapshots'::regclass, 'idx_vault_snapshots_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_snapshots'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_profile') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_profile'::regclass, 'idx_vault_profile_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_profile'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_journal') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_journal'::regclass, 'idx_vault_journal_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_journal'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_events') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_events'::regclass, 'idx_vault_events_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_events'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_memories') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_memories'::regclass, 'idx_vault_memories_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_memories'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_feedback') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_feedback'::regclass, 'idx_vault_feedback_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_feedback'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_relations') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_relations'::regclass, 'idx_vault_relations_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.vault_relations'::regclass, personal_id);
    END IF;

    IF to_regclass('public.projects') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.projects'::regclass, 'idx_projects_tenant');
        PERFORM pg_temp.backfill_personal_tenant('public.projects'::regclass, personal_id);
    END IF;

    -- Derived tables: prefer parent tenant_id, then default to personal.
    IF to_regclass('public.vault_chunks') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_chunks'::regclass, 'idx_vault_chunks_tenant');

        IF to_regclass('public.vault_entries') IS NOT NULL THEN
            UPDATE public.vault_chunks c
            SET tenant_id = e.tenant_id
            FROM public.vault_entries e
            WHERE c.entry_id = e.id
              AND c.tenant_id IS NULL
              AND e.tenant_id IS NOT NULL;
        END IF;

        PERFORM pg_temp.backfill_personal_tenant('public.vault_chunks'::regclass, personal_id);
    END IF;

    IF to_regclass('public.vault_embeddings') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.vault_embeddings'::regclass, 'idx_vault_embeddings_tenant');

        IF to_regclass('public.vault_entries') IS NOT NULL THEN
            UPDATE public.vault_embeddings emb
            SET tenant_id = e.tenant_id
            FROM public.vault_entries e
            WHERE emb.entry_id = e.id
              AND emb.tenant_id IS NULL
              AND e.tenant_id IS NOT NULL;
        END IF;

        IF to_regclass('public.vault_chunks') IS NOT NULL THEN
            UPDATE public.vault_embeddings emb
            SET tenant_id = c.tenant_id
            FROM public.vault_chunks c
            WHERE emb.chunk_id = c.id
              AND emb.tenant_id IS NULL
              AND c.tenant_id IS NOT NULL;
        END IF;

        PERFORM pg_temp.backfill_personal_tenant('public.vault_embeddings'::regclass, personal_id);
    END IF;

    IF to_regclass('public.sessions') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.sessions'::regclass, 'idx_sessions_tenant');

        IF to_regclass('public.projects') IS NOT NULL THEN
            UPDATE public.sessions s
            SET tenant_id = p.tenant_id
            FROM public.projects p
            WHERE s.project_id = p.id
              AND s.tenant_id IS NULL
              AND p.tenant_id IS NOT NULL;
        END IF;

        PERFORM pg_temp.backfill_personal_tenant('public.sessions'::regclass, personal_id);
    END IF;

    IF to_regclass('public.claude_memory') IS NOT NULL THEN
        PERFORM pg_temp.add_nullable_tenant_column('public.claude_memory'::regclass, 'idx_claude_memory_tenant');

        IF to_regclass('public.projects') IS NOT NULL THEN
            UPDATE public.claude_memory m
            SET tenant_id = p.tenant_id
            FROM public.projects p
            WHERE m.project_id = p.id
              AND m.tenant_id IS NULL
              AND p.tenant_id IS NOT NULL;
        END IF;

        PERFORM pg_temp.backfill_personal_tenant('public.claude_memory'::regclass, personal_id);
    END IF;
END $$;
