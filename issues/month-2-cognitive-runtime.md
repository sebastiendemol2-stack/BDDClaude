---
title: "Month‑2 Cognitive Runtime Platform Core — Detailed Tasks"
date: 2026-05-22
tags: [plan, roadmap, runtime]
type: decision
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# Month‑2 Cognitive Runtime Platform Core — Detailed Tasks

**State at kick‑off:** Schema tables (`vault_memories`, `vault_feedback`, `vault_relations`) already deployed. Infrastructure `runtime/` scaffold exists. Missing: API layer, core runtime module, tests, pilot integration.

## Tasks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| 1 | **Schema audit** — verify vault_memories, vault_feedback, vault_relations have all required FKs, indexes, RLS | DevOps | DONE |
| 2 | **Create `runtime/core.ts`** — storeMemory, collectFeedback, addRelation functions (TypeScript, Supabase client) | Backend | DONE |
| 3 | **Edge Function: `memories-store`** — deploy Deno edge function wrapping vault_memories upsert + vector search | Backend | DONE |
| 4 | **Edge Function: `feedback-collect`** — deploy Deno edge function wrapping vault_feedback insert with dedup | Backend | DONE |
| 5 | **Edge Function: `relations-update`** — deploy Deno edge function wrapping vault_relations upsert | Backend | DONE |
| 6 | **Integration tests** — `_scripts/tests/test_runtime_core.py` with 11 tests (store, feedback, relations, full cycle) | QA | DONE |
| 7 | **Pilot integration** — instrument subagent-workflows to log memory after dispatch + feedback after analysis | Frontend | DONE |
| 8 | **Documentation** — update `wiki/Intelligence/cognitive-runtime.md` | Tech Writer | TODO |
| 9 | **JWT config** — set `verify_jwt: false` on runtime functions (consistent with UKP functions) | DevOps | DONE |

## Acceptance Criteria

- `runtime/core.ts` exports storeMemory, collectFeedback, addRelation with typed params
- Each Edge Function is deployed and responds to a valid JWT-authenticated request
- Integration test covers: dispatch → memory → feedback → relation → verify via dashboard
- CI pipeline includes the new tests
- Documentation covers usage, error codes, rate limits
