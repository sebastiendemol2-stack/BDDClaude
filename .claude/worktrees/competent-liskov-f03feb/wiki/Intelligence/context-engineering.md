---
date: 2026-04-19
tags: [llm, context, ai-tools, knowledge-base]
type: recherche
status: active
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

## Implications pour ce vault

Ce vault est lui-même une application directe du context engineering :
- `raw/` accumule les inputs bruts
- `wiki/` compile la connaissance persistante
- Chaque session `/save` enrichit le contexte disponible pour les suivantes

## Liens

- [[wiki/index.md]] — Master Index
