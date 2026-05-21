# /prime — Chargement du contexte de session

## Comportement automatique (hook SessionStart)

Le contexte est **chargé automatiquement à chaque démarrage de session** via le hook `SessionStart` configuré dans `.claude/settings.json`. Le hook exécute :

1. `python _scripts/brain.py load` → génère `wiki/context-session.md`
2. Lit `wiki/context-session.md`, `wiki/index.md`, et le dernier journal quotidien

**Tu n'as généralement pas besoin de lancer `/prime` manuellement.**

## Quand utiliser /prime

- Pour **forcer un rechargement** du contexte en milieu de session (ex: après `/save`)
- Pour **déboguer** si le hook n'a pas tourné correctement

## Commande manuelle

```bash
python _scripts/brain.py load
```

Le script détecte automatiquement la racine du vault. Si la variable d'environnement `VAULT_PATH` est définie, elle est utilisée comme chemin de sortie pour `wiki/context-session.md`.

Puis lire :
- `wiki/context-session.md` — mémoire persistante + session en cours
- `wiki/index.md` — index du vault
