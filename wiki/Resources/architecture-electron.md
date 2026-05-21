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

- main.cjs : processus principal, IPC handler, Ollama bridge
- preload.cjs : pont securise contextIsolation
- renderer : React/Vite, feature-first

## scoreModel() — Logique de routing

- light : Qwen 2.5 3B, Gemini Flash
- medium : Qwen 3 4B, Claude Haiku
- heavy : Llama 3.1 8B, Claude Sonnet/Opus, Gemini Pro

## Patterns retenus

- IndexedDB via Dexie pour knowledge base locale
- cowork_prefs.json pour persistence legere
- subagent-memory.json avec TTL pour memoire sous-agents
- contextIsolation true + nodeIntegration false

## Supabase Vault Schema

Tables : vault_sections, vault_entries, vault_profile, vault_journal
Projet ID : ottoqbwctcpzzdfzewdi — region eu-central-1

## Liens

- [[Context/cowork-ia]]
