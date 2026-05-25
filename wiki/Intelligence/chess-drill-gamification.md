---
title: "Chess Drill — Gamification"
date: 2026-05-24
tags: [chess-drill, gamification, worldmap, progression, ux]
type: recherche
status: active
confidence: high
source_type: raw
freshness: volatile
sensitivity: internal
derived_from:
  - path: raw/docs/12-gamification.md
    relation: source
  - path: raw/docs/11-modes-de-jeu.md
    relation: source
  - path: raw/docs/13-progression-utilisateur.md
    relation: source
  - path: raw/docs/14-flux-utilisateur.md
    relation: source
---

# Chess Drill — Gamification

## Vision

Transformer une pratique tactique utile en **habitude quotidienne motivante**.

Boucle core : jouer → réussir → gagner → débloquer → revenir.

## Mécaniques classées par priorité

### MVP indispensable

- XP simple par puzzle terminé
- Objectif quotidien minimal (ex: 5 puzzles)
- Barre de progression niveau joueur
- Feedback clair succès/erreur

### V1 important

- Streak journalier (série jours consécutifs)
- Vies/coeurs (pénalité douce, régénération temporelle)
- Niveaux + seuils XP
- Missions quotidiennes
- Premiers badges de réussite

### Plus tard

- Carte de progression (worlds/levels)
- Ligues hebdomadaires
- Coffres et récompenses aléatoires contrôlées
- Objectifs hebdomadaires complexes

### Optionnel

- Boutique cosmétique
- Monnaie virtuelle avancée
- Effets sonores contextuels premium
- Animation cinématique de déblocage

## Recommandations game design

- Récompenses courtes et fréquentes en début de parcours
- Progression visible à chaque session
- Pénalité douce (vies) sans frustration bloquante
- Streak : incentive principal de rétention long terme

## Règles locales simulées (training mock)

**Calcul étoiles par session** :
- 0 erreur → 3 étoiles (perfect)
- 1 erreur → 2 étoiles
- 2 erreurs → 1 étoile
- 3+ erreurs → 0 (échec)

**Hints** : 3 types (Coup Direct, Coup Sûr, Force le Coup) — consommés sur inventaire local, désactivés en mode bibliothèque

**Mode Zen** : purement visuel, pas d'impact score/règles

## World Map Mock — Règles complètes (2026-05-20)

### Structure

- 3 mondes : Easy/prairie, Medium/desert, Hard/nuit
- Monde 1 débloqué par défaut
- Monde suivant débloqué quand dernier niveau du précédent est `completed` ou `perfect`

### États de niveau

| État | Lancable | Unlock suivant |
|------|----------|----------------|
| `available` | oui | — |
| `locked` | non | — |
| `completed` | oui (rejouable) | non |
| `perfect` | oui (rejouable) | — |

**Règles unlock** :
- `levelCompleted` 3 étoiles → `perfect` + unlock niveau suivant
- `levelCompleted` 1 ou 2 étoiles → `completed`, pas d'unlock
- `levelFailed` → aucun unlock

### Persistance locale

Clé localStorage : `cd-world-map-mock-v1` — migration backward-compatible depuis format mono-world.

### State shape multi-monde

```
currentWorldId
worlds[]   { difficulty, biome, unlocked }
levels[]   { status, stars }
lastPlayedLevelId
resources  { coins, xp, livesCurrent, livesMax, hintsInventory, unlimitedLivesUntil }
```

## Bibliothèque personnelle (mock)

- Collection dérivée du state world map (single source of truth)
- Seuls les niveaux `perfect` (3 étoiles) ajoutent des puzzles (5 par niveau)
- Replay bibliothèque : sans hints, sans mutation progression map
- Sélecteur : `frontend/src/modules/library/libraryMockSelectors.js`

## Défis quotidiens (mock)

Défis inclus :
- Résoudre 1 niveau
- Obtenir 3 étoiles sur un niveau
- Débloquer 5 puzzles
- Rejouer 1 puzzle en bibliothèque
- Utiliser 0 hint sur un niveau

Statuts : `locked` / `inProgress` / `completed` / `claimed`

Sources progression : state world map + collection bibliothèque + activité session.

## Shop et ressources globales (mock)

**Ressources single source of truth** :
- `coins`, `xp`
- `livesCurrent` / `livesMax`
- `hintsInventory` (direct, safe, force)
- `unlimitedLivesUntil` (boost temporaire)

**Règles achat** :
- Décrémente coins
- Refusé si coins insuffisants
- Vies capées à `livesMax` sauf boost

**Produits** : +1 vie, refill vies, Coup Direct/Sûr/Force ×1, Vie illimitée 15min

## Profil + badges (mock)

Niveau joueur calculé depuis XP total. Badges :
- Premier niveau réussi
- Perfect 3 étoiles
- Collectionneur 5 puzzles
- Premier replay bibliothèque
- Économe de hints

## Voir aussi

- [[Context/chess-drill]] — contexte et vision produit
- [[Intelligence/chess-drill-architecture]] — couche mock et architecture modules
- [[Intelligence/chess-drill-roadmap]] — phases 7-12 (gamification complète)
- [[Resources/chess-drill-design-system]] — composants UI gamification
