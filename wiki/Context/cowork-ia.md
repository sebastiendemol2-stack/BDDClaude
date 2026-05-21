---
title: "Cowork IA — Vue d'ensemble"
date: 2026-05-07
tags: [cowork, electron, react, ia]
type: contexte
status: active
confidence: high
source_type: extraction
freshness: volatile
sensitivity: internal
---

# Cowork IA — Vue d'ensemble

## Architecture

App Electron (main.cjs + preload.cjs) + Frontend React/Vite.
Feature-first : chat/, models/, settings/, tasks/, knowledge/.
contextIsolation: true, nodeIntegration: false.
Le processus main gere les IPC handlers, le bridge Ollama, le sandbox Docker, le browser automation, et la persistence. Le renderer est strictement UI — aucune capacite systeme.

### Stack detaille

- **Runtime** : Electron 33+, Node.js 22+
- **Frontend** : React 19 + Vite 6, React Router 7 (layout routes imbriquees)
- **State** : React Context (useReducer) + Dexie IndexedDB pour la persistance locale
- **Backend IA** : Ollama (local) via API HTTP, API Claude/Gemini (cloud) via fetch
- **Outils** : Puppeteer (browser), Dockerode (sandbox), Dexie.js (IndexedDB)
- **Build** : electron-builder, 11.5s clean build, 0 warnings

### Phase actuelle

L'application est en **phase 3** (des 5 prevues) :
1. POC — Electron + React + Ollama bridge fonctionnel
2. MVP — Routing multi-modeles, chat, copilot dans l'IDE
3. **Actuelle** — Browser automation, Docker sandbox, multi-vault knowledge, Jan migration
4. Prevue — Agents long-running, RAG, taches planifiees
5. Vision — Multi-agent orchestration, personal AI workspace

## Modeles

Locaux (Ollama): Qwen 2.5 3B, Qwen 3 4B, Qwen Coder 7B, Llama 3.1 8B, DeepSeek-R1 8B, Gemma 4.
Cloud: Gemini Flash/Pro, Claude Haiku/Sonnet/Opus.
Fallback automatique : si Jan est absent, les modeles locaux sont masques, le cloud prend le relais.

## Routing scoreModel()

Complexite: light / medium / heavy.
Domaines: code, reasoning, writing, analysis, chat, devops.
Mode hybride: orchestrateur Qwen3/Claude Haiku evalue la requete, distribue au sous-modele approprie.
Le score prend en compte : la longueur du prompt, la specialite du domaine, la latence acceptable, et la disponibilite du modele (local vs cloud).

## IPC

20 canaux main<->renderer organises en 5 groupes : app (fenetre, quit), ollama (chat, pull, list), models (status, switch), knowledge (read, write, search), sandbox (docker, browser). 10 canaux copilot definis, non encore appeles cote renderer — ils seront actives dans la phase 4 pour le copilot IDE.

## Persistence

Knowledge base: IndexedDB via Dexie. Config: cowork_prefs.json.
Le vault Obsidian est synchronise avec Supabase via `_scripts/sync.py` — la connaissance n'est pas enfermee dans l'app.

## Liens

- [[Context/subagent-workflows]]
- [[Resources/architecture-electron]]
