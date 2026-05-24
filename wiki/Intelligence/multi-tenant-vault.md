---
title: "Multi-tenant Vaults"
date: 2026-05-24
tags: [multi-tenant, vault, supabase, rls]
type: concept
status: active
confidence: high
source_type: synthesis
freshness: evergreen
sensitivity: internal
---

# Multi-tenant Vaults

Multi-tenant Vaults are the M8 continuation after [[Intelligence/model-registry]]. The goal is to host multiple independent vaults in the same Supabase project while preserving export/import, RLS isolation, and the existing single-user `personal` vault.

## First Slice

The M8 bootstrap is intentionally non-destructive:

- Create `vault_tenants` for tenant metadata.
- Create `vault_tenant_members` for user-to-tenant authorization.
- Seed the default `personal` tenant for current data.
- Add RLS and explicit grants for the new tables.
- Do not alter `vault_entries`, `vault_embeddings`, `vault_chunks`, or runtime tables yet.

This keeps the migration safe while the tenant backfill plan is reviewed.

## Second Slice

The second M8 migration adds tenant identifiers without enforcing them yet:

- Add nullable `tenant_id` columns to scoped vault and runtime tables.
- Create direct `tenant_id` indexes.
- Backfill current data to the default `personal` tenant.
- Derive child rows from parent tables where possible:
  - `vault_chunks` from `vault_entries`;
  - `vault_embeddings` from `vault_entries`, then `vault_chunks`;
  - `sessions` and `claude_memory` from `projects`.
- Do not change RLS policies yet.
- Do not add `NOT NULL` constraints yet.
- Do not drop global uniqueness constraints yet.

This creates the data shape needed for tenant-aware application reads before the policy flip.

## Security Model

Tenant authorization is membership-based:

- `vault_tenant_members.user_id` maps to `auth.uid()`.
- Policies use `TO authenticated` and `TO service_role`.
- Policies do not use deprecated `auth.role()`.
- Policies do not authorize from user-editable `user_metadata` or `raw_user_meta_data`.
- Write access to tenant metadata remains service-role only until provisioning APIs are implemented.

## Planned Tenant Columns

The next migration should add `tenant_id` only after the backfill order is approved.

Candidate tables:

| Table | Reason | Backfill |
| --- | --- | --- |
| `vault_entries` | Primary note records | Set to `personal` |
| `vault_chunks` | Derived from entries | Copy from parent entry |
| `vault_embeddings` | Derived from entry/chunk/model | Copy from parent entry or chunk |
| `vault_transactions` | Promotion audit | Set to `personal` for historical rows |
| `vault_snapshots` | Graph snapshots | Set to `personal` for historical rows |
| `vault_memories` | Runtime memory | Set by project/session tenant mapping |
| `vault_feedback` | Runtime feedback | Set by source event/session tenant |
| `vault_relations` | Graph edges | Tenant-scoped graph traversal |
| `vault_models` | Probably global, not tenant-specific initially | No tenant column in M8 unless model policy changes |

## RLS Plan

Future policies should follow this shape:

```sql
TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM public.vault_tenant_members m
    WHERE m.tenant_id = <table>.tenant_id
      AND m.user_id = (SELECT auth.uid())
      AND m.status = 'active'
  )
)
```

Admin writes should go through Edge Functions using service-role credentials server-side, with request authorization checked before mutation.

## Export/import Plan

Export should produce a deterministic bundle:

- `manifest.json` with tenant slug, schema version, counts, and content hash.
- Markdown notes from `vault_entries`, excluding private/sensitive rows unless explicitly requested by a local-only export.
- Chunk and embedding metadata when needed for offline restore.
- Link graph and alias registry references.

Import should validate frontmatter, detect duplicate `obsidian_path`, preserve source hashes, and write all rows under the target tenant.

## Open Decisions

- Whether runtime tables (`vault_memories`, `vault_feedback`, `vault_relations`) should use tenant membership directly or inherit tenant from `project_slug`.
- Whether `vault_models` remains global or supports tenant-specific model policy overrides later.
- Whether dashboard tenant selection should persist in local storage or user app metadata.

## Voir aussi

- [[Intelligence/next-steps-beyond-6-months]]
- [[Intelligence/cognitive-runtime]]
- [[Intelligence/vector-first-search]]
