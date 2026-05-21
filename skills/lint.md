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

### 6. Staging obsoletes

Scanner `wiki/_staging/` pour les notes en attente de validation depuis plus de 7 jours.

Pour chaque fichier dans `wiki/_staging/*.md` :
- Lire le frontmatter, extraire `date:`
- Si `last_reviewed:` existe, utiliser cette date comme reference d'age
- Calculer l'age en jours = aujourd'hui - date de reference
- Si age > 7 jours : action requise
- Si age <= 7 jours : listing informatif uniquement

**Actions interactives (pour chaque note > 7j) :**

L'LLM doit proposer ces options et attendre la reponse :

- `p` (Promouvoir) :
  1. Demander le dossier de destination : (1) Intelligence (2) Context (3) Resources
  2. Verifier qu'aucun conflit de nom n'existe dans le dossier cible
  3. Si conflit : proposer fusion / renommage / annulation
  4. Changer `status: staging` → `status: active` dans le frontmatter
  5. Ajouter les champs par defaut du statut active si absents
  6. Deplacer physiquement le fichier de `wiki/_staging/` vers `wiki/{dossier}/`
  7. Mettre a jour `wiki/log.md` avec la promotion
  8. Suggérer la mise a jour de `wiki/index.md`

- `a` (Archiver) :
  1. Changer `status: staging` → `status: archive` dans le frontmatter
  2. Modifier `freshness: volatile` → `freshness: deprecated`
  3. Modifier `confidence` → `low`
  4. Laisser le fichier dans `_staging/` (ou le deplacer vers un dossier d'archive)
  5. Logger dans `wiki/log.md`

- `k` (Keep / Prolonger) :
  1. Ajouter ou mettre a jour le champ `last_reviewed: YYYY-MM-DD` (date du jour)
  2. NE PAS modifier `date:` — la date de creation originale est preservee
  3. Le calcul d'age utilisera `last_reviewed` au prochain lint
  4. Logger dans `wiki/log.md`

- `s` (Skip) :
  1. Passer a la note suivante sans modification

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

### Staging obsoletes : X notes > 7j
- liste des notes depassees avec age et action recommandee

### Actions recommandees
- [ ] Ajouter des liens vers les notes orphelines
- [ ] Corriger ou supprimer les liens casses
- [ ] Ajouter les notes manquantes dans l'index
```

### Ecrire dans le log

Ajouter une entree dans `wiki/log.md` :

```
YYYY-MM-DD HH:MM — Lint : X orphelines, X liens casses, X index manquants, X staging obsoletes
```

## Regles

- Ne JAMAIS corriger automatiquement — proposer les corrections, l'utilisateur valide
- Ne JAMAIS modifier raw/
- Ne JAMAIS supprimer de notes — proposer l'archivage (status: archive)
- Pour la promotion staging : demander le dossier cible avant de deplacer
- Pour le keep staging : toujours ajouter/mettre a jour `last_reviewed` — ne jamais juste skipper sans modifier
