---
title: "Chess Drill — Projet"
date: 2026-05-24
tags: [chess-drill, projet, echecs, gamification, refactorisation]
type: projet
status: active
confidence: high
source_type: raw
freshness: volatile
sensitivity: internal
derived_from:
  - path: raw/docs/00-contexte-general.md
    relation: source
  - path: raw/docs/01-vision-produit.md
    relation: source
  - path: raw/docs/02-etat-actuel-du-projet.md
    relation: source
  - path: raw/notes/conversation maximoute chessdrill.md
    relation: source
---

# Chess Drill — Projet

## Résumé

Application web d'entraînement tactique aux échecs en cours de refactorisation vers une expérience gamifiée complète. Le produit existant est fonctionnel, mais souffre de dette technique structurelle. L'ambition : transformer Chess Drill en un Duolingo des échecs avec XP, streaks, vies, carte de progression et récompenses.

## Vision produit

**Pitch** : Entraîne-toi chaque jour sur des puzzles utiles, vois précisément tes progrès, corrige tes erreurs ciblées, et reste motivé grâce à une progression gamifiée lisible.

**Public cible** :
- Joueurs débutants/intermédiaires cherchant une routine tactique
- Joueurs club voulant une pratique structurée
- Coachs/créateurs gérant des bibliothèques de puzzles

**Inspirations** :
- Duolingo (streaks, XP, objectifs quotidiens)
- Candy Crush (carte de progression, mondes, niveaux)
- Chess.com / Lichess (qualité du plateau, feedback tactique)

**Plateforme** : PWA mobile-first (375×812 base), univers sombre spatial néon (pink/cyan/mint)

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | Node.js + Express + MySQL |
| Frontend | React 18 + Zustand + Axios |
| Échiquier | chess.js + chessground (wrapper ChessgroundBoard) |
| Infra | Docker Compose |
| Validation | Joi |
| Auth | JWT + bcryptjs |

## Ce qui fonctionne actuellement

- Auth JWT (register/login/profile)
- CRUD bibliothèques/puzzles/solutions admin
- Résolution de puzzles avec validation chess.js
- Plusieurs lignes de solution par puzzle
- Session d'entraînement avec timer et progression
- Mode exploration libre
- Revue des puzzles en erreur

## Ce qui n'existe pas encore

- Gamification (XP, streaks, vies, niveaux, carte monde) — implémenté en mock local
- Tests automatisés
- Design system UI unifié
- Normalisation complète des contrats API

## État mock local (2026-05-20)

Boucle MVP complète disponible **sans backend** :
- World Map mock → Training → End Of Level → retour Map
- Persistance localStorage (`cd-world-map-mock-v1`)
- 3 mondes mockés (Easy/prairie, Medium/desert, Hard/nuit)
- Ressources globales (XP, coins, vies, hints)
- Bibliothèque, défis quotidiens, shop, profil : mockés
- Couche d'adaptation backend-ready via `createGameServices.js`
- Niveau local reel jouable : `world-1-l5`, avec un puzzle annote et des lignes de solution.
- Admin UX shell livre : mondes, niveaux, puzzles, solution trees, joueurs, economie, rewards, logs et settings.

Pour lancer : `cd frontend && npm install && npm start` → `http://localhost:3000` → "Continuer en mode local"

## Liens

- [[Intelligence/chess-drill-architecture]] — architecture actuelle et cible
- [[Intelligence/chess-drill-gamification]] — mécanique gamification et boucle de jeu
- [[Intelligence/chess-drill-roadmap]] — roadmap 12 phases + plan stabilisation
- [[Intelligence/chess-drill-local-mvp]] — MVP local, authoring puzzle et validation manuelle
- [[Intelligence/chess-drill-admin-authoring]] — panneau admin et compatibilite authoring
- [[Resources/chess-drill-design-system]] — design tokens, composants, specs UI/UX
