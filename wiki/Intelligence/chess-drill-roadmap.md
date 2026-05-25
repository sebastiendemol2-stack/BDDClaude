---
title: "Chess Drill — Roadmap et Dette Technique"
date: 2026-05-24
tags: [chess-drill, roadmap, refactorisation, dette-technique, phase1]
type: decision
status: active
confidence: high
source_type: raw
freshness: volatile
sensitivity: internal
derived_from:
  - path: raw/docs/15-roadmap-refactorisation.md
    relation: source
  - path: raw/docs/17-dettes-techniques-et-bugs.md
    relation: source
  - path: raw/docs/21-plan-phase-1-stabilisation.md
    relation: source
---

# Chess Drill — Roadmap et Dette Technique

## Roadmap refactorisation (12 phases)

| Phase | Objectif | Statut |
|-------|---------|--------|
| **0** — Audit et documentation | Figer la connaissance actuelle | Terminé |
| **1** — Stabiliser l'existant | Corriger incohérences critiques sans changer le produit | À faire |
| **2** — Séparer modes edition/resolution/solution | Clarifier responsabilités fonctionnelles | À faire |
| **3** — Nettoyer le JavaScript | Modulariser logique frontend | À faire |
| **4** — Nettoyer le backend | Découper par domaine, uniformiser contrats | À faire |
| **5** — Clarifier la base de données | Aligner schéma réel et code + préparer gamification | À faire |
| **6** — Créer une première interface propre | Design system minimal cohérent | **Démarré** (tokens + shell mobile + world map v1) |
| **7** — Ajouter XP simple | Boucle motivation MVP | À faire |
| **8** — Ajouter vies/streak | Renforcer habitude quotidienne | À faire |
| **9** — Ajouter niveaux | Structurer montée en difficulté | À faire |
| **10** — Ajouter carte de progression | Vision macro parcours | À faire |
| **11** — Ajouter récompenses | Renforcer engagement long terme | À faire |
| **12** — Préparer une version stable | Figer une release fiable | À faire |

**État Phase 6 (2026-05-20)** : design tokens + shell mobile + world map v1 implémentés. Prochaine étape : brancher données réelles de progression sur HUD/map.

## Dette technique identifiée

### Critique (risque crash)

| Bug | Symptôme | Fichiers |
|-----|---------|----------|
| **A** — `sortOrder` manquant | Tri solutions sans colonne SQL → erreur SQL runtime | `backend/migrations/schema.sql`, `models/index.js`, `controllers/index.js` |
| **B** — Import invalide `updateSolution` | PuzzleModel importé depuis services au lieu de models → crash endpoint | `backend/src/controllers/index.js` |
| **C** — `AuthorizationError` sans import | ReferenceError sur chemins d'autorisation | `backend/src/controllers/index.js` |
| **D** — Mapping `main_line`/`mainLine` admin | Affichage/édition solution silencieusement incorrect | `frontend/src/components/admin/PuzzleEditor.jsx` |

### Important

- Nommage incohérent API/front : `main_line`/`mainLine`, `library_id`/`libraryId`, `order_index`/`orderIndex`
- PuzzleSolver et TrainingPage trop chargés (forte probabilité régression)
- Contrat de réponse API non strictement homogène

### Moyen / Faible

- Styles inline massifs (cohérence UI limitée)
- Double chargement bibliothèques dans TrainingPage
- Terminologie hétérogène (library/run/session)

## Plan phase 1 — Stabilisation

**Périmètre strict** : correctifs minimaux, localisés, testés immédiatement. Aucun changement de comportement utilisateur.

### Ordre d'intervention

1. **Corriger C** (AuthorizationError import) — rapide, sécurise contrôle d'accès
2. **Corriger B** (import updateSolution) — évite crash endpoint
3. **Corriger A** (sortOrder schéma + modèle) — aligne persistance
4. **Corriger D** (mapping frontend admin) — fiabilise UI admin

### Critères de validation par bug

**C** : accès non autorisé → 403 JSON propre, pas ReferenceError\
**B** : PUT `/api/puzzles/solutions/:id` fonctionne, erreur invalide propre\
**A** : GET puzzle avec solutions OK, reorder persistant, aucune erreur SQL\
**D** : create/edit/delete/branch/reorder solution OK, moves + tree cohérents

### Test final de non-régression (obligatoire)

1. Auth : register / login / profile / logout
2. Training : start run → résoudre puzzle → complete
3. Exploration : ouvrir bibliothèque → résoudre librement
4. Profile : consulter sessions + review errors
5. Admin : CRUD library + puzzle + solution

### Ce qu'il ne faut PAS modifier en phase 1

- Aucune refonte de structure fichiers
- Aucun redesign UI
- Aucun ajout feature gameplay
- Aucune gamification
- Aucun changement de contrat API non nécessaire

## Addendum — Boucle mock locale validée (2026-05-20)

Tests ciblés passés : `trainingSessionReducer`, `endOfLevelMockData`, `worldMapMockData`, `TrainingScreenPage.logic`\
Build frontend : OK (warnings préexistants hors périmètre)

Périmètre validé : World Map → Training mock → End Of Level Flow → retour World Map + persistance localStorage.

## Voir aussi

- [[Context/chess-drill]] — contexte projet
- [[Intelligence/chess-drill-architecture]] — architecture et modules
- [[Intelligence/chess-drill-gamification]] — mécaniques et boucle de jeu
