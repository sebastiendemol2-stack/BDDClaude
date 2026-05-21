---
title: "Log — Journal des operations"
date: 2026-05-19
tags: [log]
type: concept
status: active
confidence: high
source_type: human
freshness: evergreen
sensitivity: public
---

# Log — Journal des operations

Chaque operation sur le vault ajoute une entree ici. Format :

```
YYYY-MM-DD HH:MM — [Operation] : description
```

---

2026-04-09 00:00 — Init : vault cree a partir du Second Brain Kit
2026-04-19 — Ingest : 1 fichier scanné, 1 nouveau (wiki/Intelligence/context-engineering.md), 0 enrichi — index mis à jour
2026-04-19 — Save : daily note créée (wiki/Daily/2026-04-19.md), index vérifié
2026-04-19 — Multi-vault : connexion project vault (C:/Cowork-App/docs/vault) — préfixes kb:/project: opérationnels
2026-04-19 — Save : daily note 2026-04-19 mise à jour (session 2), logs des deux vaults synchronisés
2026-04-19 — Agent Migration Exploration : migration Claude → Gemini 2.5 Pro testée (reduction tokens) — plan cree, migration effectuee, limite depenses Google API = 0 → rollback Anthropic, configuration restauree
2026-05-07 — Refonte Architecture : nettoyage schema Supabase (drop vault_pages, ajout colonnes status/type), peuplement wiki local (3 Context, 2 Resources), index mis a jour
2026-05-07 — Save : daily note créée (wiki/Daily/2026-05-07.md), sync script opérationnel, 7 notes synced local <-> Supabase
2026-05-09 14:58 — Reorganisation PC : C:\ nettoyé (84%→83% utilisé, +6 Go libres), tous projets centralisés dans D:\Dev (cowork-app, sys-orchestra, base-de-donnees, claude-obsidian, tetris-js), archives dans D:\Dev\_archive, fichiers perso triés dans D:\sebas\, caches npm+pip vidés — vault déplacé de C:\base de données → D:\Dev\base-de-donnees
2026-05-10 — Save : vérification plan "rendre Claude plus intelligent" (6 tests passés), mise en place Option B multi-device (git init + hook post-commit sync.py push + remote GitHub privé sebastiendemol2-stack/base-de-donn-es), GitHub CLI installé via winget
2026-05-10 — Audit config Claude Code : plan "rendre Claude plus intelligent et fiable" soumis — audit révèle que les 3 changements (effortLevel: high, CLAUDE.md global, section thinking triggers) sont déjà en place. Plan réduit à 6 étapes de vérification uniquement.
2026-05-11 — Finalisation Agent System : J5 validation terminée (tests E2E, performance, audit sécurité, docs utilisateur, plan maintenance), projet déployable avec roadmap 12 mois — plan raw/ mis à jour, système prêt beta Q1 2025
2026-05-11 — Plan Intégration Jan→Cowork-App : analyse architectures, synergies identifiées (Electron/React commune, multi-modèles IA), plan 4 phases 6 semaines créé — système agent Jan comme enhancement orchestration cowork-app
2026-05-11 — Browser Automation + Docker Sandbox : browserManager Puppeteer (launch/navigate/screenshot/evaluate/pdf/close), dockerManager Dockerode (status/exec/writeFile/readFile), 10 canaux IPC, routes TaskExecutor (browser + sandbox avec approval), skills browser-automation + docker-sandbox, fix cron handler bug (ipcMain.handle→appel direct), fix vault.cjs (export generateVaultReport)
2026-05-11 — README mis à jour : stack complète, features browser/sandbox/cron/skills/agent-system, structure projet, architecture diagram, 399 tests
2026-05-11 — Jan offline resilient : isReady indépendant de Jan (hasApiKey || janOk), ModelSelector cache options locales si Jan absent, ChatInput utilisable sans Jan si clé cloud, messages d'alerte clairs, build 11s — 383/384 tests verts
2026-05-11 — Phase 1 Intégration : infrastructure terminée (Zustand migré, stores créés, dépendances Jan ajoutées, système agent intégré, build validé) — Phase 2 orchestration intelligente démarrée
2026-05-11 — Suppression Ollama : service ollama.js supprimé, constantes nettoyées (OLLAMA_BASE, LOCAL_MODELS, DEFAULT_ORCHESTRATOR), imports retirés, UI simplifiée — app 100% cloud
2026-05-11 — Phase 2 Intégration avancée : TaskExecutor amélioré (orchestration, PII guard, memory context, budget manager), PIIModeManager créé, stores settings enrichis, fichiers agent-system adaptés TypeScript→JavaScript (orchestration-interface, pii-mode, risk-matrix, backlog), build validé — 50% Phase 2 complété
2026-05-11 — Phase 3 UI/UX modernisation : SettingsPanel remanié (@radix-ui/Tabs, Switch, Tooltip), Sidebar modernisé (@radix-ui/Tabs, Tooltip, Separator, collapsible avec localStorage), AgentProfilePanel créé et intégré, CronPanel + ApprovalModal migrés vers @radix-ui/Dialog, 32 nouveaux tests — build validate (4.08s, 0 erreurs)
2026-05-11 — Migration Ollama→Jan : service jan.js créé (API OpenAI-compatible localhost:1337), constants JAN_BASE + modèles Jan, orchestration-interface route local fixée (était cassée), App.jsx callOllama→callJan, 9 fichiers UI renommés, RAG worker migré /v1/embeddings, ollama.js+test supprimés, SettingsContext.jsx mort retiré, build 11s — 383/384 tests verts (1 pathGuard env)
2026-05-11 — Phase 4 Finalisation : dual settings éliminé (SettingsContext → Zustand settingsStore), AgentModal migré @radix-ui/Dialog, CSS modal legacy supprimé, 7 tests corrigés (zustand mocking + risk matrix), KnowledgePanel lazy-loadé, build 3.76s — 399/400 tests verts, 4 phases intégralement livrées
2026-05-11 — Phase 2 Intégration finalisée : AgentOrchestrationInterface connecté au handleSend (injection instructions + mémoire agent dans le flux d'envoi), sauvegarde automatique des interactions en mémoire agent après chaque réponse, initialisation du système agent au démarrage (useEffect → loadProfile + ready), PII guard intégré dans executeCall, tests d'intégration Phase 2 créés (20 tests, stores/composer/PII/risk/backlog/orchestration), build validé (0 erreurs, 3.50s) — Phase 2 100% complétée
2026-05-14 — Code Review + 10 Fixes : audit complet _scripts/ par 3 agents parallèles → 10 tâches Subagent-Driven Development — utils.py créé (shared: _require_env, _validate_uuid, _validate_slug, _validate_path, _truncate_by_section), brain.py sécurisé (UUID/slug validation, fd leak fix, truncation sections), sync.py refactorisé (YAML parser state-machine, upsert atomique POST, UTC datetime, validate obsidian_path, timeout HTTP, conflict pull), schema/supabase.sql versionné (7 tables/RPCs), skills prime/save/sync mis à jour, .gitignore + requirements.txt + index.md nettoyés — 26 tests (0→26), 17 commits sur master
2026-05-14 — Design maj-auto-tout-compo : brainstorming complet (5 sections) pour un outil d'auto-update PC Windows — architecture retenue : PowerShell modules (winget/choco/scoop/npm-g/pipx/Windows Update/VS Code) + Node.js/Express backend + React/Vite dashboard — déclenchement mixte (manuel CLI + cron dimanche 3h), notifications BurntToast sur erreur uniquement, isolation totale par module (try/catch indépendants, timeout 10 min), SSE temps réel — design spec approuvé, plan d'implémentation en cours (D:\Dev\maj auto tout compo)
2026-05-19 — Ingest Jan : 3 sources raw/notes/ compilées → 2 nouvelles notes wiki (agent-system-architecture, agent-workflow-blueprint) + 1 enrichie (integration-jan-cowork) — index mis à jour
2026-05-19 — Migration v3.0.0 complète : 5 phases en parallèle multi-agents — normalize_for_hash + 9 tests (golden vectors), Supabase DDL enrichi (14 colonnes, 4 tables, 1 vue), sync.py v3 (content_hash, alias registry, rename-suggest), /lint 15 checks → health.md (73%), frontmatter 8 champs sur toutes les notes, types corrigés (note→decision, context-session→concept), 0 orphelins, .gitignore nettoyé (Daily/, privacy), context-session déplacé dans Context/, CLAUDE.md synchronisé avec manifest — 39/39 tests verts
2026-05-19 23:51 — Lint & Repair : execution /lint révèle 2 issues (lien cassé [[Intelligence/integration-jan-cowork]], mauvais format [[wiki/index.md]]), tous deux fixés. Création note Intelligence/integration-jan-cowork.md documentant plan 4 phases Jan→Cowork avec synergies architecture et décisions. Vault health 82% → 100%.

## Liens

- [[index.md]]

2026-05-19 20:56 — [INGEST] exemple-article -> wiki/Intelligence/exemple-article.md
2026-05-19 20:56 — [INGEST] integration-jan-cowork-plan -> wiki/Intelligence/integration-jan-cowork-plan.md
2026-05-19 20:56 — [INGEST] plan-agent-system -> wiki/Intelligence/plan-agent-system.md
2026-05-19 20:56 — [INGEST] plan-blueprint-workflow-agent-memoire-instructions -> wiki/Intelligence/plan-blueprint-workflow-agent-memoire-instructions.md
2026-05-19 22:45 — [SAVE] Améliorations locales vault : 13 tâches, 27 nouveaux tests, health 60%→93%

## Améliorations locales — Session /prime

### P0 — Santé du vault (6 correctifs)
- Fix 4 broken links `[[_meta/*]]` → markdown links standard dans `wiki/index.md`
- Intégration 4 notes orphelines dans l'index + backlinks sortants
- Fix freshness mismatch `volatile→evergreen` : context-session.md, log.md, brain.py:310
- Renommage `Daily/README.md` → `Resources/daily-notes.md`
- Suppression 4 doublons staging dans `_staging/recherche/` (déjà promus dans Intelligence/)
- Regénération health.md → 93% (14/15)

### P0.5 — Profil utilisateur
- Création `wiki/Context/profil-utilisateur.md` depuis `raw/private/documents/instructions.md`
- Type `contexte`, sensitivity `private` — profil Sébastien/Skewstony, règles, projets

### P1 — Scripts améliorés (5 modifications)
- **utils.py** : parse_frontmatter() BOM optionnel, build_frontmatter() `derived_from` structuré
- **ingest.py** : plus de duplication — importe les parsers depuis `utils.py`
- **prime_hook.py** : limites lues depuis `config.json` au lieu de hardcodées
- **embed.py** : retry Tenacity (3 tentatives) sur Jan + OpenAI, timeout depuis `config.json`
- **lint.py** : incoming link graph O(n) au lieu de O(n²)

### P2 — Tests & CI (27 nouveaux tests)
- `test_ingest.py` : 17 tests (slugify, BOM, frontmatter, defaults)
- `test_lint.py` : 10 tests (kebab-case, frontmatter, type, daily, stray)
- **75/75 tests passés** (était 48)
- CI GitHub Actions déjà existant — aucune modification nécessaire

### Restant
- `size_policy` : 12 notes sous 300 mots (expansion contenu à faire — Phase P3)
- Fusion doublons Intelligence/ (plan-agent-system ↔ agent-system-architecture, etc.) — dépriorisé

---

## 2026-05-20

### 21:46 — Lint & Correctifs vault

- **Commande:** `/lint` + `/save`
- **Action:** Audit complet vault → 19 titres frontmatter ajoutés, tags health.md, 3 liens Daily réparés, 7 liens courts normalisés (chemins complets), alias registry rebuild
- **Résultat:** ✅ Vault nettoyé, 0 liens cassés, 0 orphelins, alias registry 21 entrées
- **Temps:** 30 min

### 22:30 — Cleanup worktree obsolète + schema v3 sur Supabase remote

- **Commande:** `/prime` (auto-context) + session interactive
- **Action:** Inspection worktree `agents/source-command-review` (3 fichiers uncommitted) → constaté obsolète (master déjà mieux : tenacity, pagination `get_remote_entries`, RPC sans hack `content`). Cleanup complet : `git restore` modifs, drop 3 stashes redondants (migration:master-* identiques en stats), `git worktree remove`, `git branch -D`. Migration schema v3 sur Supabase remote `ottoqbwctcpzzdfzewdi` en 3 chunks (`schema_v3_vault`, `schema_v3_brain`, `schema_v3_rls_maintenance`) — drop 3 contraintes legacy (`vault_entries_type/status/source_check`) + migration 2 rows `type='note'` (Daily/2026-05-11 → `daily`, Intelligence/integration-jan-cowork → `decision`)
- **Résultat:** ✅ 11 tables, 12 nouvelles colonnes (`content_hash`, `freshness`, `sensitivity`, etc.), 5 fonctions (dont RPC `upsert_memory_with_history` 6 params), 8 contraintes CHECK v3. `sync.py status` OK (10 local / 17 remote / 9 synced), 68/68 tests verts.
- **Restant:** 1 note fantôme remote (`Intelligence/integration-jan-cowork.md`) à investiguer ; écart 17 remote vs 10 local à explorer
- **Temps:** 45 min

## 2026-05-21

### 00:15 — Code Review _scripts/ + Correctifs

- **Commande:** `/review` + `/save`
- **Action:** Review complète des 3 scripts vault (brain.py, sync.py, utils.py) + tests. P0: fusion fonctions Jan dupliquées (cmd_import_jan/cmd_export_jan → import_jan_memory/export_jan_memory). P1: --force flag sur cmd_pull (écrasement remote si content_hash différent). P1: 31 nouveaux tests (hash, sanitize, lock, working_dir, strip_bom, extract, wiki_links, pull/force, alias_registry, rename_suggest). P2: imports nettoyés, EXCLUDED_SCAN_DIRS mutualisé dans utils.py, assertion redondante supprimée, SECTION_TO_FOLDER harmonisé.
- **Résultat:** ✅ 68/68 tests verts (était 27), ~160 lignes supprimées, 31 nouveaux tests (+115%)
- **Temps:** 30 min

### 11:15 — Plan #2 — Cleanup follow-ups + réconciliation Supabase

- **Commande:** /plan #2 + actions interactives
- **Action:** Diagnostic `sync.py status` (10/17/9) révèle **root cause** : pas de UNIQUE constraint sur `vault_entries.obsidian_path` → 7 doublons remote (push créait au lieu de merge). Migration `dedup_vault_entries_keep_latest` : delete 7 anciens IDs (versions du 2026-05-07, garde 2026-05-14). Migration `add_unique_vault_entries_obsidian_path` : UNIQUE constraint ajoutée. 1 note fantôme remote (`wiki/Intelligence/integration-jan-cowork.md`, 5467 oct., type=decision, créée dans session checkpoint `84796a4` jamais mergé sur master) → pull local. Cleanup : `Context/profil-utilisateur.md` racine (0 oct.) supprimé + `Context/` rmdir. Worktree orphelin `opencode/mighty-panda` (pointait vers ex-path `D:/Dev/base-de-donnees`) → cleanup manuel `.git/worktrees/mighty-panda`, branche `opencode/mighty-panda` supprimée.
- **Résultat:** ✅ 10/10 synced (1 only-local context-session.md normal), 0 doublon, 0 fantôme, UNIQUE constraint en place. Repo : -1 branche, -1 dossier root, +1 note pulled.
- **Restant:** 2 worktrees orphelins claude/* (Permission denied récurrent — redémarrage requis)
- **Temps:** 45 min

## 2026-05-20

### 12:02 — Phase 1 Fiabilité — 4 sous-systèmes livrés

- **Commande:** Session interactive (build)
- **Action:** Implémentation Phase 1 complète :
  1. **Confidence scoring dérivé** (`utils.py:compute_confidence_score`) — 11 signaux heuristiques (source_type, freshness, citations, stale, lineage_depth, sources multiples, âge, review_status, summary, tags) → score 0.0-1.0 + label high/medium/low
  2. **Lineage transitif** (`utils.py:compute_lineage_depth`) — dérivation 0-3+ (original → raw → enriched → further)
  3. **Stale detection** (`utils.py:check_source_stale`) — invalidation avec status `needs_reingest` / `partially_outdated` / `stale`, stocké dans `vault_entries.stale_status` + `stale_reason`
  4. **Human validation workflow** — `review_status: draft → reviewed → verified → canonical` avec CHECK constraint, score dérivé (−0.10 draft, +0.25 canonical)
  5. **Embedding versioning** — `vault_embeddings.chunking_strategy` + `tokenizer_hash`
  6. **Concept map** — `wiki/_meta/entities.yaml` (7 entités, `depends_on`, `related_notes`)
- **Schema:** 7 nouvelles colonnes idempotentes (`confidence_score`, `confidence_signals`, `lineage_depth`, `derived_from`, `review_status`, `stale_status`, `stale_reason`), 2 CHECK constraints, embedding versioning fields
- **Résultat:** ✅ 90/90 tests verts (+22 nouveaux tests vs 68)
- **Temps:** 45 min

### 22:00 — Pipeline staging v3.1.0 + Ingest test

- **Commande:** Session multitasking subagents
- **Action:** Implementation pipeline staging complet :
  1. `wiki/_meta/manifest.yaml` cree — source de verite machine (v3.1.0, TTL staging, allowed values, defaults)
  2. `wiki/_staging/.gitkeep` cree — dossier inbox ephemerephemere
  3. `skills/ingest.md` reecrit — cible `_staging/` flat avec `status: staging` obligatoire
  4. Agent SKILL.md (ingest) synchronise
  5. `skills/lint.md` — check #6 stale-staging ajoute avec actions interactives p/a/k/s
  6. Agent SKILL.md (lint) synchronise
- **Ingest test:** `raw/notes/notion_second_brain_project_overview_fr.md` → `wiki/_staging/architecture-second-brain.md`
- **Resultat:** ✅ 90/90 tests verts, pipeline staging operationnel

## 2026-05-20

### 13:50 — Brainstorm + Sprints S1→S3 Hybrider Jan+Vault

- **Commande:** `/brainstorm` → `/brainstorm save` → implémentation 3 sprints
- **Action:**
  1. **S1 RAG minimal** — `_scripts/rag_bridge.py` créé (retrieve, chunk_by_sections, BM25 fallback, logs), handler `rag-retrieve` dans brain.py, 22 tests
  2. **S2 Injection context + Dashboard** — `format_context()` (role:context structuré), `_scripts/rag_dashboard.py` (--stats, --recent, --anomalies), 17 tests
  3. **S3 Event log central** — `schema/supabase.sql` enrichi (vault_events table), `_scripts/event_log.py` (push, process, status), handler `events` dans brain.py, 22 tests
- **Résultat:** ✅ 151 tests verts (était 90), architecture 3 couches validée, zéro régression
- **Architecture:** RAG (S1→S2) → Persistence (S3→S4) → Enrichment (S5→S6), couches indépendantes avec gates de validation
- **Nouvelles commandes:** `python brain.py rag-context`, `python rag_dashboard.py --stats`, `python brain.py events push/process/status`
- **Temps:** ~2h

### 22:00 — S4+S5+S6 parallèles + Déploiement v3.2 remote

- **Commande:** `/brainstorm continue` → implémentation 3 sprints en parallèle via subagents
- **Action:**
  1. **S4 Memory Store** — `_scripts/memory_store.py` (store/search/context sessions vectorisées), handler `memories` dans brain.py, 19 tests
  2. **S5 Feedback Pipeline** — `_scripts/feedback_pipeline.py` (3-state: raw→validated→promoted, seuil 3 occurrences), handler `feedback` dans brain.py, 15 tests
  3. **S6 Graph Extractor** — `_scripts/graph_extractor.py` (relations si confidence>0.7 ou type=decision, stockage obsidian_path text), handler `graph` dans brain.py, 15 tests
  4. **Schema v3.2** — 3 tables Supabase (vault_memories, vault_feedback, vault_relations) avec RLS, CHECK constraints, pgvector
  5. **Fix cross-project** — graph_extractor lit vault_entries via SUPABASE_URL (anon), écrit vault_relations via BRAIN_URL (service_role)
- **Déploiement remote:** 3 tables créées sur BRAIN_URL (wusyqgxzyqifpgmxxbkf) via Management API + PAT
- **Résultat:** ✅ 209 tests verts (était 151, +58 nouveaux, zéro régression)
- **Nouvelles commandes:** `python brain.py memories store|search|context`, `python brain.py feedback collect|validate|promote|status`, `python brain.py graph extract|query|status`
- **Décision:** vault_relations stocke obsidian_path en text (pas FK UUID) car vault_entries est sur un projet Supabase différent
- **Temps:** ~30 min

## 2026-05-21

### 17:00 — Code Review + Correctifs sécurité (3 fichiers)

- **Commande:** `/review` (3 agents parallèles) + `/save`
- **Action:** Review complète brain.py (836 lignes), sync.py (499 lignes), supabase.sql (557 lignes) → 8 bloquants, 21 avertissements identifiés. Correctifs appliqués :
  - **supabase.sql** — RLS ajoutée sur 5 tables sans protection (vault_profile, vault_journal, vault_transactions, vault_snapshots, vault_sections), index unique sur matview (débloque REFRESH CONCURRENTLY), REVOKE anon accès matview, search_path='' sur 4 fonctions, REVOKE EXECUTE fonctions mutables (service_role only), CHECK slug/status, FK feedback.event_id, index session_id
  - **brain.py** — Lazy loading (BRAIN_URL/KEY/HEADERS/TIMEOUT → @lru_cache, import safe sans .env), sys.exit()→return int dans load/save (plus de kill process), validation payload anti-DoS, N+1 parallélisé (ThreadPoolExecutor 4 workers), _atomic_write() extrait, regex Jan fixée (start-of-file), early exit summarize, FR→EN messages
  - **sync.py** — import subprocess en haut, _maybe_embed passe par stdin (safe UTF-8, pas --text argv)
- **Résultat:** ✅ 209/209 tests verts (zéro régression)
- **Temps:** 20 min

### 17:45 — Dépendance PyYAML installée et validation tests

- **Commande:** `/save`
- **Action:** Installation de `PyYAML`, relance de `python -m pytest _scripts/tests/test_sync.py` puis du suite complète `_scripts/tests`.
- **Résultat:** ✅ 210 passed, environnement _scripts_ validé, erreur `ModuleNotFoundError: No module named 'yaml'` corrigée.
- **Temps:** 10 min

---

## 2026-05-21

### 12:30 — UKP v1 Runtime déployé (Universal Knowledge Protocol)

- **Commande:** `/save`
- **Action:** Analyse architecturale + implémentation UKP v1 : passage d'un vault Obsidian à un runtime agentique universel. Migration SQL déployée (11 nouvelles tables : `tools_registry`, `tool_calls`, `context_profiles`, `ide_clients`, `session_events`, `resources_registry`, `agent_permissions`, `vault_events`, `vault_memories`, `vault_feedback`, `vault_relations`). 3 Edge Functions Supabase déployées (`ukp-discover`, `ukp-query`, `ukp-session`). Schema local mis à jour (`schema/supabase.sql`). Seed data peuplée (5 outils, 1 profil RAG, 5 ressources MCP).
- **Décisions:**
  - `tool_calls` = priorité #1 (observabilité, sinon runtime aveugle)
  - `context_profiles` = cerveau du système (stratégie RAG serveur, pas IDE)
  - Séparation nette tools / resources (MCP compliant)
  - Edge Functions = orchestration fine, pas monolithe
  - `session_events` en identity bigint pour timeline agentique
- **Résultat:** ✅ 22 tables total, 3 Edge Functions, contrat runtime stabilisé. Prochaine étape : SSE streaming + MCP native server + workers async (pgmq).
- **Temps:** 45 min

## 2026-05-21

### 13:30 — UKP v1.1 — MCP Server + SDK + Hooks IDE

- **Commande:** `/save`
- **Action:** Implémentation couche MCP standard + SDK multi-IDE. 2 Edge Functions créées (`ukp-mcp`, `ukp-stream`), 1 SDK TypeScript zéro-dépendance (`supabase/ukp-client.ts`), 3 configurations IDE mises à jour.
- **Nouveautés:**
  - **`ukp-mcp`** — Serveur MCP standard (JSON-RPC 2.0) avec `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`. Support batch requests, audit via `ukp_record_tool_call`.
  - **`ukp-stream`** — Streaming SSE temps réel (polling session_events/2s, keepalive 30s, subscribe/emit/health).
  - **`supabase/ukp-client.ts`** — SDK TypeScript zéro dépendance avec `UKPClient` (prime, query, session, MCP, context builder, retry/cache).
- **Configurations:**
  - `~/.claude/settings.json` → `mcpServers.ukp` ajouté
  - `~/.config/opencode/opencode.json` → `mcp.ukp` ajouté
  - `~/.claude/CLAUDE.md` → section UKP ajoutée
  - `claude-commands/ukp.md` → commandes `/ukp` créées
  - `CLAUDE.md` (projet) → section UKP + SDK quickstart
- **Livrables:**
  - `supabase/functions/ukp-mcp/index.ts` — 250 lignes, deployed ✅
  - `supabase/functions/ukp-stream/index.ts` — 120 lignes, deployed ✅
  - `supabase/ukp-client.ts` — 350 lignes, sauvegardé localement
  - `claude-commands/ukp.md` — documentation utilisateur
- **Décisions:**
  - `ukp-mcp` sans JWT (service_role interne), CORS ouvert pour IDE
  - Resources URI `vault://notes/{path}`, `vault://projects/{slug}`, etc.
  - SDK pur `fetch` — pas de dépendance supabase-js dans le client
  - Cache discovery 5 min pour éviter appels redondants
- **Résultat:** ✅ 5 Edge Functions total, 22 tables, 1 SDK, 3 configs IDE. N'importe quel IDE compatible MCP peut interroger le vault sans implémentation custom.
- **Tests:** 210/210 passés
- **Temps:** 45 min

## 2026-05-21

### 12:55 — UKP v1.2 — Réconciliation + Seed + Sources versionnées

- **Commande:** `/save`
- **Action:** Migration complète UKP v1.2 en 4 phases :
  1. **Schema** — `query_vector_hybrid` RPC créé (manquant → path vectoriel cassé dans ukp-query), `vault_embeddings` columns `chunking_strategy` + `tokenizer_hash` ajoutées, 3 indexes UKP performance
  2. **Edge Functions** — Sources de `ukp-discover`, `ukp-query`, `ukp-session` pullées depuis déploiement remote et versionnées dans `supabase/functions/` (manquaient du repo)
  3. **Seed data** — `supabase/seed/01_tools.sql`, `02_profiles.sql`, `03_resources.sql` créés (5 tools, 3 profiles, 6 resources)
  4. **Configs IDE** — Vérifié : `.claude/settings.json` (mcpServers.ukp), `.config/opencode/opencode.json` (mcp.ukp), `CLAUDE.md` (section UKP), `claude-commands/ukp.md` (doc utilisateur) — tous synchronisés
- **Décisions:**
  - `query_vector_hybrid` = FTS wrap pour compatibilité immédiate (upgrade vector search via pg_net + OpenAI plus tard)
  - Le path vectoriel de ukp-query tombait silencieusement sur FTS only avant ce fix
  - Les sources EF sont maintenant versionnées dans le repo (phase B critique)
- **Schéma:** Migration `20260521_ukp_v1_2_reconcile` appliquée remote ✅
- **Résultat:** ✅ 22 tables stables, 5 Edge Functions versionnées, 210 tests verts
- **Temps:** ~30 min

## 2026-05-21

### 19:00 — Cleanup v3.2 complet (8 agents parallèles, 3 phases)

- **Commande:** Multi-agent (8 sous-tâches) + `/save`
- **Action:** Plan complet d'assainissement vault exécuté en 3 phases parallélisées :
  **Phase 0** — Fix `VAULT_PATH` dans `_scripts/.env` (D:\base-de-donnees → D:\OneDrive\Developpement\BDDClaude), git init premier commit
  **Phase 1A** — Santé & Lint : rebuild alias_registry (14 entries, 34 refs), 6 checks lint (0 orphelins, 0 liens cassés, 0 stale), index mis à jour, `health.md` créé (83%)
  **Phase 1B** — Sync & Remote : migrations v3.2 déployées (3 tables vault_memories/vault_feedback/vault_relations), réconciliation UKP v1.2 déployée (query_vector_hybrid RPC, chunking_strategy + tokenizer_hash)
  **Phase 1C** — Expansion notes courtes : 10 fichiers enrichis, +1,745 mots ajoutés (cowork-ia 129→370, second-brain-kit 100→370, subagent-workflows 79→350, architecture-electron 135→480, etc.)
  **Phase 2A** — Manifest bump `v3.1.0 → v3.2.0`, staging promue → `Intelligence/architecture-second-brain.md`, CLAUDE.md header synchronisé, index.md mis à jour
  **Phase 2B** — Plan vector search écrit (`.opencode/plans/vector-search-plan.md`) — P2 différé
  **Phase 2C** — `_system/` infra créée (cache, locks, jobs, snapshots, transactions, hashes), `_compressed/` créé, index.md mis à jour
  **Phase 3A** — 210/210 tests verts (17.15s)
  **Phase 3B** — Save + commit final
- **Résultat:** ✅ Vault v3.2.0 nettoyé, 16 notes wiki, 6/6 checks lint passés, 210 tests, 9 commits total
- **Restant:** Déploiement tables v3.2 sur BRAIN project (wusyqgxzyqifpgmxxbkf), vrai vector search (P2), sync.py status à vérifier avec clé service
- **Temps:** ~15 min
