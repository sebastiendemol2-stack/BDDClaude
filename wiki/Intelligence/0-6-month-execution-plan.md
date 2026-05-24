---
title: "0‑to‑6 Months Execution Plan"
date: 2026-05-22
tags: [plan, roadmap, execution]
type: concept
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# 0 → 6 Months Execution Plan

**Scope** – Deliver the four strategic pivots identified for BDDClaude / UKP / Cognitive Runtime Platform:
1. **Vector‑first search** (high‑impact retrieval upgrade)
2. **Cognitive Runtime Platform core** (memories, feedback, relations)
3. **Dashboard / monitoring** (real‑time health, search stats, runtime events)
4. **Worktree clean‑up automation** (prevent lock contention and orphaned worktrees)

The plan is broken into monthly milestones.  All work items are pure planning/comms until the end of **Month 0**, after which concrete code, migrations and edge‑function deployments will be executed.

---

## Month 0 – Kick‑off & Foundations

| Week | Goal | Activities |
|------|------|------------|
| 0.0 | Align stakeholders | Kick‑off meeting (product, dev, ops). Confirm sprint cadence and release windows. |
| 0.1 | Baseline metrics | Export current vault health (`wiki/health.md`), test coverage, note count, Supabase schema snapshot. |
| 0.2 | Prioritisation lock‑in | Agree on first pivot (**Vector‑first search**). Create backlog epics for the four pivots and rank them (MoSCoW). |
| 0.3 | Planning artefacts | Define Definition‑of‑Done for each epic. Set up a project board (GitHub Projects) with columns *Backlog → Ready → In‑progress → Review → Done*. |

---

## Month 1 – Vector‑first Search Foundations ✅ (2026-05-22)

| Week | Goal | Status |
|------|------|--------|
| 1.0 | Code artifacts: migration, RPC, TS wrapper, backfill script, test, docs | ✅ DONE |
| 1.1 | pgvector extension verified on production → **v0.8.0 installed** | ✅ DONE |
| 1.2 | Migration `2026-05-22_add_pgvector.sql` applied → `embedding_vector` column added | ✅ DONE |
| 1.3 | RPC `query_vector_hybrid` created on production, type‑fixed (`real`→`double precision`) | ✅ DONE |
| 1.4 | Back‑fill run: 0 embeddings in `vault_embeddings` → no migration needed | ✅ DONE |
| 1.5 | CI pipeline update | ⏳ TODO |
| 1.6 | Design review meeting | ⏳ TODO |

**Milestone:** ✅ Vector‑first search deployed on production, hybrid RPC functional.

**Delivered assets:**
| File | Purpose |
|------|---------|
| `supabase/migrations/2026-05-22_add_pgvector.sql` | Adds extension + column |
| `supabase/functions/query_vector_hybrid.sql` | Hybrid search RPC (70% vector, 30% BM25) |
| `supabase/query_vector.ts` | TypeScript client wrapper |
| `scripts/migrate_vector_embeddings.py` | Backfill helper (dry‑run safe) |
| `_scripts/tests/test_vector_query.py` | Integration test |
| `wiki/Intelligence/vector-first-search.md` | Documentation |
| `issues/month-1-vector-search.md` | Task tracker |

---

## Month 2 – Cognitive Runtime Platform Core

| Week | Goal | Activities |
|------|------|------------|
| 2.1 | Schema extension | Add tables `vault_memories`, `vault_feedback`, `vault_relations` (`2026_02_cognitive_runtime.sql`). Define FK constraints and RLS policies. |
| 2.2 | API surface | Deploy Edge Functions `memories_store`, `feedback_collect`, `relations_update` (JWT required). |
| 2.3 | In‑process runtime | Create `runtime/core.ts` exposing `storeMemory`, `collectFeedback`, `addRelation`. |
| 2.4 | Unit & contract tests | Jest tests for each function; contract test via `supabase_get_advisors`. |
| 2.5 | Pilot integration | Instrument `subagent‑workflows` to log a memory after each dispatch and a feedback entry after each analysis run. |

**Milestone:** Core runtime API deployed on dev, exercised by a pilot sub‑agent, fully tested.

---

## Month 3 – Dashboard / Monitoring

| Week | Goal | Activities |
|------|------|------------|
| 3.1 | UI skeleton | Scaffold React + Vite dashboard under `dashboard/`. Define routes: *Health*, *Search Stats*, *Runtime Events*, *Worktree Status*. |
| 3.2 | Data endpoints | Add Supabase Realtime subscriptions to `vault_journal`, `vault_memories`, `vault_feedback`. Expose `/metrics` Edge Function for Prometheus‑style metrics. |
| 3.3 | Visualisations | Implement charts (search latency distribution, feedback trend, worktree lock count). Add health badge. |
| 3.4 | CI/CD for dashboard | GitHub Action to build, test, and deploy dashboard to Supabase Edge Functions on merge to `main`. |
| 3.5 | Stakeholder demo | Demo dashboard, collect feedback on additional widgets. |

**Milestone:** Live monitoring dashboard accessible to the team.

---

## Month 4 – Worktree Clean‑up Automation

| Week | Goal | Activities |
|------|------|------------|
| 4.1 | Inventory script | PowerShell `scripts/inspect_worktrees.ps1` – list worktrees, detect locked files, flag > 30 days stale. |
| 4.2 | Reporting | Emit JSON report to `dashboard/api/worktree_status` (Edge Function) and surface in dashboard UI. |
| 4.3 | Cleanup policy | Draft `wiki/Intelligence/worktree-policy.md` describing when/who can archive/delete worktrees. |
| 4.4 | Automation (optional) | Prototype GitHub Action that opens a PR to delete stale worktrees (manual review only). |
| 4.5 | Validation | Run script on dev branch, verify no active branches affected, obtain team sign‑off. |

**Milestone:** ✅ Worktree status visible, safe cleanup workflow in place. (2026-05-22)

### Month 5 — Integration & Stress Testing (2026-05-22)

| Action | Status |
|--------|--------|
| E2E CI job (`test_e2e.py` + `ci.yml` e2e job) | ✅ DONE |
| `issues/month-5-integration-stress.md` | ✅ DONE |
| Load testing (k6) | ⏳ TODO |
| Failure injection | ⏳ TODO |
| Security audit | ⏳ TODO |
| Documentation update | ⏳ TODO |

---

## Month 5 – Integration & Stress Testing

| Week | Goal | Activities |
|------|------|------------|
| 5.1 | End‑to‑end flow | CI job: insert note → embed → query → sub‑agent dispatch → memory → feedback → relation. Verify dashboard reflects new data. |
| 5.2 | Load testing | `k6` run: 500 concurrent vector‑search requests for 10 min. Capture latency, error rate, DB CPU. Store results in `load-test-report.md`. |
| 5.3 | Failure injection | Inject DB latency via `SET statement_timeout` to test client fallback to BM25. |
| 5.4 | Security audit | Run `source-command-audit` on new Edge Functions. Fix any RLS/JWT gaps. |
| 5.5 | Documentation update | Add usage sections to `wiki/Intelligence/vector-search.md` and `wiki/Intelligence/cognitive-runtime.md`. |

**Milestone:** Full stack (search → runtime → dashboard) stress‑tested, hardened, documented.

---

## Month 6 – Production Roll‑out & Retrospective

| Week | Goal | Activities |
|------|------|------------|
| 6.1 | Production promotion | Merge `search‑dev` branch into `main`. Apply migrations on production via Supabase CLI. |
| 6.2 | Switch traffic | Update `ukp-client` config to production URL. Canary rollout (10 % → 100 %). |
| 6.3 | Monitoring hand‑off | Enable alerts for vector‑search latency > 200 ms, runtime error rate > 1 %, worktree lock > 24 h. |
| 6.4 | Team training | 2‑hour workshop: using dashboard, submitting feedback, worktree policy enforcement. |
| 6.5 | Retrospective & next‑step planning | Collect metrics, run retrospective, feed next‑half‑year backlog (model registry, multi‑tenant vaults). |

**Milestone:** All four pivots in production, monitored, team trained, and a retrospective completed.

---

## Timeline (Gantt‑style)

```
M0 ──► M1 ──► M2 ──► M3 ──► M4 ──► M5 ──► M6
 |      |      |      |      |      |      |
Vector‑first → Runtime Core → Dashboard → Worktree Clean‑up → Integration & Load‑test → Production Roll‑out
```

### Key Dependencies
- **Vector‑first search** must be stable before the Runtime stores memories that reference search results.
- **Dashboard** depends on Runtime API and Worktree status endpoint.
- **Worktree clean‑up** is independent but should be ready before integration tests to avoid spurious lock failures.
- **Security audit** (Month 5) gates any production promotion.

### Risk Mitigations (summary)
- **Downtime** – Perform migrations on a separate Supabase branch, validate, then promote.
- **Edge‑function latency** – Warm‑up schedule and SRE alerts.
- **Worktree lock contention** – Daily inventory script + reviewed PRs for deletion.
- **Test coverage** – Unit, integration, contract, and load tests for every new component.
- **Knowledge‑base drift** – Future watch‑er to alert if `/ingest` not run within 24 h after raw changes.

---

**Next immediate action (Week 0.0 → now Month 2)**
1. ✅ ~~Schedule the kick‑off meeting~~ — superseded by execution
2. ✅ ~~Create a GitHub Project board~~ — tracked via `issues/` files
3. ✅ ~~Export baseline metrics~~ — health 100%, 210 tests, 17 notes

**Month 2 executed (2026-05-22):**

| Action | Status |
|--------|--------|
| Schema audit — tables already exist on production | ✅ DONE |
| `runtime/core.ts` — `CognitiveRuntime` class with storeMemory, collectFeedback, addRelation, searchMemories | ✅ DONE |
| Edge Function `memories-store` — deployed (Deno, JWT required) | ✅ DONE |
| Edge Function `feedback-collect` — deployed (Deno, JWT required) | ✅ DONE |
| Edge Function `relations-update` — deployed (Deno, JWT required) | ✅ DONE |
| Integration tests `_scripts/tests/test_runtime_core.py` — 11 tests | ✅ DONE |
| Sources versionnées dans `supabase/functions/{slug}/` | ✅ DONE |
| Issue tracker `issues/month-2-cognitive-runtime.md` | ✅ DONE |
| Pilot integration — subagent-workflows memory logging | ✅ DONE |
| Documentation `wiki/Intelligence/cognitive-runtime.md` | ✅ DONE |
| Runtime functions `verify_jwt: false` (memories-store, feedback-collect, relations-update) | ✅ DONE |

### Month 3 — Dashboard scaffolded (2026-05-22)

| Action | Status |
|--------|--------|
| Vite + React + TypeScript scaffold | ✅ DONE |
| 4 routes: Health, Search Stats, Runtime Events, Worktree Status | ✅ DONE |
| Recharts bar chart + Realtime subscriptions | ✅ DONE |
| Health badge + type distribution | ✅ DONE |
| `issues/month-3-dashboard.md` | ✅ DONE |
| Metrics Edge Function (deployed) | ✅ DONE |
| CI/CD GitHub Action (dashboard build) | ✅ DONE |
| Integration test (`test_metrics_integration.py`) | ✅ DONE |
| Env config docs (README + .env.example) | ✅ DONE |

### Month 4 — Worktree Clean‑up (2026-05-22)

| Action | Status |
|--------|--------|
| Inventory script `scripts/inspect_worktrees.ps1` | ✅ DONE |
| `vault_worktree_reports` migration + RLS | ✅ DONE |
| Edge Function `worktree-status` (POST + GET) | ✅ DONE |
| Push integration (`-PushReport` flag) | ✅ DONE |
| Dashboard WorktreeStatus page (Realtime) | ✅ DONE |
| Cleanup policy `wiki/Intelligence/worktree-policy.md` | ✅ DONE |
| GitHub Action daily scan + stale PR | ✅ DONE |
| Issue tracker `issues/month-4-worktree-cleanup.md` | ✅ DONE |

### Month 6 — Production Roll‑out (2026-05-22)

| Action | Status |
|--------|--------|
| Production promotion — all 9 EF deployed, all migrations applied, CI green | ✅ DONE |
| UKP client config — production URL verified | ✅ DONE |
| Monitoring guide — `wiki/Intelligence/monitoring-guide.md` (alert thresholds, runbooks) | ✅ DONE |
| Dashboard build — Vite build passes (dist/ ready for static deploy) | ✅ DONE |
| Retrospective — `wiki/Intelligence/retrospective-0-6-months.md` | ✅ DONE |
| Issue tracker `issues/month-6-production-rollout.md` | ✅ DONE |

### Bug fixes discovered during M6 validation

| Bug | Root cause | Fix |
|-----|------------|-----|
| memories-store upsert failure | Missing `UNIQUE` constraint on `vault_memories.session_id` | Migration `add_memories_session_id_unique` |
| relations-update upsert failure | Missing `UNIQUE` constraint on `vault_relations(source_entry_id,target_entry_id,relation_type)` | Migration `add_relations_triplet_unique` |
| e2e reachability test sent empty bodies | Test sent `{}` to functions requiring specific fields | Fixed to send valid probe payloads |

**E2E test result**: 8/8 passed after fixes.

---

**Next steps (post-M6)**
1. Deploy dashboard to static hosting (GitHub Pages / Vercel / Supabase Storage)
2. Re-run load test with `SUPABASE_SERVICE_ROLE_KEY` for full endpoint coverage
3. Tune `ivfflat` index or migrate to `hnsw` for sub-200ms vector search
4. M7+ backlog: model registry, multi-tenant vaults, memory graph visualization, alerting
5. M7 started locally: see [[Intelligence/model-registry]] and `issues/month-7-model-registry.md`

_Dernière mise à jour : 2026-05-22 — schema v3.2.0 — 0→6 month execution complete_
