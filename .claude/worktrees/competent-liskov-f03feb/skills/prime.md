# Prime — Chargement de contexte

Charge le contexte du vault au debut de chaque session Claude Code.

## Etapes

1. **Lance brain.py load** pour charger la memoire persistante depuis Supabase :
   ```bash
   python _scripts/brain.py load --dir "D:\Dev\base-de-donnees"
   ```

2. **Lis `wiki/context-session.md`** — genere par l'etape precedente, contient la memoire projet et l'ID de session active

3. **Lis `CLAUDE.md`** a la racine du vault — ce sont les instructions operationnelles

4. **Lis `wiki/index.md`** — c'est le panneau de direction du wiki

5. **Lis la derniere daily note** dans `wiki/Daily/` — c'est le resume de la session precedente

## Output attendu

Confirme ce qui a ete charge en resumant :

- Nombre d'entrees memoire chargees depuis claude-brain
- ID de session active (8 premiers caracteres)
- Nombre de categories dans l'index
- Derniere daily note lue (date)

## Regles

- Ne JAMAIS ecrire dans le vault pendant /prime — operation lecture uniquement
- Ne JAMAIS scanner tous les fichiers du wiki — utilise l'index comme point d'entree
- Si brain.py echoue (Supabase inaccessible), continuer sans erreur fatale
- Si l'index n'existe pas ou est vide, le signaler a l'utilisateur
