# Setup VS Code + Claude Code — maximoute

Guide pour activer le brain Claude partagé (mémoire Supabase) sur ton poste depuis VS Code.

Une fois ce setup fait, `/save` et `/prime` marcheront dans tous les projets de `$OneDrive/Developpement/` automatiquement, en utilisant les credentials et le code synchronisés via OneDrive.

---

## 1. Pré-requis (5 minutes)

### A. VS Code
Déjà installé probablement. Sinon : https://code.visualstudio.com/

### B. Python 3.10 ou plus récent
Vérifie dans un terminal :
```bash
python --version
```
Doit afficher `Python 3.10.x` minimum. Sinon, installer depuis https://python.org (cocher **"Add Python to PATH"** pendant l'installation).

### C. Git Bash (déjà installé si tu utilises Git)
Vérifie :
```bash
bash --version
```
Sinon, installer Git for Windows : https://git-scm.com/download/win (inclut Git Bash).

### D. Extension Claude Code dans VS Code
Dans VS Code → Extensions (`Ctrl+Shift+X`) → chercher **"Claude Code"** → Install.

(Ou tu peux utiliser le CLI directement : https://docs.anthropic.com/claude/docs/claude-code)

### E. Vérifier que OneDrive est bien synchronisé
Dans un terminal Git Bash :
```bash
echo $OneDrive
```
Doit afficher un chemin comme `C:\Users\TonNom\OneDrive` (ou similaire). Si rien ne s'affiche :
- Ouvrir l'app OneDrive → s'assurer qu'elle est en train de sync
- Redémarrer la session Windows pour que les variables d'env soient prises en compte

Puis vérifie que le brain est bien synchronisé :
```bash
ls "$OneDrive/Developpement/BDDClaude/_scripts/brain.py"
```
Doit retourner le chemin (pas d'erreur). Si erreur, attendre que OneDrive finisse de sync.

---

## 2. Installer les commandes /save et /prime (2 minutes)

### Option A — Copie simple (la plus rapide)

Dans Git Bash :
```bash
mkdir -p ~/.claude/commands
cp "$OneDrive/Developpement/BDDClaude/claude-commands/save.md" ~/.claude/commands/save.md
cp "$OneDrive/Developpement/BDDClaude/claude-commands/prime.md" ~/.claude/commands/prime.md
```

**Inconvénient** : si Skewstony met à jour les commandes, tu ne reçois pas la maj automatiquement. Faut refaire la copie.

### Option B — Lien symbolique (auto-update via OneDrive)

Dans **PowerShell en admin** :
```powershell
$onedrive = $env:OneDrive
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\commands\save.md" -Target "$onedrive\Developpement\BDDClaude\claude-commands\save.md"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\commands\prime.md" -Target "$onedrive\Developpement\BDDClaude\claude-commands\prime.md"
```

**Avantage** : à chaque modif des commandes dans OneDrive, tu as la maj immédiatement.

---

## 3. Test (1 minute)

### A. Ouvrir un projet OneDrive dans VS Code
Exemple :
```bash
code "$OneDrive/Developpement/ChessDrill"
```

### B. Ouvrir Claude Code dans VS Code
- Soit l'extension (panneau latéral)
- Soit dans le terminal VS Code intégré : taper `claude`

### C. Lancer /save (mode full)
Dans la conversation Claude :
```
/save
```

Claude va lire `save.md`, détecter que le projet est dans `$OneDrive/Developpement/`, et lancer le brain. Si succès, tu verras :
```
[OK] Session closed (mode: full) | <session_id>...
```

---

## 4. Setup auto-save par projet (optionnel mais recommandé)

Pour que le brain sauvegarde automatiquement à la fin de chaque session sans avoir à taper `/save`, ajouter ce fichier dans **chaque projet** OneDrive :

`<projet>/.claude/settings.json` :
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'ONEDRIVE_ROOT=\"${OneDrive:-${ONEDRIVE:-$HOME/OneDrive}}\"; PROJECT_DIR=\"$(pwd)\"; case \"$PROJECT_DIR\" in \"$ONEDRIVE_ROOT\"/Developpement/*) VAULT_PATH=\"$PROJECT_DIR\" python \"$ONEDRIVE_ROOT/Developpement/BDDClaude/_scripts/brain.py\" load --dir \"$PROJECT_DIR\" ;; esac'"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'ONEDRIVE_ROOT=\"${OneDrive:-${ONEDRIVE:-$HOME/OneDrive}}\"; PROJECT_DIR=\"$(pwd)\"; case \"$PROJECT_DIR\" in \"$ONEDRIVE_ROOT\"/Developpement/*) VAULT_PATH=\"$PROJECT_DIR\" python \"$ONEDRIVE_ROOT/Developpement/BDDClaude/_scripts/brain.py\" save --dir \"$PROJECT_DIR\" --mode close ;; esac'"
          }
        ]
      }
    ]
  }
}
```

Effet :
- **SessionStart** : charge le contexte automatiquement au début de chaque session Claude
- **Stop** : ferme la session proprement à la fin

---

## 5. Dépannage

### `command not found: python`
Python n'est pas dans le PATH. Réinstaller en cochant **"Add Python to PATH"**.

### `$OneDrive` est vide
Variable d'environnement pas définie. Solutions :
1. Redémarrer la session Windows après installation OneDrive
2. Définir manuellement : `Système → Variables d'environnement → Nouvelle → OneDrive=C:\Users\TonNom\OneDrive`

### `[ERROR] Chemin invalide`
La variable `VAULT_PATH` doit matcher exactement le projet courant. Vérifier que tu lances la commande depuis la racine du projet, pas un sous-dossier.

### Le brain ne se synchronise pas
Vérifier que OneDrive n'a pas mis le dossier `_scripts/` en "freed up space" (libéré). Clic droit sur le dossier → "Always keep on this device".

---

## 6. Que se passe-t-il sous le capot ?

1. **Chaque save** envoie en Supabase :
   - Le résumé que tu fournis (ou Claude génère)
   - Les fichiers récemment modifiés dans le projet
   - Les conversations Claude/Copilot loggées
2. **Chaque load** récupère depuis Supabase :
   - Les 5 dernières sessions du même projet
   - Génère `wiki/Context/context-session.md` que Claude lit au démarrage

3. **Les credentials Supabase** sont dans `$OneDrive/Developpement/BDDClaude/_scripts/.env` — tu n'as rien à configurer, c'est déjà là.

---

## Contact

Si ça marche pas, demander à Skewstony. Lui a déjà ce setup qui tourne.
