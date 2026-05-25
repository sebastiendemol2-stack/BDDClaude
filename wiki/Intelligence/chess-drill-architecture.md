---
title: "Chess Drill — Architecture"
date: 2026-05-24
tags: [chess-drill, architecture, frontend, backend, modules]
type: recherche
status: active
confidence: high
source_type: raw
freshness: volatile
sensitivity: internal
derived_from:
  - path: raw/docs/04-architecture-actuelle.md
    relation: source
  - path: raw/docs/05-architecture-cible.md
    relation: source
  - path: raw/docs/06-structure-fichiers.md
    relation: source
  - path: raw/docs/08-api-et-backend.md
    relation: source
  - path: raw/docs/09-frontend-et-ui.md
    relation: source
  - path: raw/docs/16-conventions-code.md
    relation: source
---

# Chess Drill — Architecture

## Architecture actuelle

### Structure monorepo

```
backend/
  src/server.js           — bootstrap serveur/middleware/routes
  src/models/index.js     — accès SQL centralisé (tous domaines)
  src/services/index.js   — logique métier sessions/validation
  src/controllers/index.js — orchestration HTTP (trop gros)
  src/routes/*.js         — exposition endpoints
  src/validators/index.js — schémas Joi
  migrations/schema.sql   — DDL actuel

frontend/
  src/pages/TrainingPage.jsx      — orchestration session (trop gros)
  src/components/chessboard/PuzzleSolver.jsx — cœur résolution (trop gros)
  src/components/admin/*          — édition contenu
  src/services/api.js             — client HTTP
```

### Dépendances réelles

```
Frontend → services/api.js → Backend routes → Controllers → Services → Models → MySQL
chess.js utilisé des deux côtés (frontend: résolution, backend: validation lignes)
```

### Problèmes identifiés

**Responsabilités mélangées** :
- `PuzzleSolver` : logique jeu + timer + réseau + transitions d'état UI
- `TrainingPage` : navigation + orchestration run + mode review + modal session
- `controllers/index.js` : tous domaines dans un seul fichier
- `models/index.js` : toutes entités dans un seul fichier

**Fragilités concrètes** :
- Référence à `sortOrder` sans colonne SQL déclarée → risque erreur SQL
- Import invalide dans `updateSolution` (PuzzleModel depuis services au lieu de models)
- `AuthorizationError` utilisé sans import dans contrôleurs run → ReferenceError
- Nommage incohérent : `main_line` vs `mainLine`, `library_id` vs `libraryId`

## Architecture cible

### Principes

- Simplicité avant sur-ingénierie
- Séparation claire des responsabilités par domaine
- Contrats API stables et typés conceptuellement
- Pas de microservices — API monolithique modulaire

### Séparation des modes

| Mode | Rôle |
|------|------|
| **Edition** | création position + lignes de solution |
| **Resolution** | validation stricte et score de session |
| **Solution** | visualisation pédagogique et replay |

### Séparation état plateau / métier / UI

| Couche | Rôle |
|--------|------|
| Board State Engine | état FEN, coups légaux, orientation, historique |
| Puzzle Domain Engine | validation contre lignes, progression, erreurs |
| UI Layer | composants visuels et feedback |

### Modules frontend cibles

```
frontend/src/modules/
  board/
    boardState.js
    moveFormatter.js
    orientation.js
  puzzle/
    solutionMatcher.js
    puzzleSession.js
    reviewMode.js
  gamification/
    xpEngine.js
    streakEngine.js
    livesEngine.js
  worldMap/       ← implémenté en mock (2026-05-20)
  library/        ← implémenté en mock
  challenges/     ← implémenté en mock
  shop/           ← implémenté en mock
  profile/        ← implémenté en mock

frontend/src/services/game/
  createGameServices.js   ← registre services (source: mock|api)
  gameServiceContracts.js
  adapters/mock/*
  adapters/api/*          ← placeholders, non branchés

frontend/src/styles/
  tokens.css              ← design tokens (implémenté)
  app-shell.css           ← shell mobile (implémenté)
  world-map.css           ← carte mondes (implémenté)
```

### Backend cible (par domaine)

```
backend/src/domains/
  auth/
    route.js | controller.js | service.js | repository.js | validator.js
  libraries/
  puzzles/
  runs/
  progression/
  rewards/
```

### Organisation CSS cible

```
styles/tokens.css
styles/components/*.css
styles/pages/*.css
```

### Règles architecture React

| Couche | Rôle | Interdit |
|--------|------|---------|
| `components/ui/*` | Pure UI, composants atomiques | Appel API, état métier |
| `modules/*` | Logique gameplay, hooks métier | JSX, styles |
| `pages/*` | Composition écran, routing | Logique métier |

**Interdits absolus** :
- Logique métier dans JSX
- Styles inline >5 propriétés
- z-index hardcodé hors tokens
- Animations métier dans composants atomiques

## État couche d'adaptation backend (2026-05-20)

Nouvelle structure permettant migration mock → API sans réécriture composants :
- `gameServices` expose services par domaine (worldMap, trainingSession, endOfLevel, library, challenges, shop, profile)
- Source par défaut : `mock`
- Source future possible : `api` (via `REACT_APP_WORLD_MAP_DATA_SOURCE=api`)
- Adapters API préparés mais non branchés

## Voir aussi

- [[Context/chess-drill]] — contexte projet et stack
- [[Intelligence/chess-drill-roadmap]] — plan de refactorisation
- [[Intelligence/chess-drill-database]] — schéma base de données
