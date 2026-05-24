---
title: "Month‑4 Worktree Clean‑up Automation — Detailed Tasks"
date: 2026-05-22
tags: [plan, roadmap, worktree]
type: decision
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# Month‑4 Worktree Clean‑up Automation — Detailed Tasks

## Tasks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| 1 | **Inventory script** — `scripts/inspect_worktrees.ps1`: list worktrees, detect locked files, flag >30d stale | DevOps | DONE |
| 2 | **Supabase table** — `vault_worktree_reports` migration + RLS | DevOps | DONE |
| 3 | **Edge Function** — `worktree-status`: POST to store, GET to retrieve latest report | DevOps | DONE |
| 4 | **Push integration** — `inspect_worktrees.ps1 -PushReport` sends report to Edge Function | DevOps | DONE |
| 5 | **Dashboard** — WorktreeStatus page reads from Supabase via Realtime | Frontend | DONE |
| 6 | **Cleanup policy** — `wiki/Intelligence/worktree-policy.md` | Tech Writer | DONE |
| 7 | **GitHub Action** — daily scan + stale worktree PR (`.github/workflows/worktree-scan.yml`) | DevOps | DONE |
| 8 | **Validation** — run on dev, verify no active branches affected (✅ pushed + GET verified) | QA | DONE |

## Acceptance Criteria

- `scripts/inspect_worktrees.ps1` outputs accurate JSON report of all git worktrees
- Dashboard Worktree Status page reflects latest report with age/status indicators
- Policy document clearly defines stale/locked cleanup rules
- CI/CD can open review PRs for stale worktrees
