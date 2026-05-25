---
title: "Chess Drill (Maximoute) — Refonte produit gamifié"
date: 2026-05-25
tags: [chess-drill, maximoute, refonte, gamification, ia-assisted]
type: projet
status: active
confidence: high
source_type: synthesis
freshness: volatile
sensitivity: internal
source: raw/notes/conversation maximoute chessdrill.md
derived_from:
  - path: raw/notes/conversation maximoute chessdrill.md
    relation: source
---

# Chess Drill — Refonte produit gamifié

App d'entraînement tactique aux échecs (codename Maximoute) en refonte complète mais **progressive**, pas big-bang. Socle existant viable (auth, libs, puzzles, solutions, sessions, erreurs, revue) ; dette principale = mélange UI/métier/session dans `PuzzleSolver` et `TrainingPage`, gros fichiers backend, incohérences API/DB.

## Vision produit

Transformer une app de drill tactique fonctionnelle en **produit gamifié style Candy Crush des échecs** : mondes, niveaux progressifs, HUD, XP, streaks, vies, missions, badges. Mobile-first, parcours visuel sur worldmap.

## Séquence stratégique (ordre non négociable)

1. **Planification produit + architecture** → Notion = "cerveau produit"
2. **Documentation technique** → `/docs` synchronisée avec Notion = mémoire IA
3. **Copilot** → seulement après cadrage solide, sinon il amplifie la dette

> Le contexte > le prompt — Copilot lancé sans cadre produit des patterns incohérents. Voir [[context-engineering]].

## Plan de refonte (5 phases)

### Phase 1 — Stabilisation technique
Bugs critiques : `sortOrder`, imports invalides, `AuthorizationError`, naming API. Pas de refonte visuelle avant que le cœur soit stable.

### Phase 2 — Clarification produit
Figer les **3 modes** : édition / résolution / solution. Séparation stricte.

### Phase 3 — Refonte architecture frontend
Extraire en modules :
- `modules/board`
- `modules/puzzle`
- `modules/gamification`

Pour alléger `PuzzleSolver` et `TrainingPage`.

### Phase 4 — Refonte backend modulaire
Domaines : `auth` · `libraries` · `puzzles` · `runs` · `progression` · `rewards`.

### Phase 5 — Refonte UI + Gamification
Design system minimal → HUD training → MVP gamif (XP, objectif quotidien, niveau, feedback) → V1 (streak, vies, missions, badges, thèmes).

## Architecture cible

### Frontend
Stores séparés : session / UI / gamification (responsabilités + persistance définies en amont).

### API Convention
- Backend : snake_case
- Frontend : camelCase
- Adapter layer entre les deux
- Fige ces conventions **avant** le refactor

### Error Strategy
Codes erreur, format unifié, mapping bidirectionnel, distinction erreurs **pédagogiques** vs techniques.

## Logique solution tree (cœur métier)

Un puzzle = plusieurs `solutionLines` (arbre de résolution). Au runtime :

- Coup joué → comparé au prochain SAN attendu dans `activeSolutionLines`
- Bon coup → filtre les branches compatibles, avance progression
- Mauvais coup → n'incrémente pas `currentMoveIndex`, incrémente `mistakes`, feedback négatif
- Branches partagées (même préfixe) → restent actives en parallèle
- Branche divergente → éliminée
- Ligne complète terminée → `levelCompleted`
- Seuil de `mistakes` atteint → `levelFailed`

**Indicateur visuel** : `SolutionBubbleProgress` (bulles candy-style) — gris/vert/bleu pour non trouvée / complétée / branche active. Pas de texte "0/3".

## Admin Panel

Refonte UX complète, mock local d'abord, backend après. Navigation : Dashboard · Worlds · Levels · Puzzles · Solution Trees · Libraries · Players · Rewards · Economy · Logs · Settings.

Outils admin essentiels (mock local) : give coins/XP/vies/hints, reset progress, unlock world/level/all, reset shop.

Composants découpés : `AdminPanel`, `AdminSidebar`, `AdminDashboard`, `AdminWorldsPage`, `AdminLevelsPage`, `AdminPuzzleEditor`, `AdminSolutionTreeEditor`, `AdminPlayersPage`, `AdminEconomyPage`, `AdminLogsPage`, `adminMockState`, `adminMockActions`. **Jamais un composant géant.**

## Coding & Refactor Rules

- Max 60 lignes/fonction, composants fins, logique métier pure
- Jamais de logique API dans UI, pas de mutation cachée
- **Refactor** : extraire avant supprimer · adapter avant remplacer · compatibilité temporaire obligatoire
- PR (même solo) : documentée, tests manuels, anti-régression, incrémentale

## Template de prompt Copilot (format imposé)

Chaque tranche doit suivre :

```
## Analyse        — compréhension, fichiers impactés, décisions archi
## Risques        — régressions, zones fragiles, limitations
## Plan           — étapes ordonnées
## Implémentation — ce qui change, fichiers, logique, archi
## Validation     — tests, build, runtime, contraintes respectées
```

Contraintes systématiquement énoncées : ne pas casser `/training/classic`, garder `one level = one puzzle`, garder Solution Mode, ne pas réécrire un écran entier d'un coup.

## Liens

- Méthode IA-first et discipline du prompt → [[context-engineering]]
- Patterns de dispatch IA → [[subagent-workflows]]
- Architecture multi-process desktop (référence) → [[architecture-electron]]
