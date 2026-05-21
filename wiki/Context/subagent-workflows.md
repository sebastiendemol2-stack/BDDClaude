---
title: "Subagent Workflows"
date: 2026-05-07
tags: [subagents, ipc, architecture]
type: contexte
status: active
confidence: high
source_type: extraction
freshness: volatile
sensitivity: internal
---

# Subagent Workflows

Dispatch de sous-agents specialises via /dispatch-subagent.

## 3 patterns

### Synthesis
Extraction de patterns cross-thematiques a partir d'un ensemble de notes. Utilise un modele `haiku` pour analyser les correlations entre notes de differents dossiers (Context + Intelligence + Resources). Produit un resume structure avec `[[wiki links]]` suggeres pour renforcer le graphe de connaissances.
**Quand l'utiliser** : apres un `/ingest` pour connecter les nouvelles notes au reseau existant, ou avant un `/lint` pour detecter les duplications.

### Research
Documentation thematique structuree a partir de sources fournies. Prend un ensemble de sources (notes wiki, fichiers raw, articles web) et produit une note wiki complete avec frontmatter, sections, et liens. Modele `haiku` par defaut, `sonnet` pour les sujets complexes.
**Quand l'utiliser** : quand on veut compiler des informations dispersees en une note de reference unique et bien structuree.

### Analysis
Audit complet de projet avec health score. Evalue la coherence du code, la qualite de l'architecture, la couverture des tests, et la securite. Produit un rapport structure avec scores (0-100) par dimension et recommandations actionnables.
**Quand l'utiliser** : avant un refactoring majeur, pour evaluer la dette technique, ou comme check de qualite avant release.

## Communication IPC

Le dispatch suit un pattern request/response via canaux dedies :
1. Renderer envoie `dispatch-subagent` avec `{ pattern, params, model }`
2. main.cjs verifie la memoire subagent (cache TTL dans subagent-memory.json)
3. Le sous-agent execute via le modele selectionne (defaut: haiku)
4. Reponse structuree retournee au renderer

10 canaux copilot sont pre-definis dans main.cjs mais pas encore connectes au renderer — ils seront actives avec le copilot IDE en phase 4.

## Liens

- [[Context/cowork-ia]]
