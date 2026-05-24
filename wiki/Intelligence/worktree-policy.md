---
title: "Worktree Cleanup Policy"
date: 2026-05-22
tags: [worktree, policy, git]
type: decision
status: active
confidence: high
source_type: synthesis
freshness: evergreen
sensitivity: internal
---

# Worktree Cleanup Policy

## Classification

| Status | Definition | Action |
|--------|------------|--------|
| **active** | Modified or committed within last 7 days | Keep |
| **idle** | No activity for 7–30 days | Warn in dashboard |
| **stale** | No activity for >30 days | Flag for cleanup |
| **locked** | Uncommitted changes >24h after last commit | Investigate + resolve |

## Cleanup rules

1. **Never delete `master` or `main`** worktree
2. **Stale worktrees** (>30d inactive) → archive branch, delete worktree
3. **Locked worktrees** (>24h uncommitted) → resolve changes first, then clean
4. **Idle worktrees** (7–30d) → no action, dashboard warning only
5. **Orphaned worktrees** (`.git/worktrees/` dir exists but worktree path missing) → `git worktree prune`

## Who can clean

| Role | Can delete stale | Can force-delete locked |
|------|-----------------|------------------------|
| Owner | ✅ | ✅ (after review) |
| Contributor | ✅ (their own) | ❌ |
| CI/CD | ❌ (open PR only) | ❌ |

## Automation

- **Daily scan**: `scripts/inspect_worktrees.ps1 -PushReport` (via cron/scheduler)
- **Weekly review**: Dashboard alerts for stale + locked worktrees
- **Manual cleanup**: `git worktree remove <path>` or `git branch -D <branch>`

## Procedure

### Archive a stale worktree

```bash
git tag archive/worktree-<branch>-$(date +%Y%m%d) <branch>
git branch -D <branch>
git worktree prune
```

### Force-remove a locked worktree

```bash
# 1. Review uncommitted changes
git -C <worktree-path> diff

# 2. Stash or commit as needed
git -C <worktree-path> stash

# 3. Remove
git worktree remove <worktree-path>
git branch -D <branch>
```

## Voir aussi

- [[Intelligence/0-6-month-execution-plan]] (Month 4)
- `scripts/inspect_worktrees.ps1`
- `dashboard/` → Worktree Status page
