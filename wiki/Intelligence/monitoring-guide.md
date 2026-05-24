---
title: "Monitoring Guide — Production Alerts & Runbooks"
date: 2026-05-22
tags: [monitoring, operations, production]
type: decision
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# Monitoring Guide — Production Alerts & Runbooks

## Alert Thresholds

| Metric | Threshold | Severity | Action |
|--------|-----------|----------|--------|
| Vector search latency p(95) | >2,000 ms | Warning | Check DB CPU, connection pool |
| Vector search latency p(95) | >5,000 ms | Critical | Failover to BM25-only, page on-call |
| Runtime error rate | >1 % | Warning | Check EF logs in Supabase dashboard |
| Runtime error rate | >5 % | Critical | Page on-call, potential rollback |
| Dashboard Realtime disconnect | >2 min | Warning | Restart subscription, check presence |
| Worktree lock age | >24 h | Warning | Review PR, manual cleanup if stale |
| Daily worktree report missed | >36 h | Warning | Check GitHub Action logs |
| Edge Function cold start | >1,500 ms | Warning | Warm-up schedule may need adjustment |
| DB connection count | >80 % of max | Critical | Scale up DB or optimize pool |

## Dashboard Access

| Environment | URL | Auth |
|-------------|-----|------|
| Production | TBD (deploy as static site) | Supabase anon key (public read) |

## Runbooks

### Latency spike on vector search

1. Check `logs` dashboard → Edge Functions → `ukp-query` and `ukp-mcp`
2. Run `EXPLAIN ANALYZE` on the slow query pattern
3. If vector index (`ivfflat`) is scanning too many rows, increase `lists` param
4. If total table size > 100k rows, consider migrating to `hnsw` index
5. As last resort, set `statement_timeout` on the RPC and enable client-side BM25 fallback

### Edge Function crash loop

1. `supabase functions logs <slug> --tail`
2. Check environment variables (missing `SUPABASE_SERVICE_ROLE_KEY`)
3. If import error, verify Deno compatibility on Supabase runtime
4. Rollback to previous version via `supabase functions deploy`

### Realtime subscription drops

1. Check Supabase Realtime dashboard → active connections
2. Verify browser hasn't throttled the tab (background tabs lose WebSocket after ~5 min)
3. Restart the dashboard app

### Worktree stuck for >48h

1. Identify via Dashboard → Worktree Status
2. Manually delete the stale worktree: `git worktree prune`
3. Clean up orphaned branch: `git branch -D <branch-name>`
4. Remove the stale report row (if needed)

## Dashboard Deployment

```bash
cd dashboard
cp .env.example .env   # fill in VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY
npm install
npm run build          # outputs to dist/
```

Deploy `dist/` as a static site (GitHub Pages, Vercel, Netlify, or Supabase Storage).

Voir aussi : [[Intelligence/cognitive-runtime]], [[Intelligence/0-6-month-execution-plan]]
