---
title: "Month‑5 Integration & Stress Testing — Detailed Tasks"
date: 2026-05-22
tags: [plan, roadmap, testing]
type: decision
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# Month‑5 Integration & Stress Testing — Detailed Tasks

## Tasks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| 1 | **E2E CI job** — `test_e2e.py` (9 tests) + `ci.yml` e2e job (master only) | DevOps | DONE |
| 2 | **Load testing** — k6 run (10 VU, 20s): metrics 100%, worktree 100%, memories-store 0% (anon key). Report saved. | QA | DONE |
| 3 | **Failure injection** — `test_failure_injection.py` (4 tests: BM25 fallback, invalid embedding, empty query, SQL injection guard) + `supabase/query_vector_fallback.ts` (client-side retry) | QA | DONE |
| 4 | **Security audit** — run on Edge Functions (score 4/10, 2 RLS fixes applied via migration) | Security | DONE |
| 5 | **Documentation** — update vector-search.md + cognitive-runtime.md (error codes, rate limits) | Tech Writer | DONE |

## Acceptance Criteria

- End-to-end CI job passes on master: all Edge Functions reachable, data flows through
- Load test report: p95 latency 1.3s (exceeds 200ms target — cold starts + DB index tuning needed)
- Client gracefully falls back to BM25 on DB timeout
- Security audit passes with no critical/high findings
- Documentation covers usage, error codes, rate limits

> ⚠️ Load test p95 latency (1.3s) exceeds acceptance target (200ms). Root causes: cold start for Edge Functions, no connection pooling on DB, ivfflat index may need tuning. Tracked for next cycle.
