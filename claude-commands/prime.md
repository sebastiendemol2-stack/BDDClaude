# /prime — Chargement du contexte de session

## Stratégie : brain partagé OneDrive

Le brain partagé est dans `$OneDrive/Developpement/BDDClaude/_scripts/brain.py` (sync OneDrive entre tous les postes).

**Cette commande ne s'applique qu'aux projets dans `$OneDrive/Developpement/`.**

## Comportement automatique (hook SessionStart)

Si configuré dans le `.claude/settings.json` du projet, le hook `SessionStart` exécute le load automatiquement. La commande à utiliser dans le hook est la même que ci-dessous (mode `load`).

## Commande à exécuter (manuelle)

```bash
# Détection automatique
ONEDRIVE_ROOT="${OneDrive:-${ONEDRIVE:-$HOME/OneDrive}}"
PROJECT_DIR="$(pwd)"

case "$PROJECT_DIR" in
  "$ONEDRIVE_ROOT"/Developpement/*)
    BRAIN="$ONEDRIVE_ROOT/Developpement/BDDClaude/_scripts/brain.py"
    VAULT_PATH="$PROJECT_DIR" python "$BRAIN" load --dir "$PROJECT_DIR"
    ;;
  *)
    echo "[skip] Projet hors $ONEDRIVE_ROOT/Developpement — brain partagé non utilisé"
    ;;
esac
```

Puis lire dans le projet :
- `wiki/Context/context-session.md` — mémoire persistante générée par le brain
- `wiki/index.md` — index du vault
- Dernier journal quotidien dans `wiki/` (log.md ou Daily/)

## Quand utiliser /prime manuellement

- **Forcer un rechargement** du contexte en milieu de session (ex: après `/save`)
- **Déboguer** si le hook `SessionStart` n'a pas tourné correctement
