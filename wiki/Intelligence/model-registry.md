---
title: "Model Registry & Versioning"
date: 2026-05-22
tags: [models, registry, versioning, supabase]
type: concept
status: active
confidence: high
source_type: synthesis
freshness: evergreen
sensitivity: internal
---

# Model Registry & Versioning

The Model Registry is the Month 7 continuation of [[Intelligence/next-steps-beyond-6-months]]. It gives BDDClaude a central catalog for embedding, chat, reranker, vision, audio, and tool models, with status control and deterministic fallback ordering.

## Scope

M7 covers the operational layer around model selection:

- Store model versions in `vault_models` with `(provider, name, version)` uniqueness.
- Select the best active model by `priority` and `fallback_order`.
- Keep inactive, deprecated, and error models visible to admin tooling without exposing write access publicly.
- Expose Edge Functions for listing, latest-model selection, registration, and deactivation.
- Surface the registry in the dashboard Models tab.
- Extend `UKPClient` so IDE clients can use model selection before calling [[Intelligence/vector-first-search]] or [[Intelligence/cognitive-runtime]] APIs.

## Data Model

`vault_models` is the source of truth.

| Column | Purpose |
| --- | --- |
| `provider`, `name`, `version` | Versioned identity, unique as a triplet |
| `kind` | `embedding`, `chat`, `reranker`, `vision`, `audio`, or `tool` |
| `dimension` | Vector dimension or equivalent compatibility marker |
| `priority` | Higher value wins primary selection |
| `fallback_order` | Lower value is tried earlier after the primary model |
| `rollout_percent` | Planned rollout gate for gradual activation |
| `status` | `active`, `inactive`, `deprecated`, or `error` |
| `config` | Non-secret operational metadata |
| `api_key_env` | Name of the server-side secret env var, never the secret value |

`vault_embeddings.model_id` links stored embeddings to the model version that generated them.

## Security Model

Read access is intentionally narrow:

- Direct table reads by `anon` and `authenticated` roles only see `status = 'active'`.
- Full table writes are restricted to `service_role` via RLS.
- Edge Functions use the service role server-side, but admin mutations require one of:
  - service-role bearer token from a trusted backend or test runner;
  - a Supabase Auth JWT whose `app_metadata.role` (or `roles`) includes `admin`, or `is_admin: true`;
  - `MODEL_REGISTRY_ADMIN_TOKEN` via `x-admin-token` (backstop for private deployments).

### Dashboard admin flow

The dashboard ships with a `/login` route. Signing in with a Supabase Auth user that has `app_metadata.role = "admin"` activates the registration form and per-row status controls on the Models page. The browser sends the user JWT in `Authorization: Bearer ...`, and `isAdminRequest` (see `supabase/functions/_shared/modelRegistry.ts`) verifies the role server-side before any mutation.

To promote a user, set their `app_metadata` in Supabase Dashboard → Authentication → Users:

```json
{ "role": "admin" }
```

`VITE_MODEL_REGISTRY_ADMIN_TOKEN` stays available as a backstop for trusted/internal builds. It must never be configured on public hosting because anyone who downloads the bundle would obtain admin write access.

## Edge Functions

| Function | Access | Purpose |
| --- | --- | --- |
| `model-list` | public read, admin can include inactive models | List active models or the full registry for admins |
| `model-latest` | public read | Return the primary active model plus fallback chain |
| `model-register` | admin only | Upsert a model version by `(provider, name, version)` |
| `model-deactivate` | admin only | Set status to `inactive`, `deprecated`, `error`, or back to `active` |

## SDK Usage

```ts
import { UKPClient } from './supabase/ukp-client'

const client = new UKPClient({ url, key, clientIde: 'Codex' })

const selected = await client.selectModel({
  kind: 'embedding',
  minDimension: 1536,
})

const chain = await client.getModelFallbackChain({
  provider: 'openai',
  kind: 'embedding',
})
```

Admin registration uses the same SDK when instantiated with a trusted service key:

```ts
await client.registerModel({
  provider: 'openai',
  name: 'text-embedding-3-small',
  version: '1.0.0',
  kind: 'embedding',
  dimension: 1536,
  priority: 30,
  fallback_order: 20,
  rollout_percent: 100,
  status: 'active',
})
```

## Dashboard

The Models tab displays:

- total, active, and fallback counts;
- selected latest embedding model;
- provider/name/version history;
- dimension, priority, fallback order, rollout percent, status, and updated timestamp.

Admin builds can register models and change status. Public builds stay read-only.

## Validation

Primary validation lives in `_scripts/tests/test_model_registry.py`:

- register two test model versions;
- list full registry as admin;
- select latest model by priority and fallback order;
- deactivate the primary and verify fallback promotion;
- verify public listing does not expose inactive models.

## Open Decisions

- Whether `rollout_percent` should become probabilistic routing inside `model-latest`, or stay metadata until the runtime has a request identity to hash against.
- Whether chat model dimensions should remain required or move to a nullable compatibility field when non-embedding model support expands.

## Resolved Decisions

- 2026-05-24 — Dashboard admin mutations default to Supabase Auth JWT (`/login` + `app_metadata.role = "admin"`). `MODEL_REGISTRY_ADMIN_TOKEN` is retained only as a backstop for trusted internal builds.

## Voir aussi

- [[Intelligence/next-steps-beyond-6-months]]
- [[Intelligence/vector-first-search]]
- [[Intelligence/cognitive-runtime]]
- [[Intelligence/monitoring-guide]]
