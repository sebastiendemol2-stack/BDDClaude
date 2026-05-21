---
date: 2026-05-07
tags: [cowork, electron, react, ia]
type: contexte
status: active
---

# Cowork IA — Vue d'ensemble

## Architecture

App Electron (main.cjs + preload.cjs) + Frontend React/Vite.
Feature-first : chat/, models/, settings/, tasks/, knowledge/.
contextIsolation: true, nodeIntegration: false.

## Modeles

Locaux (Ollama): Qwen 2.5 3B, Qwen 3 4B, Qwen Coder 7B, Llama 3.1 8B, DeepSeek-R1 8B, Gemma 4.
Cloud: Gemini Flash/Pro, Claude Haiku/Sonnet/Opus.

## Routing scoreModel()

Complexite: light / medium / heavy.
Domaines: code, reasoning, writing, analysis, chat, devops.
Mode hybride: orchestrateur Qwen3/Claude Haiku.

## IPC

20 canaux main<->renderer. 10 canaux copilot definis, non encore appeles cote renderer.

## Persistence

Knowledge base: IndexedDB via Dexie. Config: cowork_prefs.json.

## Liens

- [[subagent-workflows]]
- [[architecture-electron]]
