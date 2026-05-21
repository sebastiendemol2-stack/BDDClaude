# Query — Recherche profonde dans le wiki

Recherche et synthetise de l'information a partir du vault.

## Etapes

### 1. Lire l'index

Lire `wiki/index.md` pour identifier quelle categorie et quelle note est la plus susceptible de contenir la reponse.

### 2. Naviguer

Ouvrir la note wiki identifiee. Si la reponse necessite plusieurs notes, les lire toutes.

### 3. Synthetiser

Formuler une reponse structuree basee uniquement sur le contenu du wiki.

### 4. Proposer un enrichissement

Si la recherche produit une nouvelle synthese utile (croisement de plusieurs notes, conclusion nouvelle) :

- Proposer a l'utilisateur de creer ou enrichir une note wiki avec cette synthese
- Ne JAMAIS ecrire sans validation explicite de l'utilisateur

### 5. Ecrire dans le log

Ajouter une entree dans `wiki/log.md` :

```
YYYY-MM-DD HH:MM — Query : "question posee" → wiki/chemin/note.md
```

## Regles

- Ne JAMAIS inventer d'information absente du wiki — si la donnee n'existe pas, le dire clairement
- Ne JAMAIS scanner tous les fichiers du wiki — utiliser l'index comme point d'entree
- Ne JAMAIS modifier raw/
- Toujours citer la source (nom de la note wiki) dans la reponse
