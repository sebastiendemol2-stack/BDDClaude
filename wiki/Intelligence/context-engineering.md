---
title: "Context Engineering"
date: 2026-04-19
tags: [llm, context, ai-tools, knowledge-base]
type: recherche
status: active
confidence: high
source_type: extraction
freshness: volatile
sensitivity: internal
source: raw/notes/exemple-article.md
---

# Context Engineering

## Résumé

Le gain principal dans les outils IA (assistants de code, LLMs) ne vient pas de meilleurs prompts mais d'un **meilleur contexte**. Maintenir une base de connaissance persistante produit des résultats 3-5x plus fiables qu'une interaction sans mémoire.

## Concepts clés

- **Contexte > Prompt** : un LLM avec accès à l'historique du projet, ses décisions et conventions performe dramatiquement mieux qu'un LLM interrogé à froid
- **Capitalisation inter-sessions** : la base de contexte grossit à chaque session — chaque ajout réduit le coût des sessions suivantes
- **Coût asymétrique** : maintenir le contexte coûte bien moins cher que de tout ré-expliquer à chaque fois
- **Réduction des hallucinations** : l'IA cesse de deviner et commence à référencer — les équipes rapportent 3-5x moins de suggestions incorrectes

## Passage clé

> *"The shift is from prompt engineering to context engineering — designing the information environment around the AI, not crafting the perfect question."*

## Principes cles

1. **Contexte > Prompt** : Un prompt parfait sur un contexte vide echoue. Un prompt moyen sur un contexte riche reussit. L'investissement est dans la base de connaissance, pas dans la formulation.
2. **Capitalisation inter-sessions** : Chaque interaction est un investissement. Le contexte s'accumule, chaque session successive est moins chere que la precedente car l'IA "connait deja" le projet.
3. **Cout asymetrique** : Expliquer coute cher (tokens). Stocker coute peu. Le vault transforme des couts d'exploitation recurrents en investissement unique.
4. **Reduction des hallucinations** : Quand l'IA peut referencer des decisions passees, des conventions de projet, et des contraintes reelles, elle cesse de deviner. Les equipes utilisant un vault rapportent 3-5x moins de suggestions incorrectes.

## Exemples de bon vs mauvais contexte

**Mauvais contexte** : "Revois ce fichier et dis-moi s'il y a des bugs." → L'IA ne connait ni l'architecture, ni les conventions, ni les decisions passees. Elle va deviner les patterns et probablement suggerer des "bugs" qui sont en fait des choix deliberes.

**Bon contexte** : "Ce fichier fait partie du module de routing dans une app Electron feature-first. Voir [[Context/cowork-ia]] pour l'architecture, [[Resources/architecture-electron]] pour les patterns IPC. Les decisions passees sont dans [[wiki/Daily/2026-05-07]]. On utilise React 19 + Vite 6, contextIsolation: true. Verifie la conformite avec ces patterns." → L'IA a tout ce qu'il faut pour une revue utile.

## La philosophie "Contexte > Prompt"

Le shift n'est pas technique mais epistemologique : on passe d'une logique d'**interrogation** (poser la bonne question) a une logique d'**environnement** (concevoir le bon ecosysteme informationnel). Le prompt devient un declencheur, pas le vecteur principal de qualite.

> "Design the information environment around the AI, not craft the perfect question."

Dans ce vault, chaque note est un atome de contexte. Les `[[wiki links]]` sont les connexions qui transforment des atomes isoles en graphe. Le frontmatter (tags, confidence, freshness, sensitivity) est la couche de metadonnees qui permet un filtrage contextuel automatique.

## Implications pour ce vault

Ce vault est lui-meme une application directe du context engineering :
- `raw/` accumule les inputs bruts
- `wiki/` compile la connaissance persistante
- Chaque session `/save` enrichit le contexte disponible pour les suivantes
- Les commandes `/prime` et `/query` sont les outils de retrieval qui rendent ce contexte accessible au moment opportun

- [[index]] — Master Index
