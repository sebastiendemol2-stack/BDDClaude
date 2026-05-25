---
title: "Chess Drill — Base de Données"
date: 2026-05-24
tags: [chess-drill, database, sql, schema, mysql]
type: recherche
status: active
confidence: medium
source_type: raw
freshness: volatile
sensitivity: internal
derived_from:
  - path: raw/docs/07-base-de-donnees.md
    relation: source
---

# Chess Drill — Base de Données

## Schéma actuel

Tables existantes :

| Table | Rôle |
|-------|------|
| `users` | Comptes utilisateurs |
| `puzzle_libraries` | Bibliothèques de puzzles |
| `puzzles` | Exercices individuels |
| `solutions` | Lignes de solution par puzzle |
| `runs` | Sessions d'entraînement |
| `run_progress` | Progression par puzzle dans un run |

**Points forts** : base relationnelle saine, FK et index utiles.\
**Limites** : pas de modèle gamification, divergence possible code/schéma sur certaines colonnes.

## Schéma cible proposé

### Core (maintenant)

**`exercises`** (renommage de puzzles) : `id`, `library_id`, `fen`, `title`, `description`, `difficulty`, `theme_primary_id`, `is_active`, timestamps\
**`exercise_moves`** (renommage de solutions) : `id`, `exercise_id`, `line_index`, `move_index`, `san`, `actor` (user/opponent), `annotation`\
**`tactical_themes`** : `id`, `key`, `label`, `difficulty_weight` — N-N avec exercises\
**`user_progress`** : `id`, `user_id`, `exercise_id`, `status` (new/learned/mastered), `best_time_sec`, `success_rate`, `last_attempt_at`

### MVP gamification

**`user_xp`** : ledger des gains/pertes XP — `user_id`, `source_type`, `source_id`, `xp_delta`, `created_at`

### V1

**`user_streaks`** : `user_id` (PK), `current_streak`, `best_streak`, `last_active_date`, `freeze_tokens`\
**`user_lives`** : `user_id` (PK), `lives_current`, `lives_max`, `regen_started_at`

### Plus tard

**`worlds`** : `id`, `name`, `order_index`, `theme`\
**`levels`** : `id`, `world_id`, `index_in_world`, `xp_required`, `unlock_rule`\
**`level_exercises`** (pivot) : N-N levels × exercises\
**`rewards`** : `id`, `type` (chest/badge/currency), `payload_json`, `rarity`\
**`achievements`** : `id`, `key`, `name`, `description`, `condition_json`\
**`daily_challenges`** : `id`, `date`, `challenge_type`, `target_value`, `reward_xp`

## Relations globales

```
users 1-N runs
runs 1-N run_progress
users 1-N user_xp
users 1-1 user_streaks
users 1-1 user_lives
worlds 1-N levels
levels N-N exercises (via level_exercises)
exercises N-N tactical_themes
exercises 1-N exercise_moves
```

## Priorisation

| Priorité | Tables |
|----------|--------|
| **Maintenant** | Fiabiliser schéma actuel + exercises/exercise_moves + user_progress |
| **Ensuite** | user_xp, user_streaks, user_lives |
| **Plus tard** | worlds, levels, rewards, achievements, daily_challenges |

## Note migration

La phase 1 ajoute `sortOrder` à la table `solutions` par migration **additive avec valeur par défaut** — pas de destruction de données existantes.

## Voir aussi

- [[Context/chess-drill]] — contexte projet
- [[Intelligence/chess-drill-roadmap]] — phase 5 (nettoyage DB) et phase 1 (bug sortOrder)
- [[Intelligence/chess-drill-architecture]] — backend cible par domaine
