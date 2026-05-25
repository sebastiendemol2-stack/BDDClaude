-- M8 Task 6 — RLS enforcement on tenant-scoped vault tables.
--
-- Prerequisites (acceptance gate):
--   1. The bootstrap migration (2026-05-24_tenant_bootstrap.sql) is applied.
--   2. The additive backfill migration is applied so every scoped row has
--      tenant_id NOT NULL.
--   3. `_scripts/tenant_duplicate_check.py --strict` exits 0.
--   4. Dashboard, sync.py, rag-answer, query_vector_hybrid are tenant-aware
--      (see issues/month-8-tenant-isolation-plan.md — Phase 5).
--
-- This migration is intentionally split from the backfill so the destructive
-- step is auditable. Run it inside a single transaction.
--
-- What it does:
--   - For every scoped table, enforces NOT NULL on tenant_id.
--   - Replaces global UNIQUE constraints with composite (tenant_id, <col>).
--   - Adds membership-based SELECT/INSERT/UPDATE/DELETE policies to
--     authenticated users; keeps the existing service_role FOR ALL policies.
--   - Removes anon access on tenant-scoped tables — Edge Functions reading
--     these tables must use the service role or an authenticated bearer.
--
-- Global tables that stay outside this flip:
--   vault_models, tools_registry, resources_registry, context_profiles,
--   agent_permissions.

BEGIN;

CREATE OR REPLACE FUNCTION pg_temp.flip_tenant_table(
    table_name regclass,
    composite_unique text DEFAULT NULL,
    composite_column text DEFAULT NULL,
    drop_unique text DEFAULT NULL,
    legacy_suffix text DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    relname text := split_part(table_name::text, '.', 2);
BEGIN
    -- 0. Drop legacy broad authenticated_* policies that predate isolation.
    --    They are OR-ed with our new membership policies, so leaving them in
    --    place would let any authenticated user read every tenant.
    IF legacy_suffix IS NOT NULL THEN
        EXECUTE format('DROP POLICY IF EXISTS %I ON %s',
            'authenticated_select_' || legacy_suffix, table_name);
        EXECUTE format('DROP POLICY IF EXISTS %I ON %s',
            'authenticated_insert_' || legacy_suffix, table_name);
        EXECUTE format('DROP POLICY IF EXISTS %I ON %s',
            'authenticated_update_' || legacy_suffix, table_name);
        EXECUTE format('DROP POLICY IF EXISTS %I ON %s',
            'authenticated_delete_' || legacy_suffix, table_name);
    END IF;
    -- 1. Enforce NOT NULL on tenant_id. The backfill must have populated it.
    EXECUTE format('ALTER TABLE %s ALTER COLUMN tenant_id SET NOT NULL', table_name);

    -- 2. Drop legacy global UNIQUE and add the composite, if requested.
    IF drop_unique IS NOT NULL THEN
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT IF EXISTS %I', table_name, drop_unique);
    END IF;
    IF composite_unique IS NOT NULL AND composite_column IS NOT NULL THEN
        EXECUTE format(
            'ALTER TABLE %s ADD CONSTRAINT %I UNIQUE (tenant_id, %I)',
            table_name, composite_unique, composite_column
        );
    END IF;

    -- 3. Enable RLS (idempotent).
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', table_name);

    -- 4. Drop stale policies if they exist (idempotency for re-runs).
    EXECUTE format('DROP POLICY IF EXISTS %I_select_members ON %s', relname, table_name);
    EXECUTE format('DROP POLICY IF EXISTS %I_modify_members ON %s', relname, table_name);
    EXECUTE format('DROP POLICY IF EXISTS %I_service_all ON %s', relname, table_name);

    -- 5. SELECT for active members of the row's tenant.
    EXECUTE format($p$
        CREATE POLICY %I_select_members ON %s
            FOR SELECT TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM public.vault_tenant_members m
                    WHERE m.tenant_id = %s.tenant_id
                      AND m.user_id = (SELECT auth.uid())
                      AND m.status = 'active'
                )
            )
    $p$, relname, table_name, table_name);

    -- 6. INSERT/UPDATE/DELETE for active owner/admin/member of the row's tenant.
    --    Viewers get read-only via the SELECT policy above.
    EXECUTE format($p$
        CREATE POLICY %I_modify_members ON %s
            FOR ALL TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM public.vault_tenant_members m
                    WHERE m.tenant_id = %s.tenant_id
                      AND m.user_id = (SELECT auth.uid())
                      AND m.status = 'active'
                      AND m.role IN ('owner', 'admin', 'member')
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM public.vault_tenant_members m
                    WHERE m.tenant_id = %s.tenant_id
                      AND m.user_id = (SELECT auth.uid())
                      AND m.status = 'active'
                      AND m.role IN ('owner', 'admin', 'member')
                )
            )
    $p$, relname, table_name, table_name, table_name);

    -- 7. Keep service_role unconstrained.
    EXECUTE format($p$
        CREATE POLICY %I_service_all ON %s
            FOR ALL TO service_role
            USING (true) WITH CHECK (true)
    $p$, relname, table_name);

    -- 8. Revoke anon access on tenant-scoped data.
    EXECUTE format('REVOKE ALL ON TABLE %s FROM anon', table_name);
END;
$$;


DO $$
BEGIN
    -- Direct single-tenant tables.
    IF to_regclass('public.vault_sections') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table(
            'public.vault_sections'::regclass,
            composite_unique => 'vault_sections_tenant_slug_key',
            composite_column => 'slug',
            drop_unique => 'vault_sections_slug_key',
            legacy_suffix => 'sections'
        );
    END IF;

    IF to_regclass('public.vault_entries') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table(
            'public.vault_entries'::regclass,
            composite_unique => 'vault_entries_tenant_path_key',
            composite_column => 'obsidian_path',
            drop_unique => 'vault_entries_obsidian_path_key',
            legacy_suffix => 'entries'
        );
    END IF;

    IF to_regclass('public.projects') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table(
            'public.projects'::regclass,
            composite_unique => 'projects_tenant_slug_key',
            composite_column => 'slug',
            drop_unique => 'projects_slug_key',
            legacy_suffix => 'projects'
        );
    END IF;

    -- Tables that do not need a composite uniqueness flip — RLS + NOT NULL only.
    IF to_regclass('public.vault_chunks') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_chunks'::regclass, legacy_suffix => 'chunks');
    END IF;
    IF to_regclass('public.vault_embeddings') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_embeddings'::regclass, legacy_suffix => 'embeddings');
    END IF;
    IF to_regclass('public.vault_transactions') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_transactions'::regclass, legacy_suffix => 'transactions');
    END IF;
    IF to_regclass('public.vault_snapshots') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_snapshots'::regclass, legacy_suffix => 'snapshots');
    END IF;
    IF to_regclass('public.vault_profile') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_profile'::regclass, legacy_suffix => 'profile');
    END IF;
    IF to_regclass('public.vault_journal') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_journal'::regclass, legacy_suffix => 'journal');
    END IF;
    IF to_regclass('public.vault_events') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_events'::regclass, legacy_suffix => 'events');
    END IF;
    IF to_regclass('public.vault_memories') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_memories'::regclass, legacy_suffix => 'memories');
    END IF;
    IF to_regclass('public.vault_feedback') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_feedback'::regclass, legacy_suffix => 'feedback');
    END IF;
    IF to_regclass('public.vault_relations') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.vault_relations'::regclass, legacy_suffix => 'relations');
    END IF;
    IF to_regclass('public.sessions') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.sessions'::regclass, legacy_suffix => 'sessions');
    END IF;
    IF to_regclass('public.claude_memory') IS NOT NULL THEN
        PERFORM pg_temp.flip_tenant_table('public.claude_memory'::regclass, legacy_suffix => 'claude_memory');
    END IF;
END $$;

COMMIT;
