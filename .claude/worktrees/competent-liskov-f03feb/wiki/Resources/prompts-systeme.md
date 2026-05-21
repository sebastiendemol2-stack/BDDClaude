---
date: 2026-05-07
tags: [prompts, templates, subagents]
type: ressource
status: active
---

# Prompts Systeme

## Orchestrateur Cowork IA

Route les requetes vers le modele le plus adapte selon complexite et domaine. Reponds en francais. Concis et oriente action.

## Sous-agent Synthesis (haiku)

Analyse notes, identifie patterns cross-thematiques, resume structure markdown.

## Sous-agent Research (haiku)

Documentation thematique structuree a partir des sources fournies.

## Template Analyse de code

- Contexte : decrire le fichier/module
- Probleme : decrire le bug ou l'objectif
- Contraintes : stack, perf, compatibilite

## Template Decision Log

- Date : YYYY-MM-DD
- Contexte
- Options considerees
- Decision retenue + Raison
- Impact

## Triggers de thinking (Claude Code)

Mots-clefs a inclure dans le prompt pour escalader le budget de raisonnement de Claude Code. A utiliser quand la tache merite l'investissement en tokens.

| Trigger | Budget | Quand |
| ------- | ------ | ----- |
| (aucun) | 0 | Questions factuelles, edits triviaux, lookups |
| `think` | leger | Choix de design simple, comparer 2-3 options |
| `think hard` / `think harder` | moyen | Debug non-trivial, refactor avec dependances, decisions d'archi |
| `ultrathink` | max | Bug complexe, design multi-systeme, audit critique |

**Exemples** :

- `think hard sur la meilleure facon de structurer ce reducer`
- `ultrathink — pourquoi cette query Supabase prend 8s en prod alors que le plan est OK ?`

**`/fast`** : bascule Claude Code sur Opus 4.6 (output plus rapide, raisonnement plus puissant). Utile quand Sonnet 4.6 sature ou pour des taches creatives/architecturales lourdes. Cout plus eleve.

## Liens

- [[subagent-workflows]]
- [[cowork-ia]]
