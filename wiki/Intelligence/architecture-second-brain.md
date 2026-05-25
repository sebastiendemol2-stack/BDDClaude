---
title: "Architecture du Second Brain"
date: 2026-05-20
tags: [architecture, second-brain, systeme, vision]
type: concept
status: active
confidence: medium
source: raw/notes/notion_second_brain_project_overview_fr.md
source_path: raw/notes/notion_second_brain_project_overview_fr.md
source_type: raw
freshness: volatile
sensitivity: internal
review_status: reviewed
memory_tier: stable
---

# Architecture du Second Brain

## Pipeline documentaire

Le systeme suit un pipeline strict en 4 etapes avec validation a chaque palier :

### 1. `raw/` — Acquisition
L'humain depose du contenu brut : notes manuscrites, articles web clippes (Obsidian Web Clipper), documents PDF, fichiers recus, idees temporaires. **Immutabilite absolue** : rien dans `raw/` n'est modifie par l'IA ou un script. Le dossier est organise en sous-dossiers : `raw/notes/`, `raw/clippings/`, `raw/docs/`. Frontmatter minimal ou absent.

### 2. `_staging/` — Compilation
Le LLM (via la commande `/ingest`) compile les sources `raw/` en notes structurees dans `wiki/_staging/`. Chaque note recoit un frontmatter complet (date, tags, type, status: staging, confidence, source_type, etc.), un `derived_from` tracant la provenance, et des [[wiki links]] entrants/sortants. Les notes staging ont une duree de vie max de 7 jours — au-dela, elles sont archivees ou promues.

### 3. `wiki/` — Stabilisation
Validation humaine (ou automatique si confiance > threshold) → promotion du staging vers `wiki/` avec `status: active`. La note entre dans le graphe de connaissance permanent. Le `_staging/` est nettoye. Le `wiki/index.md` est mis a jour si necessaire. Les liens brises sont detectes par `/lint`.

### 4. Supabase sync — Distribution
`_scripts/sync.py` synchronise les notes `wiki/` vers Supabase. Sync incremental : skip si `content_hash` unchanged. Refuse les notes `sensitivity: private|sensitive`. Cree les entrees dans `vault_entries`, et les embeddings dans `vault_embeddings` (multi-provider). Les `vault_links_from` sont derivees automatiquement depuis les [[wiki links]].

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
