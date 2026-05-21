# Lint — Health-check du vault

Verifie l'integrite et la coherence du vault. A lancer periodiquement (1x/semaine recommande).

## Checks

### 1. Notes orphelines

Scanner toutes les notes dans `wiki/`. Pour chaque note, verifier qu'au moins un wiki link entrant ou sortant existe. Lister les orphelines.

### 2. Liens casses

Scanner tous les `[[wiki links]]` dans le vault. Verifier que chaque lien pointe vers une note existante. Lister les liens casses.

### 3. Index a jour

Comparer la liste des notes dans `wiki/` avec les entrees dans `wiki/index.md`. Lister les notes absentes de l'index.

### 4. Taille de l'index

Compter les lignes de `wiki/index.md`. Si > 200 lignes, recommander la creation de sous-index par categorie.

### 5. Coherence frontmatter

Verifier que chaque note wiki a un frontmatter valide avec les champs obligatoires : date, tags, type, status.

## Rapport

Afficher :

```
## Lint termine

### Orphelines : X
- liste des notes sans liens

### Liens casses : X
- [[Lien]] dans note.md → note cible inexistante

### Index incomplet : X notes manquantes
- liste des notes absentes de l'index

### Index : XX lignes (OK | ATTENTION > 200)

### Frontmatter invalide : X
- liste des notes avec champs manquants

### Actions recommandees
- [ ] Ajouter des liens vers les notes orphelines
- [ ] Corriger ou supprimer les liens casses
- [ ] Ajouter les notes manquantes dans l'index
```

### Ecrire dans le log

Ajouter une entree dans `wiki/log.md` :

```
YYYY-MM-DD HH:MM — Lint : X orphelines, X liens casses, X index manquants
```

## Regles

- Ne JAMAIS corriger automatiquement — proposer les corrections, l'utilisateur valide
- Ne JAMAIS modifier raw/
- Ne JAMAIS supprimer de notes — proposer l'archivage (status: archive)
