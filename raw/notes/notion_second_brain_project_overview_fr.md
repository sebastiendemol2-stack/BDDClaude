# 🧠 Second Brain — Knowledge Operating System

> Système de gestion de connaissances personnelles augmenté par IA, construit sur Obsidian + Supabase + Claude Code.

---

# 📌 Vision

Créer un système de mémoire fiable, structuré et évolutif capable de :

- Centraliser la connaissance personnelle et technique
- Compiler automatiquement des notes brutes en connaissances stables
- Alimenter des agents IA avec une mémoire persistante
- Garantir la traçabilité et la fiabilité des informations
- Éviter la dérive documentaire classique des systèmes IA

---

# 🏗️ Architecture globale

## Architecture en 3 couches

| Couche | Dossier | Description |
|---|---|---|
| Humain écrit | `raw/` | Notes brutes, documentation, réflexions humaines — immutable |
| Compilation IA | `wiki/` | Connaissance consolidée et enrichie |
| Infrastructure | `_system/`, `_meta/` | Cache, locks, hashes, manifests, santé du vault |

### Buffer intermédiaire

`wiki/_staging/`

Zone temporaire avant promotion vers le wiki stable.

Fonctions :
- Validation
- Contrôle qualité
- Détection de dérive
- Audit avant publication

---

# ⚙️ Stack technique

## Frontend documentaire

- Obsidian
- Markdown
- Frontmatter structuré

## Backend cloud

- Supabase
- PostgreSQL
- pgvector (prévu)

## Scripts et orchestration

- Python
- `sync.py`
- `brain.py`
- `utils.py`

## IA et agents

- Claude Code
- Skills personnalisés
- Workflows multi-agents

---

# 🧩 Schéma conceptuel

## Pipeline documentaire

```text
raw/
  ↓
_ingest
  ↓
wiki/_staging/
  ↓ validation
wiki/
  ↓
Supabase sync
  ↓
Retrieval / Agents / Query
```

---

# 🗂️ Structure du vault

## Dossiers principaux

### `raw/`

Contenu humain original.

Règles :
- Jamais modifié par IA
- Jamais renommé automatiquement
- Source de vérité primaire

---

### `wiki/`

Connaissance stabilisée.

Contient :
- Synthèses
- Concepts consolidés
- Architecture projet
- Documentation enrichie

---

### `wiki/_meta/`

Métadonnées système.

Exemples :
- Health reports
- Manifests
- Metrics
- Audit logs

---

### `wiki/_system/`

Infrastructure interne.

Exemples :
- Hashes
- Cache
- Locks
- Indexes

---

# 🧠 Fonctionnalités clés

## `/prime`

Charge le contexte global du vault au démarrage d’une session.

---

## `/ingest`

Compile :

```text
raw/ → wiki/_staging/ → wiki/
```

Fonctions :
- Structuration
- Résumé
- Enrichissement
- Classification
- Détection d’alias

---

## `/save`

Sauvegarde :
- Session actuelle
- Daily note
- Historique mémoire

---

## `/query`

Recherche documentaire.

Actuellement :
- BM25
- Fallback grep

Prévu :
- Embeddings
- Hybrid retrieval
- pgvector
- Query routing

---

## `/lint`

Validation santé du vault.

Checks actuels :
- Liens cassés
- Orphelins
- Frontmatter
- Intégrité structurelle
- Cohérence globale

---

# 🗃️ Infrastructure Supabase

## Tables principales

| Table | Rôle |
|---|---|
| `vault_entries` | Documents principaux |
| `vault_chunks` | Segments chunkés |
| `vault_embeddings` | Vecteurs embeddings |
| `vault_transactions` | Historique sync |
| `vault_snapshots` | Snapshots temporels |

---

# 🔒 Principes fondamentaux

## 1. Immutabilité humaine

`raw/` est sacré.

Aucune modification automatique.

---

## 2. Pas de note orpheline

Chaque note doit appartenir à un réseau de connaissances.

---

## 3. Compilation contrôlée

Aucune promotion automatique sans validation implicite du pipeline.

---

## 4. Fiabilité avant intelligence

Le système privilégie :
- la cohérence,
- la traçabilité,
- la provenance,

avant les performances retrieval.

---

# 📈 État actuel

## Version

`v3.0.0`

---

## Santé du système

- 39/39 tests verts
- 0 orphelins
- 0 liens cassés
- Hash normalization stable
- Sync Supabase opérationnel

---

# 🚧 Chantiers futurs

## Gouvernance sémantique

Objectif :
- éviter la dérive des concepts
- introduire des entities canoniques
- détecter les duplications sémantiques

---

## Temporalité

Objectif :
- snapshots historiques
- replay du vault
- état à une date donnée

---

## Retrieval hybride

Objectif :
- embeddings
- pgvector
- hybrid search
- retrieval multi-couches

---

## Confiance & lineage

Objectif :
- confidence scoring automatique
- provenance transitive
- stale synthesis detection
- validation humaine structurée

---

# 🧭 Direction stratégique

Le projet évolue progressivement de :

```text
Vault Obsidian
    ↓
Second Brain
    ↓
Knowledge OS
    ↓
Agentic Memory Runtime
```

---

# 🔮 Vision long terme

Construire une infrastructure personnelle de connaissance capable de :

- survivre dans le temps,
- rester fiable malgré les agents IA,
- devenir une mémoire exécutable,
- servir de base à des workflows autonomes.

---

# 🧠 Résumé exécutif

Second Brain est un système hybride combinant :

- PKM (Personal Knowledge Management)
- Moteur RAG
- Infrastructure documentaire
- Runtime mémoire pour agents IA

avec une priorité forte sur :

> fiabilité, traçabilité et gouvernance documentaire.

