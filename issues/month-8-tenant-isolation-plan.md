---
title: "M8 Tenant Isolation Backfill Plan"
date: 2026-05-24
tags: [plan, multi-tenant, rls, backfill]
type: decision
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# M8 Tenant Isolation Backfill Plan

This plan defines the migration order before any existing vault table receives a tenant policy. It is intentionally separate from the bootstrap migration so the destructive and behavior-changing steps can be reviewed before execution.

## Policy

- `vault_models`, `tools_registry`, `resources_registry`, `context_profiles`, and `agent_permissions` remain global in M8.
- Direct table reads by `anon` must not be expanded for tenant-scoped data.
- Existing anon reads on vault data should be removed only after dashboard and Edge Function reads are tenant-aware.
- Tenant-scoped policies must use membership rows plus `(SELECT auth.uid())`.
- Policies must not use `auth.role()`, `user_metadata`, or `raw_user_meta_data`.

## Phase 1 - Add Nullable Columns

Add nullable `tenant_id uuid references public.vault_tenants(id)` to these tables only:

| Table | Scope | Backfill Source |
| --- | --- | --- |
| `vault_sections` | tenant catalog | default `personal` tenant |
| `vault_entries` | primary notes | default `personal` tenant |
| `vault_chunks` | derived note chunks | parent `vault_entries.tenant_id` |
| `vault_embeddings` | derived vectors | parent entry, then parent chunk |
| `vault_transactions` | ingest audit | default `personal` tenant |
| `vault_snapshots` | graph snapshots | default `personal` tenant |
| `vault_profile` | profile data | default `personal` tenant |
| `vault_journal` | journal rows | default `personal` tenant |
| `vault_events` | runtime event log | default `personal` tenant |
| `vault_memories` | runtime memory | default `personal` tenant initially |
| `vault_feedback` | feedback pipeline | default `personal` tenant initially |
| `vault_relations` | graph edges | default `personal` tenant initially |
| `projects` | agent project namespace | default `personal` tenant |
| `sessions` | agent sessions | parent `projects.tenant_id` |
| `claude_memory` | agent memory | parent `projects.tenant_id` |

Required indexes:

- `idx_<table>_tenant` for direct tenant filters.
- Composite future uniques only after duplicate checks pass.

## Phase 2 - Backfill

1. Resolve the `personal` tenant id from `vault_tenants.slug = 'personal'`.
2. Backfill direct tables to `personal`.
3. Backfill derived tables from parents:
   - `vault_chunks` from `vault_entries`.
   - `vault_embeddings` from `vault_entries`, falling back to `vault_chunks`.
   - `sessions` and `claude_memory` from `projects`.
4. Verify every scoped table has `tenant_id IS NOT NULL`.
5. Only then add `NOT NULL` constraints.

## Phase 3 - Constraint Review

Review these global uniqueness constraints before replacing them:

| Current Constraint | Future Shape | Risk |
| --- | --- | --- |
| `vault_sections.slug` unique | `(tenant_id, slug)` | section slug collisions across tenants |
| `vault_entries.obsidian_path` unique | `(tenant_id, obsidian_path)` | duplicate note paths across tenants |
| `projects.slug` unique | `(tenant_id, slug)` | project namespace collisions |

Do not drop global uniqueness until duplicate checks confirm that the replacement constraints can be added in the same transaction.

## Phase 4 - RLS Flip

Use a reusable predicate shape:

```sql
EXISTS (
  SELECT 1
  FROM public.vault_tenant_members m
  WHERE m.tenant_id = <table>.tenant_id
    AND m.user_id = (SELECT auth.uid())
    AND m.status = 'active'
)
```

Policy order:

1. Keep `service_role` `FOR ALL` policies.
2. Add authenticated membership `SELECT` policies.
3. Add authenticated write policies only where user writes are product requirements.
4. Remove or narrow anon policies after Edge Function reads are tenant-aware.

## Phase 5 - Application Updates

- `sync.py push/pull/status` must include a tenant argument or default to `personal`. **DONE** — `--tenant <slug>` or `VAULT_TENANT` env var, default `personal`; push refuses `sensitivity ∈ {private, sensitive}`; pull/status/push filter REST reads by `tenant_id`.
- `rag-answer`, `query_vector_hybrid`, and dashboard reads must filter by tenant. **PARTIAL** — `query_vector_hybrid` accepts an optional `tenant_id` in the request payload (no behavior change when absent, for back-compat). `rag-answer` resolves `body.tenant_slug` (default `personal`) against `vault_tenants` (status=active), rejects unknown/inactive, and forwards `tenant_id` to the RPC. Dashboard selector still TODO.
- Export/import scripts must require source and target tenant slugs. **DONE** — `_scripts/tenant_bundle.py` with `export --tenant <slug> --out <dir>` and `import --tenant <slug> --in <dir> [--on-conflict skip|overwrite]`. Bundle v1 = `manifest.json` (schema_version) + `tables/{vault_sections,vault_entries}.jsonl` + `markdown/<obsidian_path>`. Import rewrites `tenant_id`, strips `id`/`created_at`/`updated_at`, blocks cross-tenant `obsidian_path` collisions unless overwrite is requested.
- Dashboard should persist the selected tenant locally, not in user-editable auth metadata. **TODO**

## Rollback

- Before RLS flip: drop nullable `tenant_id` columns and indexes.
- After RLS flip: restore previous policies from migration backup, then drop tenant columns only after service-role export confirms row counts.

## Acceptance Gate

The tenant-column migration can proceed only when:

- bootstrap migration is applied;
- default `personal` tenant exists;
- duplicate checks for future composite uniques pass;
- dashboard and Edge Function reads have a tenant filter path;
- static tests verify no `auth.role()` or user-editable metadata in tenant RLS.
