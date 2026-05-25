---
title: "Chess Drill — Admin et Authoring"
date: 2026-05-24
tags: [chess-drill, admin, authoring, puzzle-editor, audit]
type: recherche
status: active
confidence: high
source_type: raw
freshness: volatile
sensitivity: internal
derived_from:
  - path: raw/docs/27-admin-panel-requirements.md
    relation: source
  - path: raw/docs/24-local-puzzle-data-format.md
    relation: enriched_by
---

# Chess Drill - Admin et Authoring

## Portee livree

Le panneau admin fournit une coque UX complete avec ecrans modulaires et etat local/mock. Les integrations backend restent hybrides : les endpoints CRUD existants sont utilises quand ils existent, tandis que les champs pedagogiques et editoriaux peuvent rester dans le stockage mock local.

## Capacites admin

Le panneau admin couvre actuellement :

- gestion des mondes
- gestion des niveaux
- creation et edition de puzzles
- edition FEN
- edition des arbres de solution
- annotations par coup
- explications pedagogiques
- erreurs frequentes
- bibliotheques
- joueurs
- attribution et retrait de XP, coins, vies, hints
- logs
- progression utilisateur
- rewards et badges
- shop items
- audit des changements

## Ecrans

- Dashboard Admin
- Worlds
- Levels
- Puzzles
- Solution Trees
- Libraries
- Players
- Rewards
- Economy
- Logs
- Settings

## Compatibilite data model

Le modele local admin est compatible avec le schema d'authoring du MVP local :

- metadata niveau : `id`, `worldId`, `levelNumber`, `title`
- un objet `puzzle` unique par niveau
- metadata puzzle : `title`, `fen`, `sideToMove`, `theme`, `difficulty`
- blocs pedagogiques : `shortGoal`, `explanation`, `keyIdea`, `commonMistakes`
- `solutionLines[]` avec ids et labels
- `moveAnnotations[]` avec highlights et arrows

## Gaps restants

- Pas encore d'API backend dediee pour metadata pedagogique et annotations de solution tree.
- Pas encore d'audit trail serveur.
- Pas encore de matrice avancee roles/permissions au-dela du route gating admin.

## Audit futur

Les mutations admin serveur devront inclure :

- id utilisateur acteur
- timestamp
- type et id d'entite
- payload avant/apres
- raison et source

## Voir aussi

- [[Context/chess-drill]]
- [[Intelligence/chess-drill-local-mvp]]
- [[Intelligence/chess-drill-architecture]]
- [[Intelligence/chess-drill-roadmap]]
