# /sync — Synchronisation vault ↔ Supabase

Synchronise les notes `wiki/` vers la table `vault_entries` de Supabase (requêtable par d'autres outils).

> **Deux projets Supabase distincts :**
> - `brain.py` utilise `BRAIN_URL` (mémoire Claude, sessions)
> - `sync.py` utilise `SUPABASE_URL` (contenu vault, `vault_entries`)

## Commandes

```bash
# Voir l'état de la sync (local vs remote)
python _scripts/sync.py status

# Pousser les notes locales vers Supabase
python _scripts/sync.py push

# Récupérer les entrées remote absentes localement
# ATTENTION : ne remplace pas les fichiers locaux existants (conflit = skip)
python _scripts/sync.py pull
```

## Quand utiliser

- Après `/ingest` pour rendre les nouvelles notes requêtables
- En début de session sur une nouvelle machine (`pull`)
- Avant de partager le vault (`push`)

## Schéma Supabase

Voir `schema/supabase.sql` pour le DDL complet de la table `vault_entries` et ses contraintes.
