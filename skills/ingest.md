# Ingest — raw/ vers _staging/

Compile les sources brutes du vault en notes staging structurees dans `wiki/_staging/`.

## Etapes

### 1. Scanner raw/

Lister tous les fichiers dans `raw/clippings/`, `raw/docs/`, `raw/notes/`.
Ignorer les fichiers README.md dans chaque sous-dossier.

### 2. Identifier les fichiers non traites

Pour chaque fichier dans raw/ :

- Chercher dans `wiki/_staging/` et `wiki/` une note dont le frontmatter `source:` reference ce fichier
- Si la note staging ou wiki existe et est a jour → skip
- Si le fichier est nouveau → traiter

### 3. Traiter chaque fichier

1. **Lire** le contenu complet du fichier raw
2. **Extraire** les concepts cles, faits, decisions, insights
3. **Decider** : creer une nouvelle note wiki OU enrichir une note existante
   - Sujet existant → enrichir la note wiki correspondante
   - Sujet nouveau → creer dans `wiki/_staging/` (flat)

### 4. Creer ou enrichir la note staging

Chaque note staging doit avoir ce frontmatter :

```yaml
---
date: YYYY-MM-DD
tags: []
type: concept | projet | recherche | decision | ressource
status: staging
confidence: medium
source: raw/chemin/du/fichier.md
source_path: raw/chemin/du/fichier.md
source_type: raw
freshness: volatile
sensitivity: internal
review_status: draft
---
```

Contenu de la note :

- **Resume** — 2-3 phrases, l'essentiel
- **Concepts cles** — bullet points des idees principales
- **Details** — sections structurees si le contenu est riche
- **Liens** — wiki links vers les notes connexes existantes

### 5. Cross-referencer

Pour chaque note creee ou modifiee :

- Ajouter des `[[wiki links]]` vers les notes connexes dans `wiki/`
- Verifier que les notes referencees ont un lien retour
- La note reste dans `wiki/_staging/` jusqu'a validation

### 6. Ne pas ajouter dans l'index

Ne pas ajouter dans l'index — les notes staging ne sont pas indexees

### 7. Ecrire dans le log

Ajouter une entree dans `wiki/log.md` :

```
YYYY-MM-DD HH:MM — Ingest : X fichiers → _staging/, Y nouveaux, Z enrichis
```

### 8. Rapport

Afficher :

```
## Ingest termine

- Fichiers scannes : X
- Nouveaux : Y (liste)
- Enrichis : Z (liste)
- Skipped : W
- Index mis a jour : non
- Log mis a jour : oui/non
```

## Regles

- Ne JAMAIS modifier, renommer ou deplacer un fichier dans raw/
- Ne JAMAIS creer de note superficielle — si un article n'apporte rien de nouveau, ne pas creer de note
- Privilegier l'enrichissement d'une note existante plutot que la creation d'une nouvelle
- Les notes wiki sont des syntheses, pas des copies — reformuler, structurer, extraire la valeur
- Ne JAMAIS creer de note orpheline — au moins un wiki link entrant ou sortant
- Toute note creee dans _staging/ a status: staging obligatoire
