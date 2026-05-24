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
