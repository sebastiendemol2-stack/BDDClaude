---
title: "Second Brain Kit Vault"
date: 2026-05-07
tags: [obsidian, second-brain, vault]
type: contexte
status: active
confidence: high
source_type: extraction
freshness: volatile
sensitivity: internal
---

# Second Brain Kit Vault

Systeme de gestion de connaissances Obsidian integre a Cowork App.

## Localisation

- docs/vault/ (integre au projet Cowork App)
- C:\base de donnees\ (Obsidian local)
- Supabase (projet ottoqbwctcpzzdfzewdi) — backend cloud requetable

## Schema v3 — Architecture complete

Le vault suit une architecture en 7 zones (au lieu des 3 couches initiales) :

### Zones principales
- **raw/** : Espace humain immutable — brainstorming, drafts, scratchpads, clippings web, PDFs. Jamais modifie par l'IA.
- **wiki/** : Connaissance stabilisee, compilee par LLM via `/ingest`. Contient Context/, Intelligence/, Resources/, Daily/.
- **wiki/_staging/** : Memoire de travail temporaire — notes en cours de validation, max 7 jours avant promotion ou archive.
- **wiki/_meta/** : Metadonnees du vault — manifest.yaml (source de verite machine-readable), entities.yaml, alias_registry.yaml, health.md.
- **wiki/_system/** : Infrastructure interne — cache, locks, transactions, jobs, snapshots, hash indexes.
- **wiki/_compressed/** : Meta-notes consolidees pour les vaults de >200 notes (Phase 4).
- **skills/** : References CLI chargees par Claude Code via le skill tool.

## Backend Supabase

Projet ID : `ottoqbwctcpzzdfzewdi` — region eu-central-1.

Tables :
- `vault_sections` : Categories du vault
- `vault_entries` : Notes wiki synchronisees (35+ colonnes, sans embedding)
- `vault_embeddings` : Multi-provider (provider, model, dim, embedding) — table separee
- `vault_chunks` : Chunks pour notes longues (>512 tokens)
- `vault_transactions` : Audit des staging→wiki promotions
- `vault_snapshots` : Temporal graph snapshots (Phase 4)
- `vault_profile` : Profil utilisateur
- `vault_journal` : Journal chronologique par projet
- `vault_links_from` : Vue derivee (links_to inverses)

## Workflow sync

```bash
python _scripts/sync.py push        # Local → Supabase (skip private/sensitive)
python _scripts/sync.py pull        # Supabase → Local
python _scripts/sync.py status      # Compare les deux cotes
```

Sync incremental : skip si `content_hash` unchanged. Refuse push si `sensitivity ∈ {private, sensitive}`.

## Commandes CLI

/prime, /ingest, /save, /query, /lint, /brainstorm, /review, /audit, /doc, /refactor, /explain

## Liens

- [[Context/cowork-ia]]
- [[Intelligence/context-engineering]]
