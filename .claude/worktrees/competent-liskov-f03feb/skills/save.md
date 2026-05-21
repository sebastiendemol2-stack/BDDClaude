# Save — Sauvegarde de session

Sauvegarde l'etat de la session en cours. A lancer en fin de session.

## Etapes

### 0. Sauvegarder dans claude-brain

Lancer brain.py save avec un resume de la session :

```bash
python _scripts/brain.py save --dir "D:\Dev\base-de-donnees" --summary "<resume 1-2 phrases de ce qui a ete fait>" --mode full
```

Si brain.py echoue (Supabase inaccessible), continuer les etapes suivantes sans erreur fatale.

---

### 1. Daily note

Creer ou mettre a jour `wiki/Daily/YYYY-MM-DD.md` (date du jour) :

```yaml
---
date: YYYY-MM-DD
tags: [daily]
type: daily
status: active
---
```

Contenu :

- **Actions** — ce qui a ete fait cette session (bullet points)
- **Decisions** — choix pris et pourquoi
- **Prochaine etape** — ce qui reste a faire

### 2. Mettre a jour wiki/index.md

Si de nouvelles notes wiki ont ete creees pendant la session, ajouter les entrees manquantes dans l'index.

### 3. Ecrire dans le log

Ajouter une entree dans `wiki/log.md` :

```
YYYY-MM-DD HH:MM — Save : daily note creee/mise a jour, index verifie
```

### 4. Confirmation

Afficher un resume court de ce qui a ete sauvegarde.

## Regles

- Ne JAMAIS supprimer de contenu existant dans une daily note — uniquement ajouter
- Ne JAMAIS modifier raw/ pendant /save
- Ne JAMAIS creer de note orpheline
- Executer directement sans demander confirmation
