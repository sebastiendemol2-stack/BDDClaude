# /save — Sauvegarde de session

## Les 3 modes

| Mode | Quand | Déclenché par |
|------|-------|---------------|
| `autosave` | Contexte > 90% | Hook Notification (automatique) |
| `close` | Fin de session | Hook Stop (automatique) |
| `full` | Sauvegarde manuelle complète | `/save` (toi) |

**Les modes `autosave` et `close` sont automatiques** — configurés dans `.claude/settings.json`.

## Utilisation manuelle (mode full)

Lance `/save` en fin de session pour journaliser + sauvegarder en Supabase :

```bash
python _scripts/brain.py save \
  --summary "Résumé de la session : ce qui a été fait" \
  --mode full
```

> `--summary` est requis en mode `full`. Sans lui, la session se ferme sans résumé Supabase.
> Le script détecte automatiquement la racine du vault — `--dir` est optionnel.

## Ce que ça fait

1. Sauvegarde la mémoire de session en Supabase (`claude_memory`)
2. Crée/met à jour l'entrée de journal quotidien
3. Ferme la session (supprime `.brain/session-id`)
