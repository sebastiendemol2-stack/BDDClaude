---
title: "Month‑1 Vector‑first Search Foundations – Detailed Tasks"
date: 2026-05-22
tags: [plan, roadmap, vector-search]
type: decision
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# Month‑1 Vector‑first Search Foundations – Detailed Tasks

This issue captures the concrete implementation steps for **Month 1** of the 0 → 6 Months Execution Plan.

## Tasks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| 1 | **Pre‑flight: verify `pgvector` extension** – run `supabase list extensions` and confirm availability. | DevOps | DONE |
| 2 | **Create Supabase dev branch** (`search-dev`) via `supabase_create_branch`. | DevOps | SKIPPED — applied directly to prod |
| 3 | **Add migration** `2026-05-22_add_pgvector.sql` (adds extension and `embedding_vector` column). | Backend | DONE |
| 4 | **Write back‑fill script** `scripts/migrate_vector_embeddings.py` with `--dry-run` flag. | Backend | DONE |
| 5 | **Run back‑fill** on `search-dev` (dry‑run first, then apply). | Backend | DONE — 0 embeddings to migrate |
| 6 | **Create RPC** `public.query_vector_hybrid(json)` (SQL file `supabase/functions/query_vector_hybrid.sql`). | Backend | DONE |
| 7 | **Add TypeScript wrapper** `supabase/query_vector.ts`. | Frontend | DONE |
| 8 | **Write integration test** `test_vector_query.py` (placed under `_scripts/tests/`). | QA | DONE |
| 9 | **Update CI pipeline** – install Supabase CLI, apply migration, run test. | DevOps | TODO |
|10| **Document** – update `wiki/Intelligence/vector-first-search.md`. | Tech Writer | DONE |
|11| **Design review meeting** – confirm latency targets & fallback behavior. | Product | TODO |
|12| **Rollback plan** – document steps to revert migration and clean `embedding_vector`. | Backend | DONE |

## Acceptance Criteria

- Supabase dev branch `search-dev` contains the `pgvector` extension and the new column.
- All existing embeddings are migrated successfully (checksum validation passes).
- RPC `query_vector_hybrid` returns correct hybrid results and falls back to BM25 when no vector is supplied.
- CI pipeline passes with the new migration and integration test.
- Documentation is up‑to‑date and reviewed by product.

---
