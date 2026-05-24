---
title: "Month‑3 Dashboard / Monitoring — Detailed Tasks"
date: 2026-05-22
tags: [plan, roadmap, dashboard]
type: decision
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# Month‑3 Dashboard / Monitoring — Detailed Tasks

## Tasks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| 1 | **Scaffold dashboard** — React + Vite under `dashboard/`, define routes: Health, Search Stats, Runtime Events, Worktree Status | Frontend | DONE |
| 2 | **Health page** — entries count, health badge (green/yellow/red), by-type table, Realtime updates | Frontend | DONE |
| 3 | **Search Stats page** — bar chart (recharts), recent entries table | Frontend | DONE |
| 4 | **Runtime Events page** — memories + feedback tables with Realtime INSERT subscriptions | Frontend | DONE |
| 5 | **Worktree Status page** — placeholder with planned features | Frontend | DONE |
| 6 | **Metrics Edge Function** — expose `/metrics` for Prometheus-style metrics | DevOps | DONE |
| 7 | **CI/CD** — GitHub Action to build & test dashboard on PR | DevOps | DONE |
| 8 | **Integration test** — `_scripts/tests/test_metrics_integration.py` (JSON + Prometheus + data flow) | QA | DONE |
| 9 | **Env config** — document VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY in README + .env.example | DevOps | DONE |

## Acceptance Criteria

- Dashboard accessible at `/dashboard` with 4 routes
- Health badge auto-updates via Realtime
- Charts render with mock data (real data when Supabase is connected)
- CI passes on PR
