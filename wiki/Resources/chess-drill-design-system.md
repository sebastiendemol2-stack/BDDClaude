---
title: "Chess Drill — Design System"
date: 2026-05-24
tags: [chess-drill, design-system, ui, ux, tokens, css]
type: ressource
status: active
confidence: high
source_type: raw
freshness: volatile
sensitivity: internal
derived_from:
  - path: raw/docs/23-cahier-des-charges-ui-ux.md
    relation: source
  - path: raw/docs/22-training-screen-mobile.md
    relation: source
  - path: raw/docs/25-sound-feedback-foundation.md
    relation: source
---

# Chess Drill — Design System

## Direction artistique

- **Style** : gamifié, coloré, intuitif — inspiré Duolingo/Candy Crush
- **Univers** : sombre spatial, accents néon (pink, cyan, mint)
- **Plateforme** : PWA mobile-first strict (375×812 base iPhone X)
- **Règle d'or** : 1 héro visuel maximum par zone

## Design Tokens CSS

### Couleurs

```css
/* Backgrounds */
--cd-bg: #09071c;           --cd-surface: #120b34;
--cd-surface-soft: #1a1149; --cd-panel: #1e1760;
--cd-panel-border: #32247e;

/* Text */
--cd-text: #f7f3ff;         --cd-text-muted: #c8bfe6;

/* Accents */
--cd-accent-pink: #f6275b;  --cd-accent-cyan: #18c5d9;
--cd-accent-mint: #3df2f2;  --cd-accent-lilac: #d3b3cb;
--cd-accent-red: #d90404;

/* Semantic */
--cd-success: #48d56a;      --cd-warning: #ffbf33;
```

### Typographie

Font : `'Segoe UI', 'Trebuchet MS', sans-serif` (bubble font custom à valider)

```css
--cd-text-xs: clamp(0.66rem, 1.4vw, 0.72rem);   /* labels, pills */
--cd-text-sm: clamp(0.72rem, 1.6vw, 0.78rem);   /* meta, badges */
--cd-text-base: clamp(0.82rem, 1.8vw, 0.92rem); /* body */
--cd-text-lg: clamp(0.95rem, 2.2vw, 1.05rem);   /* titres cartes */
--cd-text-xl: clamp(1.2rem, 3vw, 1.5rem);        /* grands titres */
--cd-text-hero: clamp(1.5rem, 4vw, 2rem);        /* hero/splash */
```

### Espacements (grille 4px), rayons, motion

```css
--cd-space-{1-6}: 4px, 8px, 12px, 16px, 20px, 24px

--cd-radius-sm: 10px;  --cd-radius-md: 14px;
--cd-radius-lg: 18px;  --cd-radius-xl: 24px;  --cd-radius-pill: 999px;

--cd-motion-fast: 120ms;  --cd-motion-base: 220ms;  --cd-motion-slow: 420ms;
--cd-ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
--cd-ease-smooth: cubic-bezier(0.22, 0.61, 0.36, 1);
```

### Z-Index scale

```css
--cd-z-board: 1;  --cd-z-hud: 10;  --cd-z-dropdown: 20;
--cd-z-overlay: 40;  --cd-z-modal: 60;  --cd-z-toast: 80;
--cd-z-critical: 100;
```

**Règle** : aucun z-index hardcodé hors de ces tokens.

## Composants clés

### Bubble Button (border-radius: 999px, min-height: 42px)

- `primary` : gradient pink `#f6275b → #b6163f`
- `secondary` : gradient cyan `#18c5d9 → #0f8b98`
- `success` : gradient green `#73db3d → #3ea922`
- `outline` : border rgba(white,0.24), bg rgba(white,0.07)
- `disabled` : opacity 0.5
- Touch states : pressed scale(0.97) 120ms, hover translateY(-2px)

### Level Card (min-height: 90px, border-radius: 14px)

- `done` : border green glow, bg rgba(green, 0.26)
- `current` : border mint glow + pulse, bg rgba(pink+cyan, 0.3)
- `locked` : opacity 0.62, cadenas

### Feedback chips (pill)

| État | Background | Texte |
|------|-----------|-------|
| `correctMove` | #48d56a | #083217 |
| `wrongMove` | #d90404 | #fff |
| `puzzleSolved` | #18c5d9 | #052f35 |
| `levelCompleted` | #3df2f2 | #083840 |
| `starLost` | #ffbf33 | #4d3500 |
| `levelFailed` | #f6275b | #fff |

### Hints (3 types, grille 3 col, min-height 72px)

| Hint | Icône |
|------|-------|
| Coup Direct | 🎯 |
| Coup Sûr | 🛡️ |
| Force le Coup | 💪 |

## Layout Interface de Jeu

```
Top HUD    : Niveau, progression (1/5), ⭐ 3, timer, Zen toggle
Board area : Échiquier central dominant (92vw max, mobile portrait)
Bottom HUD : Trait, solutions count
           : [⟳ Retry] [Next ➜]
           : [Coup Direct] [Coup Sûr] [Force le Coup]
Bottom nav : 🏠 🌍 📚 👤 ⚙️
```

**Mode Zen** : cache hint rows et infos secondaires, agrandit le plateau.

## États système et gameplay

| Catégorie | États |
|-----------|-------|
| Système | loading, success, error, empty, offline |
| Gameplay | idle, thinking, correct, incorrect, combo, completed, failed |
| Pédagogique | hint-visible, review-mode, solution-visible, retry-available |
| Gamification | xp-gain, streak-updated, level-up, reward-unlocked |

**Règle** : un composant ne gère jamais plus de 2 catégories d'état directement.

## Audio UX

| Catégorie | Durée max |
|-----------|-----------|
| `move` (coup joué) | <300ms |
| `success` (puzzle résolu) | <500ms |
| `error` (coup incorrect) | <300ms |
| `reward` (XP, étoile) | <800ms |
| `streak` | <500ms |
| `level-up` | <1s |

**Règles** : volume soft 40% par défaut, désactivable globalement, jamais bloquant.

## Breakpoints responsive

```css
--cd-bp-xs: 360px; --cd-bp-sm: 480px; --cd-bp-md: 768px;
--cd-bp-lg: 1024px; --cd-bp-xl: 1440px;
```

Touch targets : 44×44px minimum. Safe areas : `env(safe-area-inset-*)`.

## Thèmes futurs réservés

`neon` (actuel), `classic`, `cyber`, `pastel`, `midnight`

## Voir aussi

- [[Context/chess-drill]] — contexte et vision produit
- [[Intelligence/chess-drill-gamification]] — mécaniques et états gamification
- [[Intelligence/chess-drill-architecture]] — architecture React et règles couches
