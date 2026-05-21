---
title: "Brainstorm: Hybrider Jan + Vault → IA + intelligente"
date: 2026-05-20
tags: [brainstorm, jan, rag, memoire, vault, roadmap]
type: concept
status: active
confidence: medium
source_type: synthesis
freshness: volatile
sensitivity: internal
---

## Session

- **Sujet:** Hybrider Jan et base de données (Supabase + vault) pour rendre l'IA plus intelligente
- **Date:** 2026-05-20
- **Objectif:** Plan d'action en sprints avec gates de validation

## Problème identifié

Le vault contient de la connaissance structurée (notes wiki, embeddings, relations) mais Jan n'y a pas accès au moment de répondre. Chaque session part de zéro, sans mémoire du vault ni des sessions passées.

## Architecture retenue

3 couches indépendantes avec gates de validation entre chaque :

```
Retrieval (S1→S2) → Persistence (S3→S4) → Enrichment (S5→S6)
```

Chaque couche est testable sans dépendre des autres.

## Roadmap 6 sprints

### S1 — RAG minimal observable
- 1 embedding provider (Jan local `/v1/embeddings`)
- Chunking section-based simple (`##` split)
- `rag_bridge.py` avec `retrieve(query, top_k=5)`
- Logs `_system/logs/rag_*.jsonl`
- Gate : 5 tests, latency <200ms, logs vérifiables

### S2 — Injection contextuelle + fallback
- Message structuré `role: context` (pas de pollution system prompt)
- Fallback BM25 si Jan embedding timeout
- Dashboard RAG : `--stats`, `--recent`

### S3 — Append-only event log central
- Table `vault_events` dans Supabase
- Jan écrit des events bruts, pas de logique métier
- Worker `cmd_process_events` dérive sessions/mémoire
- Résilient : si Jan crash, events déjà en base

## Implémentation — S4+S5+S6 livrés en parallèle (2026-05-20)

### S4 ✅ — Memory Store (`_scripts/memory_store.py`)
- `store_session()` → persist sessions with embeddings in `vault_memories` (Supabase)
- `search_sessions()` → cosine similarity + BM25 fallback
- `format_session_context()` → `[RELATED_SESSIONS]` block (`role: context`)
- Handlers: `python brain.py memories store|search|context`
- 19 tests

### S5 ✅ — Feedback Pipeline (`_scripts/feedback_pipeline.py`)
- 3 états : `raw_feedback → validated_precedent → promoted_memory`
- Validation à 3 occurrences (déduplication par contenu normalisé)
- `collect_feedback()` avec auto-increment si même contenu
- `validate_feedback()` → promote si >= threshold
- `promote_memory()` → écrit dans `claude_memory` (type=pattern, confidence max medium)
- Handlers: `python brain.py feedback collect|validate|promote|status`
- Table `vault_feedback` dans Supabase
- 15 tests

### S6 ✅ — Graph Extractor (`_scripts/graph_extractor.py`)
- Extraction relations si confidence >0.7 OU type=decision
- `_load_local_entries()` parse frontmatter + wiki links
- `extract_relations()` → sync relations to `vault_relations`
- `query_relations()` → requête entrante/sortante par note
- Jamais injecté automatiquement dans contexte LLM
- Handlers: `python brain.py graph extract|query|status`
- Table `vault_relations` (types: references, decides, depends_on, related_to)
- 15 tests

### Stats
- **209 tests** (était 151, +58)
- **3 nouvelles tables**: `vault_memories`, `vault_feedback`, `vault_relations`
- **4 nouvelles commandes**: `memories`, `feedback`, `graph` (+ `rag-retrieve`, `rag-context`, `events` existants)
- **Zéro régression**

## Connexions vault
- [[Intelligence/integration-jan-cowork]]
- [[Resources/architecture-electron]]
- [[Intelligence/context-engineering]]
- [[Context/cowork-ia]]
- [[Context/subagent-workflows]]
- [[Context/context-session]]
