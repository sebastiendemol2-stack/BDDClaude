# Second Brain — Vault Obsidian + Claude Code

## Regles absolues

1. Ne JAMAIS modifier, renommer ou deplacer un fichier dans `raw/` — c'est l'espace humain, immutable
2. Ne JAMAIS creer de note orpheline — chaque note a au moins un wiki link entrant ou sortant
3. Ne JAMAIS ecrire dans le vault sans passer par un skill (/ingest, /save, /query)
4. Ne JAMAIS supprimer une note wiki — archiver en changeant `status: archive`
5. Ne JAMAIS inventer d'information absente du vault — signaler quand la donnee manque

## Architecture 3 couches (Karpathy LLM Wiki)

| Couche           | Dossier     | Proprietaire | Regle                                             |
| ---------------- | ----------- | ------------ | ------------------------------------------------- |
| Layer 1 — Raw    | `raw/`      | Humain       | Immutable. Inputs bruts (clippings, docs, notes). |
| Layer 2 — Wiki   | `wiki/`     | LLM          | Compile via `/ingest`. Concepts, resumes, index.  |
| Layer 3 — Schema | `CLAUDE.md` | Humain       | Structure et conventions. Definit raw → wiki.     |

## Fonctionnement

L'humain browse le vault dans Obsidian. Le LLM ecrit et maintient le wiki. Le wiki compile et grandit.

- **raw/** contient le bordel humain : articles clippes, PDFs, notes manuscrites. Le LLM lit mais ne touche JAMAIS.
- **wiki/** contient la connaissance compilee : notes structurees, index, log. Le LLM est responsable de la qualite.
- **wiki/index.md** est le panneau de direction. Le LLM le lit EN PREMIER pour naviguer le wiki sans scanner chaque dossier. Economise les tokens.
- **wiki/log.md** est le journal chronologique append-only. Chaque operation (ingest, query, lint, save) y ajoute une entree.

## Operations disponibles

| Commande  | Role                                       | Quand l'utiliser                            |
| --------- | ------------------------------------------ | ------------------------------------------- |
| `/prime`  | Charger le contexte au debut d'une session | A chaque nouvelle session Claude Code       |
| `/ingest` | Compiler raw/ → wiki/                      | Apres avoir ajoute du contenu dans raw/     |
| `/save`   | Sauvegarder l'etat de la session           | En fin de session de travail                |
| `/query`  | Recherche profonde dans le wiki            | Pour trouver de l'information dans le vault |
| `/lint`   | Health-check du vault                      | Periodiquement (1x/semaine recommande)      |

## Conventions Obsidian

- **Wiki links** : `[[Nom de la note]]` pour tout lien interne
- **Embeds** : `![[Note]]` pour inclure du contenu
- **Frontmatter YAML obligatoire** sur chaque note wiki :

```yaml
---
date: YYYY-MM-DD
tags: []
type: note | contexte | recherche | ressource | daily
status: active | archive
---
```

## Structure wiki/

| Dossier              | Contenu                                        |
| -------------------- | ---------------------------------------------- |
| `wiki/Context/`      | Notes de contexte : profil, objectifs, projets |
| `wiki/Intelligence/` | Decisions, recherches, analyses, benchmarks    |
| `wiki/Resources/`    | Templates, patterns, snippets reutilisables    |
| `wiki/Daily/`        | Journal quotidien auto-genere par /save        |

Ces dossiers se creent au besoin. Ne JAMAIS creer un dossier vide.

## Supabase — Backend cloud

Projet ID : `ottoqbwctcpzzdfzewdi` — region eu-central-1

| Table            | Role                                                    |
| ---------------- | ------------------------------------------------------- |
| `vault_sections` | Categories du vault (projets, doc-technique, prompts…)  |
| `vault_entries`  | Notes wiki synchronisees depuis Obsidian                |
| `vault_profile`  | Profil utilisateur (nom, machine, preferences Claude)   |
| `vault_journal`  | Journal chronologique (entrees quotidiennes par projet) |

Colonnes cles de `vault_entries` : section_slug, title, content, tags[], source, obsidian_path, type, status.

### Sync Obsidian <-> Supabase

Script : `_scripts/sync.py` (Python, deps dans `_scripts/lib/`)

| Commande                  | Action                          |
| ------------------------- | ------------------------------- |
| `python sync.py push`     | Local → Supabase                |
| `python sync.py pull`     | Supabase → Local                |
| `python sync.py status`   | Compare les deux                |

Obsidian est la source de verite. Supabase est la couche requetable pour Claude.
