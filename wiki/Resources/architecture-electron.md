---
title: "Architecture Technique"
date: 2026-05-07
tags: [electron, architecture, patterns, supabase]
type: ressource
status: active
confidence: high
source_type: extraction
freshness: evergreen
sensitivity: public
---

# Architecture Technique

## Architecture Electron — Cowork IA

### Separation main/renderer

- **main.cjs** : Processus principal Electron — gere les fenetres, les IPC handlers, le bridge Ollama (API HTTP), le sandbox Docker (Dockerode), le browser automation (Puppeteer/CDP), le cron de reporting, et la persistence des preferences. Point d'entree unique, secure par `contextIsolation: true`.
- **preload.cjs** : Pont securise entre main et renderer. Expose une API minimaliste au renderer via `contextBridge.exposeInMainWorld()`. Chaque groupe de fonctionnalites a son propre bloc d'exposition (app, ollama, models, knowledge, sandbox, copilot). Aucun acces direct a Node.js.
- **renderer** : Application React 19 + Vite 6. Strictement UI — aucune capacite systeme. Se connecte au main via les canaux definis dans preload. Architecture feature-first : chat/, models/, settings/, tasks/, knowledge/.

### Securite

- `contextIsolation: true` — le renderer n'a pas acces aux APIs Node.js
- `nodeIntegration: false` — pas de `require()` dans le renderer
- `sandbox: true` — le processus renderer est sandboxe
- Content Security Policy stricte sur les charges utiles HTML
- Validation des arguments IPC cote main avant traitement

### IPC Channels

20 canaux organises en 5 groupes :

| Groupe | Canaux | Role |
|--------|--------|------|
| app | window-open, window-close, app-quit, app-version | Cycle de vie fenetre |
| ollama | chat, pull, list, status, embeddings | Interface Ollama |
| models | switch, get-status, list-local, list-cloud | Gestion modeles |
| knowledge | read, write, search, delete, list-notes | Vault Obsidian |
| sandbox | docker-exec, browser-navigate, browser-screenshot, sandbox-status, sandbox-approval | Executeurs |

+ 10 canaux copilot definis (non encore actives cote renderer).

### Routing (scoreModel)

- **light** : Qwen 2.5 3B, Gemini Flash — questions factuelles, chat rapide
- **medium** : Qwen 3 4B, Claude Haiku — analyse, ecriture, code simple
- **heavy** : Llama 3.1 8B, Claude Sonnet/Opus, Gemini Pro — raisonnement complexe, audit, refactoring

Le mode hybride utilise Qwen3 ou Claude Haiku comme orchestrateur : il evalue la requete entrante, la classifie par domaine (code, reasoning, writing, analysis, chat, devops) et complexite (light/medium/heavy), puis distribue au sous-modele approprie.

### Patterns retenus

- IndexedDB via Dexie pour knowledge base locale
- cowork_prefs.json pour persistence legere des preferences
- subagent-memory.json avec TTL pour memoire sous-agents
- contextIsolation true + nodeIntegration false
- IPC request/response synchrone pour les actions, asynchrone (events) pour les streams

### Testabilite

- Tests Jest pour main.cjs (IPC handlers mockes)
- Tests Jest pour preload.cjs (bridge API)
- Tests React Testing Library pour le renderer
- Tests d'integration : lancement Electron + interaction renderer
- Tests Ollama : mock server HTTP local
- 384 tests total, build 11.5s, 0 erreurs

## Supabase Vault Schema

Tables : vault_sections, vault_entries, vault_embeddings, vault_chunks, vault_transactions, vault_snapshots, vault_profile, vault_journal, vault_links_from
Projet ID : ottoqbwctcpzzdfzewdi — region eu-central-1

## Liens

- [[Context/cowork-ia]]
