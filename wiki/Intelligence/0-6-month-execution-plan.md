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

## Month 1 – Vector‑first Search Foundations

| Week | Goal | Activities |
|------|------|------------|
| 1.1 | Environment prep | Provision a Supabase dev branch (`supabase_create_branch`). Add `pgvector` extension via migration `2026_01_add_pgvector.sql`. |
| 1.2 | Data migration | Write a script (dry‑run) to back‑fill `vector` column with existing embeddings. Validate checksum. |
| 1.3 | Query layer | Create RPC `query_vector_hybrid` (fallback to BM25). Add TypeScript wrapper `queryVector` in `supabase/ukp-client.ts`. |
| 1.4 | Integration test | Add `test_vector_query.py` covering insert‑embed‑search cycle. Run via CI. |

**Milestone:** Vector‑first search functional on a dev branch, covered by automated tests.

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

**Milestone:** Worktree status visible, safe cleanup workflow in place.

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

**Next immediate action (Week 0.0)**
1. Schedule the kick‑off meeting with product, dev, ops.
2. Create a GitHub Project board (Backlog, Ready, In‑progress, Review, Done).
3. Export baseline metrics (health, test coverage, note count) and store them under `wiki/Intelligence/baseline-metrics.md`.

These steps set the foundation for the rest of the roadmap.
