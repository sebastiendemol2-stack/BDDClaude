---
title: "Vector‑first Search"
date: 2026-05-22
tags: [search, vector]
type: concept
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

Voir aussi : [[Intelligence/cognitive-runtime]], [[Intelligence/model-registry]]
# Vector‑first Search

This document describes the new hybrid search capability introduced in the **0 → 6 Months Execution Plan**.

## Overview

- **Hybrid RPC**: `public.query_vector_hybrid(json)` – combines vector similarity (using the `pgvector` extension) with BM25 full‑text search.
- **Fallback**: If no embedding is supplied, the function automatically falls back to pure BM25.
- **Scoring**: Weighted blend (70 % vector similarity, 30 % BM25) – configurable in the function body.
- **Client wrapper**: `supabase/queryVector` (TypeScript) – easy to call from the frontend or any Node / Deno app.

## Usage (SQL)

```sql
SELECT * FROM public.query_vector_hybrid(
  '{"query":"machine learning", "embedding":"[0.12,0.34,...]", "limit":5}'::json
);
```

If `embedding` is omitted, the call devolves to a regular text search.

## Usage (TypeScript)

```ts
import { queryVector } from './supabase/queryVector';

const results = await queryVector({
  supabaseUrl: process.env.SUPABASE_URL!,
  supabaseKey: process.env.SUPABASE_ANON_KEY!,
  query: 'machine learning',
  embedding: [0.12, 0.34, /* … */],
  limit: 5,
});
```

## Deployment steps (summary)

1. **Enable `pgvector`** on the Supabase project (via dashboard or edge‑function migration).
2. **Run migration** `2026-05-22_add_pgvector.sql` – adds the extension and the `embedding_vector` column.
3. **Back‑fill** existing embeddings with `scripts/migrate_vector_embeddings.py` (run with `--dry-run` first).
4. **Create RPC** – apply `supabase/functions/query_vector_hybrid.sql`.
5. **Add client wrapper** – `supabase/queryVector.ts`.
6. **Write integration test** – `test_vector_query.py` (covers both vector and fallback paths).
7. **Update CI** – ensure the new migration, RPC, and test run on every push.
8. **Document** – this page.

## Error codes

| Code | Meaning | Recovery |
|------|---------|----------|
| `400` | Invalid JSON payload or missing `query` field | Check request body format |
| `500` | Internal server error (DB timeout, extension not loaded) | Check pgvector extension status |
| `503` | Embedding provider unavailable | Falls back to BM25 automatically |

## Rate limits

- **RPC**: 100 req/min per IP (Supabase Postgres); 429 if exceeded
- **Edge Function** (`/functions/v1/query`): 50 req/min (configurable in Supabase dashboard)
- **Embedding generation**: 10 req/s via Jan (localhost); 3000 req/min via OpenAI API

## Monitoring & Alerts

- Alert if the `embedding_vector` column contains > 5 % NULLs after back‑fill.
- Alert on RPC latency > 200 ms (Prometheus metric from `/metrics`).

---
