# /ukp — Universal Knowledge Protocol

Interface standardisée vers le backend UKP (Supabase). Utilisable depuis n'importe quel IDE — Claude Code, OpenCode, VS Code (via extension MCP), Cursor.

## Serveur MCP

Le serveur MCP UKP expose 3 tools + resources :

| Tool | Description | Paramètres |
|------|-------------|------------|
| `query` | Recherche hybride (FTS + vector) | `{ query, max_results?, project? }` |
| `prime` | Chargement contexte vault | `{ project? }` |
| `session` | Gestion session | `{ action: begin\|end\|inject, session_id?, ... }` |

### Resources MCP
- `vault://notes/{path}` — Lire une note
- `vault://projects/{slug}` — Lister les notes d'un projet
- `vault://sections/{slug}` — Contenu d'une section
- `vault://session/current` — Session active
- `vault://memory/{project}` — Mémoire persistante

## Endpoints REST (fallback)

```
POST https://ottoqbwctcpzzdfzewdi.supabase.co/functions/v1/ukp-mcp
POST https://ottoqbwctcpzzdfzewdi.supabase.co/functions/v1/ukp-query
POST https://ottoqbwctcpzzdfzewdi.supabase.co/functions/v1/ukp-session
POST https://ottoqbwctcpzzdfzewdi.supabase.co/functions/v1/ukp-discover
POST https://ottoqbwctcpzzdfzewdi.supabase.co/functions/v1/ukp-stream
```

## SDK TypeScript

```typescript
import { UKPClient } from './chemin/vers/ukp-client'

const client = new UKPClient({
  url: 'https://ottoqbwctcpzzdfzewdi.supabase.co',
  key: process.env.SUPABASE_SERVICE_ROLE_KEY!,
  clientIde: 'claude-code',
  profile: 'rag-default',
})

// Utilisation
await client.prime()
await client.query('architecture vault')
await client.beginSession()
await client.buildContextPrompt('Comment configurer sync?')
await client.endSession(sessionId, { summary: '...' })
```

## Commandes rapides

| Commande | Action |
|----------|--------|
| `/ukp prime` | Charge le contexte vault |
| `/ukp query <...>` | Recherche dans la connaissance |
| `/ukp session` | Démarre une session tracée |
| `/ukp discover` | Liste outils + ressources disponibles |
