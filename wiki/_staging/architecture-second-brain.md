---
date: 2026-05-20
tags: [architecture, second-brain, systeme, vision]
type: concept
status: staging
confidence: medium
source: raw/notes/notion_second_brain_project_overview_fr.md
source_path: raw/notes/notion_second_brain_project_overview_fr.md
source_type: raw
freshness: volatile
sensitivity: internal
review_status: draft
---

# Architecture du Second Brain

## Pipeline documentaire

Le systeme suit un pipeline strict en 4 etapes : `raw/` → `_staging/` → `wiki/` → Supabase sync.

Chaque couche a un role precis : l'humain ecrit dans `raw/`, le LLM compile dans `_staging/`, la validation promeut dans `wiki/`, et `sync.py` synchronise vers le cloud.

## Principes fondateurs

- **Immutabilite humaine** : `raw/` n'est jamais modifie par l'IA
- **Pas de note orpheline** : chaque note appartient a un reseau de [[wiki links]]
- **Compilation controlee** : pas de promotion automatique sans validation
- **Fiabilite avant intelligence** : coherence, tracabilite, provenance avant performance retrieval

## Stack technique

- Frontend : Obsidian + Markdown + frontmatter structure
- Backend cloud : Supabase + PostgreSQL (pgvector prevu)
- Scripts : Python (sync.py, brain.py, utils.py)
- IA : Claude Code + skills personnalises + workflows multi-agents

## Vision long terme

Le projet evolue de "Vault Obsidian" vers un "Agentic Memory Runtime" en 4 phases :
1. Vault Obsidian
2. Second Brain
3. Knowledge OS
4. Agentic Memory Runtime

L'objectif final est une infrastructure personnelle de connaissance capable de survivre dans le temps, rester fiable malgre les agents IA, et servir de base a des workflows autonomes.

## Chantiers futurs

- Gouvernance semantique (entites canoniques, detection duplications)
- Temporalite (snapshots historiques, replay)
- Retrieval hybride (embeddings, pgvector, hybrid search)
- Confiance & lineage (confidence scoring automatique, provenance transitive)

## Liens connexes

- [[Context/second-brain-kit]] — le vault schema lui-meme
- [[Resources/architecture-electron]] — architecture technique Electron
- _systeme agent (note a creer)_
