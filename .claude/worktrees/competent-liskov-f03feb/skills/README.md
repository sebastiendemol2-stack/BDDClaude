# Skills — Installation

Ces fichiers sont des slash commands pour Claude Code.

## Comment installer

Copie chaque fichier `.md` (sauf ce README) dans le dossier :

```
~/.claude/commands/
```

Sur Mac/Linux : `~/.claude/commands/`
Sur Windows : `%USERPROFILE%\.claude\commands\`

## Utilisation

Une fois copies, les commandes sont disponibles dans Claude Code :

| Commande  | Role                                    |
| --------- | --------------------------------------- |
| `/prime`  | Charger le contexte en debut de session |
| `/ingest` | Compiler raw/ vers wiki/                |
| `/save`   | Sauvegarder la session                  |
| `/query`  | Rechercher dans le wiki                 |
| `/lint`   | Verifier la sante du vault              |

## Premier test

1. Ouvre Claude Code dans le dossier du vault
2. Tape `/prime` — Claude charge le contexte
3. Tape `/ingest` — Claude compile l'exemple dans raw/notes/
4. Verifie que wiki/ contient une nouvelle note
