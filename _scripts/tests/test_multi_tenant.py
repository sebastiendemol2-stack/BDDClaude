"""
Static tests for M8 multi-tenant vault bootstrap.
"""
import os
from pathlib import Path


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MIGRATION = os.path.join('supabase', 'migrations', '2026-05-24_tenant_bootstrap.sql')
PLAN = os.path.join('issues', 'month-8-tenant-isolation-plan.md')


def read_repo_file(*parts: str) -> str:
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as handle:
        return handle.read()


def read_latest_migration(suffix: str) -> str:
    migration_dir = Path(ROOT) / 'supabase' / 'migrations'
    matches = sorted(migration_dir.glob(f'*_{suffix}.sql'))
    assert matches, f'Migration ending with {suffix}.sql not found'
    return matches[-1].read_text(encoding='utf-8')


class TestMultiTenantBootstrap:
    def test_migration_creates_tenant_tables_without_altering_existing_vault_tables(self):
        sql = read_repo_file(MIGRATION)

        assert 'CREATE TABLE IF NOT EXISTS public.vault_tenants' in sql
        assert 'CREATE TABLE IF NOT EXISTS public.vault_tenant_members' in sql
        assert 'ALTER TABLE public.vault_entries' not in sql
        assert 'ALTER TABLE public.vault_embeddings' not in sql
        assert 'ALTER TABLE public.vault_chunks' not in sql

    def test_rls_uses_memberships_and_modern_role_clauses(self):
        sql = read_repo_file(MIGRATION)

        assert 'ENABLE ROW LEVEL SECURITY' in sql
        assert 'TO authenticated' in sql
        assert 'TO service_role' in sql
        assert 'auth.uid()' in sql
        assert 'auth.role()' not in sql
        assert 'user_metadata' not in sql
        assert 'raw_user_meta_data' not in sql

    def test_data_api_grants_are_explicit(self):
        sql = read_repo_file(MIGRATION)

        assert 'GRANT SELECT ON TABLE public.vault_tenants TO authenticated' in sql
        assert 'GRANT SELECT ON TABLE public.vault_tenant_members TO authenticated' in sql
        assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.vault_tenants TO service_role' in sql
        assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.vault_tenant_members TO service_role' in sql

    def test_default_personal_tenant_is_seeded_idempotently(self):
        sql = read_repo_file(MIGRATION)

        assert "'personal'" in sql
        assert 'ON CONFLICT (slug) DO UPDATE' in sql
        assert 'default-single-user-backfill-target' in sql

    def test_tenant_isolation_plan_defers_destructive_changes_until_gates_pass(self):
        plan = read_repo_file(PLAN)

        assert '`vault_entries`' in plan
        assert '`vault_embeddings`' in plan
        assert '`vault_chunks`' in plan
        assert '`vault_models`' in plan
        assert 'remain global in M8' in plan
        assert 'Do not drop global uniqueness' in plan
        assert 'dashboard and Edge Function reads have a tenant filter path' in plan

    def test_tenant_isolation_plan_keeps_rls_membership_based(self):
        plan = read_repo_file(PLAN)

        assert 'vault_tenant_members' in plan
        assert '(SELECT auth.uid())' in plan
        assert 'auth.role()' in plan
        assert 'must not use `auth.role()`' in plan
        assert 'user_metadata' in plan
        assert 'must not use `auth.role()`, `user_metadata`, or `raw_user_meta_data`' in plan


class TestTenantBackfillMigration:
    def test_backfill_migration_adds_nullable_tenant_columns_for_scoped_tables(self):
        sql = read_latest_migration('tenant_id_backfill_personal')

        for table in [
            'vault_sections',
            'vault_entries',
            'vault_chunks',
            'vault_embeddings',
            'vault_transactions',
            'vault_snapshots',
            'vault_profile',
            'vault_journal',
            'vault_events',
            'vault_memories',
            'vault_feedback',
            'vault_relations',
            'projects',
            'sessions',
            'claude_memory',
        ]:
            assert f"to_regclass('public.{table}')" in sql
            assert f'idx_{table}_tenant' in sql

        assert 'ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES public.vault_tenants(id)' in sql

    def test_backfill_migration_derives_child_tenants_before_personal_fallback(self):
        sql = read_latest_migration('tenant_id_backfill_personal')

        assert 'UPDATE public.vault_chunks c' in sql
        assert 'FROM public.vault_entries e' in sql
        assert 'UPDATE public.vault_embeddings emb' in sql
        assert 'FROM public.vault_chunks c' in sql
        assert 'UPDATE public.sessions s' in sql
        assert 'FROM public.projects p' in sql
        assert 'UPDATE public.claude_memory m' in sql
        assert 'backfill_personal_tenant' in sql

    def test_backfill_migration_does_not_flip_rls_or_constraints(self):
        sql = read_latest_migration('tenant_id_backfill_personal')

        assert 'CREATE POLICY' not in sql
        assert 'DROP POLICY' not in sql
        assert 'ENABLE ROW LEVEL SECURITY' not in sql
        assert 'DROP CONSTRAINT' not in sql
        assert 'SET NOT NULL' not in sql
        assert 'UNIQUE (' not in sql


FUNCTIONS_DIR = os.path.join('supabase', 'functions')
TENANT_CREATE = os.path.join(FUNCTIONS_DIR, 'tenant-create', 'index.ts')
TENANT_MEMBER_ASSIGN = os.path.join(FUNCTIONS_DIR, 'tenant-member-assign', 'index.ts')
TENANTS_SHARED = os.path.join(FUNCTIONS_DIR, '_shared', 'tenants.ts')


class TestTenantProvisioningSharedHelpers:
    def test_shared_helpers_expose_role_and_status_enums(self):
        src = read_repo_file(TENANTS_SHARED)

        assert "TENANT_MEMBER_ROLES = ['owner', 'admin', 'member', 'viewer']" in src
        assert "TENANT_MEMBER_STATUSES = ['active', 'invited', 'suspended']" in src
        assert "TENANT_STATUSES = ['active', 'suspended', 'archived']" in src

    def test_shared_helpers_validate_slug_with_bootstrap_regex(self):
        src = read_repo_file(TENANTS_SHARED)
        # Mirror the CHECK constraint on vault_tenants.slug.
        assert '^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$' in src
        assert 'isValidTenantSlug' in src

    def test_shared_helpers_never_trust_user_editable_metadata(self):
        src = read_repo_file(TENANTS_SHARED)
        # Platform admin gate may inspect app_metadata (server-controlled), but
        # tenant authorization must never read user_metadata / raw_user_meta_data.
        assert 'user_metadata' not in src
        assert 'raw_user_meta_data' not in src
        assert 'auth.role()' not in src

    def test_shared_helpers_check_membership_via_vault_tenant_members(self):
        src = read_repo_file(TENANTS_SHARED)

        assert 'hasTenantManagementRole' in src
        assert "from('vault_tenant_members')" in src
        assert "'active'" in src
        assert "'owner'" in src
        assert "'admin'" in src


class TestTenantCreateFunction:
    def test_tenant_create_requires_platform_admin(self):
        src = read_repo_file(TENANT_CREATE)

        assert 'isPlatformAdmin(req)' in src
        assert 'Platform admin authorization required' in src
        assert '401' in src

    def test_tenant_create_validates_slug_status_and_metadata(self):
        src = read_repo_file(TENANT_CREATE)

        assert 'isValidTenantSlug(slug)' in src
        assert 'isTenantStatus(status)' in src
        assert 'metadata must be an object' in src
        assert 'requireNonEmptyText(body.name' in src

    def test_tenant_create_rejects_duplicate_slug_before_insert(self):
        src = read_repo_file(TENANT_CREATE)

        assert "from('vault_tenants')" in src
        assert ".eq('slug', slug)" in src
        assert 'already exists' in src
        assert '409' in src

    def test_tenant_create_inserts_owner_membership_and_rolls_back_on_failure(self):
        src = read_repo_file(TENANT_CREATE)

        assert "from('vault_tenant_members')" in src
        assert "role: 'owner'" in src
        assert "status: 'active'" in src
        # Compensating delete keeps an owner-less tenant from being left behind.
        assert "from('vault_tenants').delete().eq('id', tenant.id)" in src


class TestTenantMemberAssignFunction:
    def test_tenant_member_assign_validates_inputs(self):
        src = read_repo_file(TENANT_MEMBER_ASSIGN)

        assert 'isValidTenantSlug(tenantSlug)' in src
        assert 'isTenantMemberRole(role)' in src
        assert 'isTenantMemberStatus(status)' in src
        assert "requireNonEmptyText(body.user_id, 'user_id')" in src

    def test_tenant_member_assign_blocks_inactive_tenants(self):
        src = read_repo_file(TENANT_MEMBER_ASSIGN)

        assert "tenant.status !== 'active'" in src
        assert 'not active' in src
        assert 'getTenantBySlug' in src

    def test_tenant_member_assign_authorizes_via_membership_not_metadata(self):
        src = read_repo_file(TENANT_MEMBER_ASSIGN)

        assert 'isPlatformAdmin(req)' in src
        assert 'hasTenantManagementRole(' in src
        assert 'Tenant owner or admin role required' in src
        assert 'user_metadata' not in src
        assert 'raw_user_meta_data' not in src
        assert 'auth.role()' not in src

    def test_tenant_member_assign_restricts_owner_role_assignment(self):
        src = read_repo_file(TENANT_MEMBER_ASSIGN)

        assert "role === 'owner'" in src
        assert 'Only platform admin or tenant owner may assign owner role' in src

    def test_tenant_member_assign_uses_upsert_on_tenant_user_unique(self):
        src = read_repo_file(TENANT_MEMBER_ASSIGN)

        assert "onConflict: 'tenant_id,user_id'" in src
        assert "from('vault_tenant_members')" in src


RAG_ANSWER = os.path.join(FUNCTIONS_DIR, 'rag-answer', 'index.ts')
QUERY_VECTOR_SQL = os.path.join(FUNCTIONS_DIR, 'query_vector_hybrid.sql')


class TestQueryVectorHybridTenantFilter:
    def test_function_reads_optional_tenant_id_from_request(self):
        sql = read_repo_file(QUERY_VECTOR_SQL)

        assert "req->>'tenant_id'" in sql
        # Empty string must not produce a bogus uuid cast.
        assert "NULLIF(req->>'tenant_id', '')" in sql

    def test_function_appends_tenant_clause_only_when_provided(self):
        sql = read_repo_file(QUERY_VECTOR_SQL)

        assert 'tenant_clause' in sql
        assert "WHEN tenant_filter IS NULL THEN ''" in sql
        assert "format('AND e.tenant_id = %L::uuid'" in sql

    def test_function_passes_tenant_clause_in_both_branches(self):
        sql = read_repo_file(QUERY_VECTOR_SQL)
        # Both the vector and text-only branches must inject the clause.
        assert sql.count('tenant_clause') >= 3  # decl + 2 format calls

    def test_dedicated_migration_exists_for_tenant_filter(self):
        sql = read_latest_migration('query_vector_hybrid_tenant_filter')

        assert 'CREATE OR REPLACE FUNCTION public.query_vector_hybrid' in sql
        assert "req->>'tenant_id'" in sql
        assert 'tenant_clause' in sql
        assert 'SECURITY DEFINER' in sql


class TestRagAnswerTenantAware:
    def test_rag_answer_defaults_tenant_slug_to_personal(self):
        src = read_repo_file(RAG_ANSWER)

        assert "DEFAULT_TENANT_SLUG = 'personal'" in src
        assert 'body.tenant_slug' in src

    def test_rag_answer_validates_slug_with_bootstrap_regex(self):
        src = read_repo_file(RAG_ANSWER)
        # Must mirror the vault_tenants slug CHECK constraint.
        assert '^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$' in src

    def test_rag_answer_requires_active_tenant(self):
        src = read_repo_file(RAG_ANSWER)

        assert "from('vault_tenants')" in src
        assert ".eq('status', 'active')" in src
        assert 'not found or not active' in src
        assert '404' in src

    def test_rag_answer_passes_tenant_id_to_rpc(self):
        src = read_repo_file(RAG_ANSWER)

        # The tenant_id must be part of the RPC payload, not just logged.
        assert 'tenant_id: tenantId' in src
        assert "supabase.rpc('query_vector_hybrid'" in src

    def test_rag_answer_echoes_tenant_in_response(self):
        src = read_repo_file(RAG_ANSWER)
        # The response should advertise which tenant served the query, for debug.
        assert 'tenant: { slug: requestedSlug, id: tenantId }' in src

    def test_rag_answer_never_reads_user_editable_metadata(self):
        src = read_repo_file(RAG_ANSWER)
        # Tenant resolution must not depend on user-controlled JWT fields.
        assert 'user_metadata' not in src
        assert 'raw_user_meta_data' not in src
        assert 'auth.role()' not in src


class TestTenantRlsEnforcementMigration:
    def test_migration_wraps_in_a_transaction(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        assert sql.lstrip().startswith('-- M8 Task 6')
        assert 'BEGIN;' in sql
        assert sql.rstrip().endswith('COMMIT;')

    def test_migration_sets_tenant_id_not_null_via_helper(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        assert 'ALTER COLUMN tenant_id SET NOT NULL' in sql

    def test_migration_replaces_global_uniques_with_composite(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        # Each replacement requires both a DROP and an ADD CONSTRAINT.
        assert "'vault_sections_slug_key'" in sql
        assert "'vault_sections_tenant_slug_key'" in sql
        assert "'vault_entries_obsidian_path_key'" in sql
        assert "'vault_entries_tenant_path_key'" in sql
        assert "'projects_slug_key'" in sql
        assert "'projects_tenant_slug_key'" in sql
        assert 'UNIQUE (tenant_id, %I)' in sql

    def test_migration_only_grants_authenticated_through_membership(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        assert 'TO authenticated' in sql
        assert 'TO service_role' in sql
        # The reusable predicate must be membership-based, not metadata-based.
        assert 'vault_tenant_members m' in sql
        assert 'm.user_id = (SELECT auth.uid())' in sql
        assert "m.status = 'active'" in sql
        assert "m.role IN ('owner', 'admin', 'member')" in sql

    def test_migration_never_trusts_user_editable_jwt_fields(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        assert 'auth.role()' not in sql
        assert 'user_metadata' not in sql
        assert 'raw_user_meta_data' not in sql

    def test_migration_revokes_anon_access_on_tenant_tables(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        # Anon must not read tenant-scoped data after the flip. Edge Functions
        # call as service_role; authenticated users go through membership.
        assert 'REVOKE ALL ON TABLE' in sql
        assert 'FROM anon' in sql

    def test_migration_keeps_service_role_unconstrained(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        assert 'service_all ON' in sql
        assert 'USING (true) WITH CHECK (true)' in sql

    def test_migration_covers_every_scoped_table_from_the_plan(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        # Mirrors the table list in issues/month-8-tenant-isolation-plan.md.
        for table in [
            'vault_sections', 'vault_entries', 'vault_chunks', 'vault_embeddings',
            'vault_transactions', 'vault_snapshots', 'vault_profile', 'vault_journal',
            'vault_events', 'vault_memories', 'vault_feedback', 'vault_relations',
            'projects', 'sessions', 'claude_memory',
        ]:
            assert f"to_regclass('public.{table}')" in sql, f"Missing flip for {table}"

    def test_migration_does_not_flip_global_registry_tables(self):
        sql = read_latest_migration('tenant_rls_enforcement')
        # These remain global per the M8 isolation plan.
        for table in ['vault_models', 'tools_registry', 'resources_registry',
                      'context_profiles', 'agent_permissions']:
            assert f"to_regclass('public.{table}')" not in sql, f"Unexpected flip for global table {table}"
