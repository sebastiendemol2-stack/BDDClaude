# /save — Sauvegarde de session

## Stratégie : brain partagé OneDrive

Le brain est installé une seule fois dans `$OneDrive/Developpement/BDDClaude/_scripts/brain.py` et synchronisé via OneDrive entre tous les postes (Skewstony, maximoute, etc.).

**Cette commande ne s'applique qu'aux projets dans `$OneDrive/Developpement/`.** Pour les autres projets, demander à l'utilisateur.

## Les 3 modes

| Mode | Quand | Déclenché par |
|------|-------|---------------|
| `autosave` | Contexte > 90% | Hook Notification (automatique si configuré) |
| `close` | Fin de session | Hook Stop (automatique si configuré) |
| `full` | Sauvegarde manuelle complète | `/save` (l'utilisateur) |

## Commande à exécuter (mode full)

**Toujours utiliser ce pattern portable** (Git Bash sur Windows, marche aussi Linux/macOS si `$OneDrive` est défini) :

```bash
# Détection automatique de la racine OneDrive et du projet courant
ONEDRIVE_ROOT="${OneDrive:-${ONEDRIVE:-$HOME/OneDrive}}"
PROJECT_DIR="$(pwd)"

# Vérifier que le projet est bien dans OneDrive/Developpement/
case "$PROJECT_DIR" in
  "$ONEDRIVE_ROOT"/Developpement/*)
    BRAIN="$ONEDRIVE_ROOT/Developpement/BDDClaude/_scripts/brain.py"
    VAULT_PATH="$PROJECT_DIR" python "$BRAIN" save \
      --dir "$PROJECT_DIR" \
      --summary "Résumé de la session : ce qui a été fait" \
      --mode full
    ;;
  *)
    echo "[skip] Projet hors $ONEDRIVE_ROOT/Developpement — brain partagé non utilisé"
    ;;
esac
```

> `--summary` est requis en mode `full`. Sans lui, la session se ferme sans résumé Supabase.

## Modes autosave / close

Mêmes patterns, juste changer `--mode full --summary "..."` par :
- `--mode autosave` (pas de summary)
- `--mode close` (pas de summary)

## Ce que ça fait

1. **Sauvegarde la mémoire** de session en Supabase (table `claude_memory`)
2. **Crée/met à jour** l'entrée de journal quotidien dans `wiki/`
3. **Ferme la session** (supprime `.brain/session-id` local)
