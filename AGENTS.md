# Second Brain — Vault Obsidian + Codex

> **Schema v3.2.0** — voir [wiki/_meta/manifest.yaml](wiki/_meta/manifest.yaml) pour la source de vérité machine-readable (allowed values, policies, pipelines).

## Regles absolues

1. Ne JAMAIS modifier, renommer ou deplacer un fichier dans `raw/` — c'est l'espace humain, immutable
2. Ne JAMAIS creer de note orpheline — chaque note a au moins un wiki link entrant ou sortant (sauf `type: index`)
3. Ne JAMAIS ecrire dans le vault sans passer par un skill (/ingest, /save, /query)
4. Ne JAMAIS supprimer une note wiki — archiver en changeant `status: archive`
5. Ne JAMAIS inventer d'information absente du vault — signaler quand la donnee manque
6. Ne JAMAIS lire `raw/private/` ou `raw/sensitive/` depuis un LLM ou un script (voir privacy_policy)
7. Ne JAMAIS éditer manuellement `summary` ou `wiki/_meta/alias_registry.yaml` — auto-générés
8. Ne JAMAIS modifier `_scripts/utils.py:normalize_for_hash` sans bumper `vault_version.major`

## Philosophie

| Layer | Dossier | Rôle |
| --- | --- | --- |
| Épisodique | `raw/` | Workspace humain — brainstorming, drafts, scratchpads, sensible possible |
| Sémantique | `wiki/` | Knowledge stabilisée uniquement (public/internal) |
| Mémoire de travail | `wiki/_staging/` | Buffer de validation (max 7 jours) |
| Infrastructure | `wiki/_system/` | Cache, locks, jobs, snapshots, transactions, hashes |
| Méta | `wiki/_meta/` | manifest.yaml, entities.yaml, alias_registry.yaml, health.md |
| Compressed | `wiki/_compressed/` | Méta-notes consolidées (Phase 4, > 200 notes) |

**Règle d'or** : `wiki/` est pour la connaissance stabilisée. Pas de brainstorming, pas de pensées temporaires. Ces dernières vont dans `raw/` ou `wiki/_staging/`.

## Frontmatter obligatoire (v3.2.0)

```yaml
---
date: YYYY-MM-DD
tags: []
type: concept | projet | contexte | recherche | decision | ressource | personne | daily | index
status: active | archive | staging
confidence: high | medium | low
source_type: raw | extraction | synthesis | human
freshness: evergreen | volatile | deprecated
sensitivity: public | internal | private | sensitive
---
```

Champs optionnels usuels : `canonical`, `aliases`, `links_to`, `derived_from`, `summary` (auto), `ingested_at`, `source_hash`, `token_count`, `memory_tier`, etc. Voir manifest.yaml § `optional_frontmatter`.

### Defaults par type

| type | freshness | memory_tier | sensitivity |
| --- | --- | --- | --- |
| concept | evergreen | stable | internal |
| contexte | volatile | stable | internal |
| projet | volatile | working | internal |
| recherche | volatile | stable | internal |
| decision | volatile | stable | internal |
| ressource | evergreen | stable | public |
| personne | volatile | stable | private |
| daily | volatile | archived | private |
| index | evergreen | stable | public |

## Operations disponibles

| Commande  | Role                                       | Quand l'utiliser                            |
| --------- | ------------------------------------------ | ------------------------------------------- |
| `/prime`  | Charger le contexte au debut d'une session | A chaque nouvelle session Codex       |
| `/ingest` | Compiler raw/ → staging/ → wiki/ via tx    | Apres avoir ajoute du contenu dans raw/     |
| `/save`   | Sauvegarder l'etat de la session           | En fin de session de travail                |
| `/query`  | Recherche hybride (BM25 + vector + graph)  | Pour trouver de l'information dans le vault |
| `/lint`   | 15 checks v2 (santé du vault)              | Periodiquement (1x/semaine recommande)      |

## Conventions Obsidian

- **Wiki links** : `[[Nom de la note]]` pour tout lien interne (résolus via `alias_registry.yaml`)
- **Embeds** : `![[Note]]` pour inclure du contenu
- **Naming** : kebab-case strict (`a-z0-9-`, max 64 chars), daily = `YYYY-MM-DD`
- **`derived_from` structuré** : `[{path: raw/x.md, relation: source}]` (relations : source / enriched_by / extends / relates_to)

## Structure wiki/

| Dossier              | Contenu                                          |
| -------------------- | ------------------------------------------------ |
| `wiki/index.md`      | Master index hiérarchique (lu en premier)        |
| `wiki/log.md`        | Journal chronologique append-only                |
| `wiki/Context/`      | Projets et contextes actifs                      |
| `wiki/Intelligence/` | Concepts, recherches, decisions                  |
| `wiki/Resources/`    | Ressources réutilisables, templates              |
| `wiki/Daily/`        | Journal quotidien (YYYY-MM-DD.md)                |
| `wiki/_meta/`        | manifest, entities, alias_registry, health       |
| `wiki/_system/`      | Infrastructure (cache, locks, tx, jobs, …)       |
| `wiki/_staging/`     | Mémoire de travail (max 7j)                      |
| `wiki/_compressed/`  | Phase 4 — méta-notes consolidées                 |

## Supabase — Backend cloud

Projet ID : `ottoqbwctcpzzdfzewdi` — region eu-central-1

Tables principales (v3.2.0) :

| Table                | Role                                                          |
| -------------------- | ------------------------------------------------------------- |
| `vault_sections`     | Categories du vault                                           |
| `vault_entries`      | Notes wiki synchronisees (35+ colonnes, sans embedding)       |
| `vault_embeddings`   | **Séparée** — multi-provider (provider, model, dim, embedding) |
| `vault_chunks`       | Chunks pour notes longues (>512 tokens)                       |
| `vault_transactions` | Audit des staging→wiki promotions                             |
| `vault_snapshots`    | Temporal graph snapshots (Phase 4)                            |
| `vault_profile`      | Profil utilisateur                                            |
| `vault_journal`      | Journal chronologique par projet                              |
| `vault_links_from`   | Vue dérivée (links_to inversés)                               |

Voir `schema/supabase.sql` pour le DDL complet.

### Sync Obsidian ↔ Supabase

| Commande                                     | Action                                  |
| -------------------------------------------- | --------------------------------------- |
| `python _scripts/sync.py push`               | Local → Supabase (skip private/sensitive) |
| `python _scripts/sync.py pull`               | Supabase → Local                        |
| `python _scripts/sync.py status`             | Compare                                 |
| `python _scripts/sync.py --rebuild-alias-registry` | Rebuild wiki/_meta/alias_registry.yaml |
| `python _scripts/sync.py --rename-suggest`   | Liste fichiers non kebab-case          |

Sync incrémental : skip si `content_hash` unchanged. Refuse push si `sensitivity ∈ {private, sensitive}`.

## Universal Knowledge Protocol (UKP)

Le backend UKP est accessible via MCP depuis tous les IDE :
- **Endpoint**: `https://ottoqbwctcpzzdfzewdi.supabase.co/functions/v1/ukp-mcp`
- **Tools**: `query` (recherche hybride), `prime` (contexte vault), `session` (gestion session)
- **SDK**: `supabase/ukp-client.ts` (zero-dependency TypeScript)
- **Streaming SSE**: `ukp-stream` (events temps réel)

### Quickstart
```typescript
const client = new UKPClient({ url, key, clientIde: 'Codex' })
await client.prime()
const results = await client.query('vault architecture')
```

## Tests

`_scripts/tests/test_hash.py` est **obligatoire** (golden vectors). Toute modification de `normalize_for_hash` invalide tous les hashes existants → bump `vault_version.major`.

```bash
python -m pytest _scripts/tests/ -v
```

## Voir aussi

- [wiki/_meta/manifest.yaml](wiki/_meta/manifest.yaml) — source de vérité machine-readable
- [wiki/_meta/entities.yaml](wiki/_meta/entities.yaml) — canonicalisation entités
- [wiki/_meta/health.md](wiki/_meta/health.md) — rapport santé hebdomadaire (Phase 3)
