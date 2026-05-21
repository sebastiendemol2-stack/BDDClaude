# BDDClaude — Brain Claude Code partagé

Mémoire persistante Claude Code ↔ Supabase, installée sur OneDrive pour être accessible depuis **toutes les sessions Claude sur tous les postes**.

## Structure
```
BDDClaude/
├── README.md                       ← Ce fichier
├── SETUP-VSCODE-MAXIMOUTE.md       ← Guide d'installation pour un nouveau poste (VS Code)
├── _scripts/                       ← Le brain (Python)
│   ├── brain.py
│   ├── .env                        ← Credentials Supabase (synced)
│   ├── lib/                        ← Dépendances vendorisées
│   └── ...
└── claude-commands/                ← Slash commands (/save, /prime)
    ├── save.md
    └── prime.md
```

Synchronisé automatiquement via OneDrive entre les postes (Skewstony, maximoute, futurs collabs).

## Pour installer sur un nouveau poste

➡️ Voir [SETUP-VSCODE-MAXIMOUTE.md](SETUP-VSCODE-MAXIMOUTE.md)

## Pré-requis (par poste)
- **Python 3.10+** installé (`python --version`)
- Toutes les dépendances sont vendorisées dans `_scripts/lib/` — pas de `pip install` requis

## Utilisation depuis n'importe quel projet

⚠️ **Important** : `brain.py` est conçu pour 1 brain = 1 vault. La variable `VAULT_PATH` doit **toujours** être définie et doit correspondre au projet courant. Sans elle, le brain refuse de lire/écrire (sécurité anti path-traversal).

### Charger le contexte (équivalent /prime)
```bash
# Linux/macOS/Git Bash
VAULT_PATH="<chemin_du_projet>" python "D:/OneDrive/Developpement/BDDClaude/_scripts/brain.py" load --dir "<chemin_du_projet>"

# PowerShell
$env:VAULT_PATH="<chemin_du_projet>"; python "D:/OneDrive/Developpement/BDDClaude/_scripts/brain.py" load --dir "<chemin_du_projet>"
```

### Sauvegarder une session (équivalent /save)
```bash
# Mode full — fin de session avec résumé
VAULT_PATH="<chemin_du_projet>" python "D:/OneDrive/Developpement/BDDClaude/_scripts/brain.py" save \
  --dir "<chemin_du_projet>" \
  --summary "Résumé de la session" \
  --mode full

# Mode autosave — sauvegarde rapide en cours de session
VAULT_PATH="<chemin_du_projet>" python "D:/OneDrive/Developpement/BDDClaude/_scripts/brain.py" save \
  --dir "<chemin_du_projet>" \
  --mode autosave

# Mode close — fermer sans écrire
VAULT_PATH="<chemin_du_projet>" python "D:/OneDrive/Developpement/BDDClaude/_scripts/brain.py" save \
  --dir "<chemin_du_projet>" \
  --mode close
```

### Exemple validé (ChessDrill, 2026-05-20)
```bash
VAULT_PATH="D:/OneDrive/Developpement/ChessDrill" python "D:/OneDrive/Developpement/BDDClaude/_scripts/brain.py" save \
  --dir "D:/OneDrive/Developpement/ChessDrill" \
  --summary "..." \
  --mode full
# → [OK] Session closed (mode: full) | f8b1d914...
```

## Configuration

Le fichier `_scripts/.env` contient les credentials Supabase (BRAIN_URL + BRAIN_SERVICE_KEY). Il est lu automatiquement par `brain.py` via `load_dotenv()`.

⚠️ **Sécurité** : ces credentials sont synchronisés via OneDrive (donc dans le cloud Microsoft). C'est acceptable pour un usage perso mais à connaître.

## Pour activer ce brain dans un projet Claude

### Option A — Variables d'environnement par projet (recommandé)
Dans le `.claude/settings.json` de **chaque projet** :
```json
{
  "env": {
    "CLAUDE_BRAIN_PATH": "D:/OneDrive/Developpement/BDDClaude/_scripts/brain.py",
    "VAULT_PATH": "D:/OneDrive/Developpement/<NomDuProjet>"
  }
}
```

Puis dans les skills (`/save`, `/prime`), utiliser `$CLAUDE_BRAIN_PATH` au lieu de `_scripts/brain.py`.

### Option B — Path absolu dans les skills globaux
Modifier les skills `/save` et `/prime` dans `C:/Users/sebas/.claude/skills/` pour utiliser :
```bash
VAULT_PATH="$(pwd)" python "D:/OneDrive/Developpement/BDDClaude/_scripts/brain.py" save ...
```

### Option C — Lien symbolique par projet (legacy)
Créer un lien symbolique `_scripts/` dans chaque projet :
```powershell
# PowerShell admin
New-Item -ItemType Junction -Path "C:/path/to/project/_scripts" -Target "D:/OneDrive/Developpement/BDDClaude/_scripts"
```
Permet de garder l'ancien pattern `python _scripts/brain.py` qui fonctionne nativement.

## Évolution future

Le brain actuel impose **1 brain par vault**. Pour vraiment supporter plusieurs vaults depuis un seul brain global, il faudrait modifier `brain.py` pour :
- Accepter une liste de VAULT_PATHs valides
- OU valider que `--dir` existe et contient un `wiki/` plutôt que vérifier l'inclusion dans VAULT_PATH unique

À envisager si plusieurs projets utilisent ce brain régulièrement.

## Scripts disponibles

| Script | Rôle |
|--------|------|
| `brain.py` | Save/load mémoire session Supabase |
| `event_log.py` | Logging d'événements |
| `feedback_pipeline.py` | Pipeline feedback utilisateur |
| `graph_extractor.py` | Extraction graphe de connaissance |
| `memory_store.py` | Stockage mémoire local |
| `rag_bridge.py` | Bridge RAG |
| `rag_dashboard.py` | Dashboard RAG |
| `sync.py` | Sync vault Obsidian ↔ Supabase |
| `utils.py` | Utilitaires partagés |

## Source originale

Ce dossier est une copie de `D:/base-de-donnees/_scripts/`. Pour mettre à jour, copier les fichiers depuis là.
