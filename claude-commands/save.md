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

**Sur ce poste Windows, utiliser ce pattern PowerShell** :

```powershell
$projectDir = (Get-Location).Path
$oneDriveRoot = $env:OneDrive
if (-not $oneDriveRoot) { $oneDriveRoot = Join-Path $env:USERPROFILE 'OneDrive' }

if ($projectDir -like "$oneDriveRoot\Developpement\*") {
  $brain = Join-Path $oneDriveRoot 'Developpement\BDDClaude\_scripts\brain.py'
  $env:VAULT_PATH = $projectDir
  python $brain save --dir $projectDir --summary "Resume de la session : ce qui a ete fait" --mode full
} else {
  Write-Host "[skip] Projet hors $oneDriveRoot\Developpement - brain partage non utilise"
}
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
