---
title: "6‑12 Months Execution Plan"
date: 2026-05-22
tags: [roadmap, next‑steps]
type: concept
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: internal
---

# 6 → 12 Months Execution Plan

## Overview

| Horizon | Focus area | Core outcome |
|--------|------------|--------------|
| **6‑9 mo** | **Model Registry & Versioning** | Central catalog of AI models, automated rollout, and inference fallback. |
| **9‑12 mo** | **Multi‑tenant Vaults & Export/Import** | Ability to host multiple independent vaults, with secure import/export pipelines. |
| **12 mo** | **Marketplace & Extensibility** | Public SDK/extensions marketplace for sub‑agents, prompts, and UI widgets. |

---

## 6‑9 Months – Model Registry & Versioning

| Week | Milestone | Tasks (high‑level) |
|------|-----------|--------------------|
| 6.1 | **Registry schema** | Add `vault_models` table (id, name, version, provider, source_hash, status). Define RLS: only admins may write, all users may read active models. |
| 6.2 | **Edge Functions** | Deploy `model_register`, `model_deactivate`, `model_latest` (JWT‑protected). |
| 6.3 | **Client SDK** | Extend `ukp-client.ts` with `registerModel`, `listModels`, `selectModel`. Provide TypeScript types via `supabase_generate_typescript_types`. |
| 6.4 | **CI pipeline** | Add test that a model registration triggers a DB migration and the new model appears in the dashboard. |
| 6.5 | **Fallback strategy** | Implement client‑side logic: if the selected model endpoint fails, automatically fall back to the next‑highest‑priority model. |
| 6.6 | **Dashboard UI** | New “Models” tab: list, statuses, version history, activation toggle. |
| 6.7 | **Documentation** | `wiki/Intelligence/model-registry.md` – how to add, retire, and version models. |
| 6.8 | **Pilot rollout** | Register the current production embeddings model (`text-embedding-3-large`) and an experimental RAG‑optimised model. Verify end‑to‑end queries use the selected model. |

**Success criteria** – Model registry searchable via dashboard, API returns correct version, fallback works in 95 % of simulated failures, docs published.

### M7 Continuation Status - 2026-05-22

| Area | Status |
| --- | --- |
| Registry schema | DONE locally - `vault_models` versioned by `(provider, name, version)` with RLS/grants |
| Edge Functions | DONE locally - `model-list`, `model-latest`, `model-register`, `model-deactivate` |
| Client SDK | DONE locally - typed list/register/latest/status/fallback helpers in `UKPClient` |
| Dashboard | DONE locally - Models tab reads registry and supports private admin builds |
| Tests | DONE locally - `_scripts/tests/test_model_registry.py` |
| Documentation | DONE locally - [[Intelligence/model-registry]] + `issues/month-7-model-registry.md` |
| Remote deployment | DONE - migration applied + 4 functions deployed (2026-05-22) |
| Pilot rollout | DONE - `OPENAI_API_KEY` configured, `rag-answer` confirms `model-latest` picks `text-embedding-3-large`; BM25 fallback covers OpenAI quota 429 (2026-05-24) |

---

## 9‑12 Months – Multi‑tenant Vaults & Export/Import

| Week | Milestone | Tasks |
|------|-----------|-------|
| 9.1 | **Tenant isolation schema** | Add `vault_tenants` table (tenant_id, name, owner_user_id). Extend all existing tables with `tenant_id` foreign key. |
| 9.2 | **RLS policies** | Enforce per‑tenant row‑level security: a user can only see rows where `tenant_id = user.tenant_id`. |
| 9.3 | **Tenant provisioning API** | Edge Function `tenant_create`, `tenant_assign_user`. Return a scoped service URL (`https://<project>.supabase.co/functions/v1/<tenant>/...`). |
| 9.4 | **Export pipeline** | New script `scripts/export_vault.ts` that: <br>• fetches all rows for a tenant, <br>• writes a zip containing markdown notes and a manifest JSON, <br>• stores it in Supabase Storage bucket `vault-exports`. |
| 9.5 | **Import pipeline** | Complementary script `scripts/import_vault.ts` that reads the zip, validates front‑matter, and inserts rows under the target tenant (duplicate detection, conflict resolution). |
| 9.6 | **Dashboard tenant view** | Add “Tenant” selector in the top‑right; UI shows only notes belonging to the selected tenant. |
| 9.7 | **Testing** | End‑to‑end test: create tenant A, export, create tenant B, import, verify note count and link integrity. |
| 9.8 | **Documentation** | `wiki/Intelligence/multi-tenant-vault.md` – provisioning, export/import, security considerations. |
| 9.9 | **Beta rollout** | Invite two internal teams to pilot separate tenants; collect feedback on latency and permission handling. |

**Success criteria** – Export/import works without data loss, RLS blocks cross‑tenant access, at least two tenants successfully onboarded.

---

## 12 Months – Marketplace & Extensibility

| Week | Milestone | Tasks |
|------|-----------|-------|
| 12.1 | **Extension registry** | Table `vault_extensions` (slug, name, version, description, repo_url, status). |
| 12.2 | **Publish API** | Edge Functions `extension_publish`, `extension_update`, `extension_search`. Require admin JWT. |
| 12.3 | **CLI tool** | New `opencode extension` sub‑command to push/pull extensions from the registry. |
| 12.4 | **Marketplace UI** | Dashboard “Marketplace” tab: browse, filter by category (sub‑agent, prompt, UI widget), install button that writes the extension files into `skills/` or `plugins/`. |
| 12.5 | **Review workflow** | PR‑based submission: extension authors open a PR against `master`; CI runs lint/tests; maintainers approve and merge → automatically published. |
| 12.6 | **Revenue / licensing** (optional) | Schema for `extension_licenses` (free, trial, paid). Integration with Stripe (future). |
| 12.7 | **Documentation** | `wiki/Intelligence/marketplace.md` – how to develop, publish, and consume extensions. |
| 12.8 | **Pilot extensions** | Publish three starter packs: <br>• “Sub‑agent template” (boilerplate for new agents), <br>• “Prompt collection – research”, <br>• “UI widget – quick‑note”. |
| 12.9 | **Beta community test** | Invite a small group of power users to install and give feedback on the Marketplace experience. |

**Success criteria** – At least three extensions publicly listed, installation flow works end‑to‑end, documentation complete, community feedback positive.

---

## Cross‑cutting Activities (throughout 6‑12 months)

| Activity | Frequency | Owner |
|----------|-----------|-------|
| **Security audits** | Quarterly (run `source-command-audit`) | Security lead |
| **Performance profiling** | Monthly load‑test of vector search & runtime APIs | Performance engineer |
| **Documentation sync** | After each major feature (update wiki) | Technical writer |
| **User training** | Bi‑monthly webinars (new dashboard features, tenant management) | Product ops |
| **Feedback loop** | Continuous (feedback channel in dashboard) | Product manager |

---

## Timeline (visual)

```
Month 6 ──► Month 9 ──► Month 12
   |            |            |
   | Model Reg  | Multi‑tenant| Marketplace
   |            |            |
   └─► Dashboard updates ──► UI extensions
```

---

### How to proceed
1. **Create the markdown file** – this file is already added to the repository at `wiki/Intelligence/next-steps-beyond-6-months.md`.
2. **Add the file to git** – commit with a concise message (e.g., `Add 6‑12 month roadmap`).
3. **Schedule the first kickoff** for the Model Registry (Week 6.1) with the relevant stakeholders (DB, backend, frontend, security).

Feel free to adjust dates, scope, or ask for more detail on any workstream. The outline is modular so you can start any of the three horizons independently while keeping the overall direction aligned.
