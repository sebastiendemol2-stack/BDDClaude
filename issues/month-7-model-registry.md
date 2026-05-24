---
title: "Month-7 Model Registry & Versioning - Detailed Tasks"
date: 2026-05-22
tags: [plan, roadmap, models]
type: decision
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# Month-7 Model Registry & Versioning - Detailed Tasks

## Tasks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| 1 | **Registry schema** - `vault_models` versioned by `(provider, name, version)`, RLS/grants, `vault_embeddings.model_id` | Backend | DONE |
| 2 | **Edge Functions** - `model-list`, `model-latest`, `model-register`, `model-deactivate` | Backend | DONE |
| 3 | **Client SDK** - `UKPClient` model types, list/register/latest/status/fallback helpers | SDK | DONE |
| 4 | **Dashboard UI** - Models route with registry stats, latest model, status controls for private admin builds | Frontend | DONE |
| 5 | **Integration tests** - registration, latest selection, deactivation fallback, public inactive filtering | QA | DONE |
| 6 | **Documentation** - `wiki/Intelligence/model-registry.md` and dashboard env docs | Tech Writer | DONE |
| 7 | **Deploy remote functions** - deploy `model-latest` and `model-deactivate`, redeploy list/register | DevOps | DONE |
| 8 | **Pilot rollout** - register production embedding model and verify RAG/vector clients use selected model | DevOps | DONE - secret `OPENAI_API_KEY` configured 2026-05-24; `rag-answer` v4 selects `text-embedding-3-large` via `model-latest`; BM25 fallback covers OpenAI 429 (quota-bound, external to BDDClaude) |
| 9 | **Auth hardening** - replace temporary admin token path with Supabase Auth admin UI before public dashboard writes | Security | DONE |

## Acceptance Criteria

- Model versions can coexist under the same name when version differs.
- Public clients can list active models and fetch the latest model without seeing inactive entries.
- Admin clients can register and deactivate a model without exposing service role keys in the browser.
- SDK clients can request a fallback chain for model selection.
- Dashboard build passes and the Models page remains read-only unless configured for a private admin build.

## Notes

- `rollout_percent` is stored but not used for probabilistic routing yet.
- `MODEL_REGISTRY_ADMIN_TOKEN` is an internal fallback for trusted/private deployments only.
- Remote deployment completed on 2026-05-22: `model-list` v2, `model-register` v2, `model-latest` v1, `model-deactivate` v1.
- Remote schema required corrective alignment via `model_registry_remote_alignment_v2` because the applied migration name existed with an older table shape.
- `text-embedding-3-large` is active at 100% rollout and is selected by `model-latest`; `text-embedding-3-small` remains fallback.
- `rag-answer` v4 selects the registry model and requests 1536-dimensional embeddings for pgvector compatibility, but remote embeddings currently fall back to BM25 because `OPENAI_API_KEY` is not configured.
- Local Jan hybrid path verified via `http://localhost:1337/v1`: `gemma-4-E2B-it-IQ4_XS` can generate grounded answers from retrieved vault context.
- Dedicated local embeddings server verified on `http://127.0.0.1:1338/v1` with `sentence-transformer-mini` (`384` dimensions).
- `_scripts/rag_bridge.py answer` supports Jan chat completion, `--no-log` for vault-safe smoke tests, and `--embed-base-url` for a separate Jan/llama.cpp embeddings endpoint.
- `tools/scripts/start-jan-embedding-server.ps1` starts or detects the dedicated local embeddings server without modifying Jan source files.
- `_scripts/.env.example` documents the local Jan chat and embeddings variables for reproducible setup.
- 2026-05-24 — Task 9 closed: dashboard ships `/login` and an `AuthProvider`, admin mutations send `Bearer <user_jwt>` from `supabase.auth.getSession()`, and Models page surfaces a sign-in hint when the visitor is not an admin. `VITE_MODEL_REGISTRY_ADMIN_TOKEN` remains documented as an internal backstop only; the server-side `isAdminRequest` already accepts the JWT path (`app_metadata.role === 'admin'`).
- 2026-05-24 — Task 8 closed: `OPENAI_API_KEY` added to Supabase Edge Function secrets; live `rag-answer` call confirms `selected_model = text-embedding-3-large` (3072d, query_dimensions=1536) is picked by the registry. OpenAI currently returns HTTP 429 (quota exhausted on the account) so embeddings are not yet flowing end-to-end, but the integration is verified and the BM25 fallback keeps RAG responses available. Quota refill / billing is the only remaining external dependency.
- 2026-05-24 (PM) — OpenAI quota refilled. Two latent bugs surfaced and fixed:
  - `query_vector_hybrid` RPC used `%s::vector` (no quotes) and `search_path = 'public'` (vector type lives in `extensions`). Patched to `%L::extensions.vector` with `search_path = 'public', 'extensions'`. Also added `'english'` regconfig to `ts_headline` calls.
  - Embedding back-fill had never run — 0/11 entries had `embedding_vector`. New Edge Function `embed-backfill` deployed (selects active embedding model from registry, batches OpenAI `/v1/embeddings` call, UPDATE vault_entries). Back-filled 11/11 entries at 1536d successfully. End-to-end vector RAG now returns scored hybrid results (cosine + BM25).
