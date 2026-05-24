# BDDClaude Dashboard

Monitoring dashboard for the BDDClaude vault — vault health, search stats, runtime events, and worktree status.

## Routes

| Path | Page | Data source |
|------|------|-------------|
| `/` | Health | `vault_entries` via Realtime |
| `/search-stats` | Search Stats | `vault_entries` via Realtime |
| `/runtime-events` | Runtime Events | `vault_memories` + `vault_feedback` via Realtime |
| `/worktree-status` | Worktree Status | `worktree-status` Edge Function + Realtime |
| `/chat` | Chat Vault | `rag-answer` Edge Function |
| `/models` | Model Registry | `model-list`, `model-latest`, `model-register`, `model-deactivate` Edge Functions |
| `/graph` | Memory Graph | `vault_entries` + `vault_relations` |
| `/login` | Sign in | Supabase Auth (`signInWithPassword`) |

## Quick start

```bash
cp .env.example .env
# Edit .env with your Supabase project credentials
npm install
npm run dev
```

## Environment

| Variable | Source |
|----------|--------|
| `VITE_SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase Dashboard → Settings → API → anon public key |
| `VITE_MODEL_REGISTRY_ADMIN_TOKEN` | Optional backstop for trusted/internal builds — matches `MODEL_REGISTRY_ADMIN_TOKEN` in Edge Function secrets |

## Admin access (Model Registry)

The Models page is read-only by default. Two paths grant write access:

1. **Recommended — Supabase Auth.** Visit `/login`, sign in with an account whose `app_metadata` includes `role: "admin"` (or `roles: ["admin"]`, or `is_admin: true`). The dashboard sends the user JWT in `Authorization: Bearer ...`; `model-register` and `model-deactivate` verify the role server-side via `isAdminRequest` in `supabase/functions/_shared/modelRegistry.ts`.
2. **Backstop — `VITE_MODEL_REGISTRY_ADMIN_TOKEN`.** Optional shared secret for trusted/internal builds only. Sent as `x-admin-token`. Never configure it on public static hosting.

To grant a user the admin role, update their auth metadata via Supabase Dashboard → Authentication → Users → Edit user → `app_metadata`:

```json
{ "role": "admin" }
```

## Build

```bash
npm run build
```

Output goes to `dist/`. Deploy as a static site or serve via Supabase Storage / hosting.
