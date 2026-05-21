---
title: "Vector Search Implementation Plan"
date: 2026-05-21
priority: P2
status: draft
---

## Current State

- **`query_vector_hybrid` RPC** (`schema/migrations/20260521_ukp_v1_2_reconcile.sql:13`) is FTS-only — uses `plainto_tsquery('french')` on `vault_entries.content_search`. It never touches the `vault_embeddings` table. The `_method` field always returns `'fts'`.
- **`vault_embeddings` table** (`schema/supabase.sql:231`) has `embedding vector(1536)`, `provider`, `model`, `embedding_dim`, `embedding_hash`, `pipeline_version`, `chunking_strategy`, `tokenizer_hash` — schema is ready. An `ivfflat` index (`idx_embeddings_vector`) exists. **But the table is empty** — no pipeline populates it.
- **`vault_chunks` table** exists (FK from `vault_embeddings`) — chunking infrastructure is wired but unused.
- **`ukp-query` Edge Function** (`supabase/functions/ukp-query/index.ts:40`) calls `query_vector_hybrid` thinking it gets vector results, then merges with `search_vault` using `fts_weight`/`vector_weight`. In reality, both calls return FTS results — the "hybrid merge" is FTS + duplicate FTS.
- **`rag_bridge.py`** does real embeddings (via Jan at `localhost:1337`) but locally — chunks markdown files, calls `_embed_text`, computes cosine similarity in-process. Disconnected from Supabase pipeline.
- **`memory_store.py`** embeds session summaries into `vault_memories` (separate table) via Jan, also does client-side cosine similarity.

## Required Steps

### 1. Real `query_vector_hybrid` RPC
Rewrite the function to:
- Accept `query_text`, `match_count`, `fts_weight`, `vector_weight`
- Embed `query_text` via a Supabase-side embedding call (pgvector extension has no embedding function — embedding must happen client-side or via Edge Function)
- **Approach**: Embed query in the Edge Function (via OpenAI API or Jan), then pass the vector to the RPC
- Perform `vault_embeddings.embedding <=> query_embedding` (cosine distance)
- JOIN with `vault_entries` for metadata + status filter
- Combine FTS rank + vector similarity via RRF (Reciprocal Rank Fusion) or weighted normalization

```sql
create or replace function query_vector_hybrid(
    query_text text,
    query_embedding vector(1536),
    match_count int default 10,
    fts_weight real default 0.4,
    vector_weight real default 0.6
) returns jsonb ...
```

### 2. Embedding pipeline script (`_scripts/embed.py`)
Create a script that:
- Reads all active `vault_entries` from Supabase
- Chunks content by section (reuse `chunk_by_sections` from `rag_bridge.py` or `vault_chunks`)
- Embeds each chunk via Jan (`/v1/embeddings`) or OpenAI API
- Upserts into `vault_embeddings` (dedup by `entry_id + chunk_id + model`)
- Logs progress, skips unchanged hashes
- Supports `--backfill` and `--incremental` modes

### 3. Update `ukp-query` Edge Function
- Embed the query text via OpenAI/Jan before calling the RPC
- Pass the resulting `vector(1536)` to the new `query_vector_hybrid`
- Remove the fake vector branch that calls `query_vector_hybrid` without an embedding
- Keep the FTS fallback when embedding is unavailable

### 4. Incremental trigger (post-ingest)
- When `/ingest` creates/updates entries, trigger embedding generation
- Add a `needs_embedding` flag or use `vault_events` to queue embedding jobs
- Option: add an Edge Function webhook on `vault_entries` INSERT/UPDATE

### 5. Backfill job
- Run `_scripts/embed.py --backfill` to populate `vault_embeddings` for all ~250+ entries
- Batch in groups of 10 to avoid rate limits
- Expected: ~500-1000 chunks total (each entry ~2-4 sections)
- Estimate: ~2-5 min with Jan local, ~30s with OpenAI API

## Architecture Decision

| Concern | Decision |
|---------|----------|
| Embedding source | Jan local (OpenAI-compatible), fallback to OpenAI API |
| Embedding model | `text-embedding-ada-002` (1536d) — matches existing `vector(1536)` |
| Where embedding happens | Edge Function (for queries), script (for indexing) |
| Hybrid fusion | Weighted sum (configurable via `context_profiles.retrieval_config`) |
| Vector index type | `ivfflat` (existing) — upgrade to `hnsw` if >10k embeddings |

## Dependencies

- Jan running locally on port 1337 (or OpenAI API key in `.env`)
- pgvector extension loaded (already enabled)
- `vault_embeddings` table + index (already exist)
- `vault_chunks` data populated (currently empty)
