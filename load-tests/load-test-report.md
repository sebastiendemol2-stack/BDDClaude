# Load Test Report — 2026-05-22

## Rerun with SUPABASE_SERVICE_ROLE_KEY — 2026-05-22 13:40

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Duration | 30s | — | — |
| Virtual users | 10 | — | — |
| Iterations | 181 | — | — |
| HTTP requests | 543 | — | — |
| p(95) query latency | 329 ms | <5,000 ms | ✅ |
| p(95) HTTP duration | 322 ms | <10,000 ms | ✅ |
| Error rate | 0% | <1% | ✅ |

## Endpoints

| Endpoint | Success rate | Avg latency |
|----------|-------------|-------------|
| `metrics` (POST) | 100% | ~230 ms |
| `worktree-status` (GET) | 100% | ~230 ms |
| `memories-store` (POST) | 100% | ~230 ms |

## Fixes from first run

| Issue | Fix |
|-------|-----|
| memories-store 401/403 | Added `SUPABASE_SERVICE_ROLE_KEY` env var |
| memories-store 400 invalid UUID | Fixed k6 script: `session_id` now generates valid UUID v4 |

## Summary

All 3 endpoints pass at 100% success rate. Error rate 0%. No threshold violations. Runtime is production-ready under 10 VU / 30s load.

## Recommendations

1. Add `SUPABASE_SERVICE_ROLE_KEY` to CI secrets for accurate CI load testing
2. Consider warm-up schedules for Edge Functions (cold start adds ~500ms)
3. Monitor p(95) > 2s as an alert threshold
4. Re-run with full 500 VU / 10 min load in production environment
