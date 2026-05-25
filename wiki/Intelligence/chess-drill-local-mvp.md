---
title: "Chess Drill — Local MVP et Authoring"
date: 2026-05-24
tags: [chess-drill, local-mvp, training, authoring, pwa]
type: recherche
status: active
confidence: high
source_type: raw
freshness: volatile
sensitivity: internal
derived_from:
  - path: raw/docs/24-local-puzzle-data-format.md
    relation: source
  - path: raw/docs/26-localhost-mvp-readiness.md
    relation: source
---

# Chess Drill - Local MVP et Authoring

## Objectif

Le MVP local permet de tester Chess Drill de bout en bout sans backend. Le flux prioritaire est :

`/` -> Continuer en mode local -> `/worlds` -> Monde 1 Niveau 5 -> Training -> End Of Level -> Map/Bibliotheque/Solution Mode.

Ce mode sert a valider la boucle produit avant de brancher les donnees backend.

## Niveau local reel

Le niveau jouable de reference est `world-1-l5`.

Il contient un seul puzzle local annote, avec une ou plusieurs lignes de solution. Le fichier auteur est :

`frontend/src/modules/training/levels/world-1-l5.level.js`

## Regle MVP

L'ancienne regle "1 niveau = 5 puzzles" est remplacee pour le MVP local par :

**1 niveau = 1 puzzle annote avec une ou plusieurs lignes de solution.**

Le runtime garde une compatibilite legacy avec `puzzles: [...]`, mais les nouveaux contenus doivent utiliser un objet `puzzle` unique.

## Schema auteur

Chaque niveau exporte un objet :

```js
{
  id: 'world-1-l5',
  worldId: 'world-1',
  levelNumber: 5,
  title: 'Level title',
  puzzle: {}
}
```

Le puzzle doit inclure :

- `id`, `title`, `fen`, `sideToMove`
- `theme`, `difficulty`
- `shortGoal`, `explanation`, `keyIdea`
- `commonMistakes`
- `solutionLines`

Chaque ligne de solution contient `id`, `label`, `moves`, `explanation`, `moveAnnotations`.

## Validation locale

Le validateur local impose :

- exactement 1 puzzle par niveau
- FEN valide
- coherence entre `sideToMove` et la FEN
- au moins une ligne de solution
- coups SAN legaux depuis la position initiale
- annotations rattachees a des coups presents dans la ligne
- champs pedagogiques presents

## Surfaces mock/locales

Surfaces utilisables sans backend :

- World Map
- Training mock
- End Of Level Flow
- Library
- Solution Mode
- Challenges
- Shop
- Profile
- progression `localStorage`

Surfaces qui restent liees au backend :

- `/training/classic`
- exploration backend
- surfaces admin hybrides ou API

## Test manuel MVP

1. Ouvrir `/`.
2. Cliquer `Continuer en mode local`.
3. Verifier l'arrivee sur `/worlds`.
4. Lancer `Monde 1 - Niveau 5`.
5. Terminer ou echouer le niveau.
6. Verifier l'End Of Level Flow.
7. Revenir a la map et rafraichir la page.
8. Obtenir 3 etoiles pour debloquer le puzzle en bibliotheque.
9. Rejouer le puzzle depuis Bibliotheque.
10. Ouvrir Solution Mode.
11. Tester Defis, Shop, Profil.
12. Reset la progression locale et verifier le retour a l'etat initial.

## Voir aussi

- [[Context/chess-drill]]
- [[Intelligence/chess-drill-gamification]]
- [[Intelligence/chess-drill-architecture]]
- [[Resources/chess-drill-design-system]]
